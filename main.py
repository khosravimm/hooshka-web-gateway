import os
import json
import time
import uuid
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from api.openai_compat import api_bp
from adapters.chatgpt_dom import dom_chat
from adapters.chatgpt_network import network_chat

app = Flask(__name__)

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/bridge.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CDP_URL = "http://127.0.0.1:9222"
CHATGPT_URL = "https://chatgpt.com"

app.register_blueprint(api_bp, url_prefix="")

BRIDGE_MODES = ["dom", "network"]


@app.route("/modes", methods=["GET"])
def list_modes():
    return jsonify({
        "modes": BRIDGE_MODES,
        "default": "dom",
        "description": {
            "dom": "DOM-based automation using Playwright selectors",
            "network": "Network/WebSocket interception via CDP"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/v1/chat/code", methods=["POST"])
def code_chat():
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    model = data.get("model", "chatgpt-web")
    language = data.get("language")
    code_only = data.get("code_only", False)
    save_to = data.get("save_to")
    stream = data.get("stream", False)
    file_paths = data.get("file_paths") or ([data.get("file_path")] if data.get("file_path") else [])

    if not messages:
        return jsonify({"error": {"message": "messages is required", "type": "invalid_request_error"}}), 400

    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        return jsonify({"error": {"message": "No user message provided", "type": "invalid_request_error"}}), 400

    message = user_messages[-1].get("content", "").strip()
    if not message:
        return jsonify({"error": {"message": "Empty user message", "type": "invalid_request_error"}}), 400

    adapter = "dom"
    try:
        if stream:
            result = network_chat(message, file_paths=file_paths, long_text=True)
            adapter = "network"
        else:
            result = dom_chat(message, file_paths=file_paths, long_text=True)
    except Exception as e:
        logger.error(f"Adapter error: {e}")
        return jsonify({"error": {"message": str(e), "type": "adapter_error"}}), 500

    response_text = result.get("response", "")

    from core.code_parser import extract_code_blocks, save_code_block
    blocks = extract_code_blocks(response_text, language=language)

    payload = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text if not code_only else "\n".join(b["code"] for b in blocks),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "code": {
            "blocks": blocks,
            "language": language,
            "count": len(blocks),
        },
    }

    if save_to and blocks:
        try:
            path = save_to if len(blocks) == 1 else save_to
            saved = save_code_block(blocks[0]["code"], path)
            payload["code"]["saved_to"] = saved
        except Exception as e:
            logger.error(f"Save code failed: {e}")

    if result.get("downloads"):
        payload["downloads"] = result["downloads"]
    if result.get("chunks_sent"):
        payload["chunks_sent"] = result["chunks_sent"]
    if result.get("meta"):
        payload["meta"] = result["meta"]

    logger.info(f"/v1/chat/code [{adapter}] language={language} code_only={code_only}")
    return jsonify(payload)


@app.route("/v1/chat/conversation", methods=["POST"])
def conversation_chat():
    data = request.get_json(force=True)
    conversation_id = data.get("conversation_id") or uuid.uuid4().hex
    messages = data.get("messages", [])
    model = data.get("model", "chatgpt-web")
    stream = data.get("stream", False)
    file_paths = data.get("file_paths") or ([data.get("file_path")] if data.get("file_path") else [])

    if not messages:
        return jsonify({"error": {"message": "messages is required", "type": "invalid_request_error"}}), 400

    message = messages[-1].get("content", "").strip()
    if not message:
        return jsonify({"error": {"message": "Empty user message", "type": "invalid_request_error"}}), 400

    adapter = "dom"
    try:
        if stream:
            result = network_chat(message, file_paths=file_paths, long_text=True)
            adapter = "network"
        else:
            result = dom_chat(message, file_paths=file_paths, long_text=True)
    except Exception as e:
        logger.error(f"Adapter error: {e}")
        return jsonify({"error": {"message": str(e), "type": "adapter_error"}}), 500

    response_text = result.get("response", "")
    payload = {
        "conversation_id": conversation_id,
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    if result.get("downloads"):
        payload["downloads"] = result["downloads"]
    if result.get("chunks_sent"):
        payload["chunks_sent"] = result["chunks_sent"]
    if result.get("meta"):
        payload["meta"] = result["meta"]

    logger.info(f"/v1/chat/conversation [{adapter}] conversation_id={conversation_id}")
    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
