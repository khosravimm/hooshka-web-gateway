import uuid
import logging
from flask import Blueprint, request, jsonify
from adapters.chatgpt_dom import dom_chat
from adapters.chatgpt_network import network_chat

logger = logging.getLogger(__name__)

api_bp = Blueprint("openai_compat", __name__)


@api_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    model = data.get("model", "chatgpt-web")
    stream = data.get("stream", False)
    file_path = data.get("file_path")
    file_paths = data.get("file_paths") or ([file_path] if file_path else [])
    long_text = data.get("long_text", True)

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
            result = network_chat(message, file_paths=file_paths, long_text=long_text)
            adapter = "network"
        else:
            result = dom_chat(message, file_paths=file_paths, long_text=long_text)
    except Exception as e:
        logger.error(f"Adapter error: {e}")
        return jsonify({"error": {"message": str(e), "type": "adapter_error"}}), 500

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    response_payload = {
        "id": completion_id,
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result.get("response", ""),
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
        response_payload["downloads"] = result["downloads"]
    if result.get("chunks_sent"):
        response_payload["chunks_sent"] = result["chunks_sent"]
    if result.get("meta"):
        response_payload["meta"] = result["meta"]

    logger.info(f"/v1/chat/completions [{adapter}] model={model} stream={stream}")
    return jsonify(response_payload)
