import os
from typing import Optional, List


def ensure_file_exists(file_path: str) -> None:
    if not file_path:
        return
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)


def read_file_in_chunks(file_path: str, chunk_size: int = 2048):
    ensure_file_exists(file_path)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def build_chunked_messages(text: str, chunk_size: int = 2048, overlap: int = 200):
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


async def extract_download_links(page) -> List[dict]:
    links = []
    anchors = page.locator("a[href]")
    count = await anchors.count()
    for i in range(count):
        href = await anchors.nth(i).get_attribute("href") or ""
        if href.startswith("https://") and any(
            token in href.lower() for token in ["download", "file", "export", "blob"]
        ):
            text = (await anchors.nth(i).inner_text()).strip()
            links.append({"href": href, "text": text})
    return links