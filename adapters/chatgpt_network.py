import os
import time
import logging
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from core.session import get_page
from core.parser import parse_sse_chunks, extract_text_from_sse_events
from core.files import (
    ensure_file_exists,
    build_chunked_messages,
    extract_download_links,
)

logger = logging.getLogger(__name__)

INPUT_SELECTOR = "#prompt-textarea"
SEND_SELECTOR = "button[data-testid='send-button']"
ASSISTANT_SELECTOR = "[data-message-author-role='assistant']"
FILE_INPUT_SELECTOR = "input[type='file']"
UPLOAD_READY_SELECTOR = "button[data-testid='send-button'], text=Upload complete, .upload-complete"
MAX_FILE_UPLOAD_TIMEOUT = 600000
LONG_TEXT_CHUNK_SIZE = 2048


def send_message(page, message: str):
    page.wait_for_selector(INPUT_SELECTOR, timeout=30000)
    input_box = page.locator(INPUT_SELECTOR)
    input_box.click()
    input_box.press("Control+a")
    input_box.press("Delete")
    input_box.press_sequentially(message)

    send_btn = page.locator(SEND_SELECTOR)
    if send_btn.count() > 0 and send_btn.is_visible():
        send_btn.click()
    else:
        input_box.press("Enter")


def wait_for_assistant(page, timeout: int = 120000):
    page.wait_for_selector(ASSISTANT_SELECTOR, timeout=timeout)


def extract_latest_assistant_text(page) -> str:
    assistant_messages = page.locator(ASSISTANT_SELECTOR)
    count = assistant_messages.count()
    latest = assistant_messages.nth(count - 1)

    old_text = ""
    for _ in range(30):
        try:
            new_text = latest.inner_text(timeout=10000).strip()
        except Exception:
            try:
                new_text = latest.evaluate("el => el.innerText || el.textContent || ''").strip()
            except Exception:
                new_text = ""
        if new_text and new_text == old_text:
            break
        old_text = new_text
        time.sleep(1)

    try:
        return latest.inner_text(timeout=10000).strip()
    except Exception:
        try:
            return latest.evaluate("el => el.innerText || el.textContent || ''").strip()
        except Exception:
            return old_text.strip()


def upload_file(page, file_path: str):
    ensure_file_exists(file_path)

    add_btn = page.locator("button[data-testid='composer-plus-btn']")
    if add_btn.count() == 0:
        raise Exception("File upload button not found")

    add_btn.click()

    try:
        file_input = page.locator(FILE_INPUT_SELECTOR)
        file_input.set_input_files(file_path)
    except Exception:
        add_btn.click()
        file_input = page.locator(FILE_INPUT_SELECTOR)
        file_input.set_input_files(file_path)

    try:
        page.wait_for_selector(UPLOAD_READY_SELECTOR, timeout=MAX_FILE_UPLOAD_TIMEOUT)
    except PlaywrightTimeout:
        logger.warning("File upload timeout; continuing anyway")


def upload_files(page, file_paths):
    if not file_paths:
        return
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for path in file_paths:
        upload_file(page, path)


def network_chat(message: str, file_paths=None, long_text: bool = True) -> dict:
    page, pw, browser = get_page()
    captured = {"chunks": [], "stream_complete": False}

    try:
        def on_response(response):
            url = response.url
            if "/backend-api/f/conversation" not in url:
                return
            try:
                ct = response.headers.get("content-type", "")
                if "text/event-stream" not in ct:
                    return
                body = response.text()
                captured["chunks"].append({"url": url, "body": body})
                if "event: [DONE]" in body or "event: done" in body:
                    captured["stream_complete"] = True
            except Exception as e:
                logger.debug(f"[network] Response read error: {e}")

        page.on("response", on_response)

        if file_paths:
            upload_files(page, file_paths)

        chunks = build_chunked_messages(message, chunk_size=LONG_TEXT_CHUNK_SIZE) if long_text else [message]
        for idx, chunk in enumerate(chunks):
            prefix = f"[Part {idx + 1}/{len(chunks)}] " if len(chunks) > 1 else ""
            send_message(page, f"{prefix}{chunk}")
            if idx < len(chunks) - 1:
                time.sleep(2)

        deadline = time.time() + 120
        while time.time() < deadline:
            if captured["chunks"] and captured["stream_complete"]:
                break
            time.sleep(0.5)

        stream_text = ""
        if captured["chunks"]:
            combined = "\n".join(c.get("body", "") for c in captured["chunks"])
            events = parse_sse_chunks(combined)
            stream_text = extract_text_from_sse_events(events)

        wait_for_assistant(page)
        dom_text = extract_latest_assistant_text(page)
        downloads = extract_download_links(page)

        response_text = stream_text or dom_text
        meta = {
            "captured_chunks": len(captured["chunks"]),
            "stream_complete": captured["stream_complete"],
            "chunk_urls": [c.get("url") for c in captured["chunks"]],
        }

        return {
            "status": "success",
            "mode": "network",
            "response": response_text,
            "meta": meta,
            "chunks_sent": len(chunks),
            "downloads": downloads,
        }
    finally:
        try:
            pw.stop()
        except Exception:
            pass
