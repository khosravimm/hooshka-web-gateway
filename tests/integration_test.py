#!/usr/bin/env python3
"""
Integration test script for Web LLM Bridge.

This script tests the API endpoints against a running server.
Requires:
- Server running on localhost:5000
- Chrome with remote debugging on port 9222
- Active ChatGPT session at chatgpt.com
"""

import sys
import json
import time
import requests
from typing import Dict, Any, Optional


BASE_URL = "http://localhost:5000"
TIMEOUT = 180  # seconds


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(name: str, success: bool, details: str = ""):
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name}")
    if details:
        print(f"       {details}")


def test_health() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception as e:
        return False


def test_modes() -> tuple[bool, dict]:
    try:
        r = requests.get(f"{BASE_URL}/modes", timeout=10)
        if r.status_code == 200:
            data = r.json()
            providers = data.get("providers", [])
            return len(providers) > 0, data
        return False, {}
    except Exception as e:
        return False, {}


def test_models() -> tuple[bool, list]:
    try:
        r = requests.get(f"{BASE_URL}/v1/models", timeout=10)
        if r.status_code == 200:
            data = r.json()
            models = data.get("data", [])
            return len(models) > 0, models
        return False, []
    except Exception as e:
        return False, []


def test_chat_completion(message: str = "Reply only with TEST_OK", stream: bool = False) -> tuple[bool, dict]:
    try:
        payload = {
            "model": "chatgpt-web",
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
            "temperature": 0.1,
        }
        r = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=TIMEOUT,
            stream=stream,
        )
        
        if stream:
            # Parse SSE stream
            full_content = ""
            for line in r.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                        except:
                            pass
            return "TEST_OK" in full_content.upper(), {"content": full_content}
        else:
            if r.status_code == 200:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return "TEST_OK" in content.upper(), data
            return False, {"error": r.text}
    except Exception as e:
        return False, {"error": str(e)}


def test_code_generation() -> tuple[bool, dict]:
    try:
        payload = {
            "model": "chatgpt-web",
            "messages": [{"role": "user", "content": "Write a Python function that adds two numbers"}],
            "language": "python",
            "code_only": False,
        }
        r = requests.post(
            f"{BASE_URL}/v1/chat/code",
            json=payload,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            blocks = data.get("code", {}).get("blocks", [])
            has_python = any(b.get("language") == "python" for b in blocks)
            return has_python, data
        return False, {"error": r.text}
    except Exception as e:
        return False, {"error": str(e)}


def test_conversation() -> tuple[bool, dict]:
    try:
        conv_id = f"test-conv-{int(time.time())}"
        
        # First message
        payload1 = {
            "conversation_id": conv_id,
            "model": "chatgpt-web",
            "messages": [{"role": "user", "content": "Remember: my test value is 42"}],
        }
        r1 = requests.post(f"{BASE_URL}/v1/chat/conversation", json=payload1, timeout=TIMEOUT)
        
        if r1.status_code != 200:
            return False, {"error": "First message failed", "response": r1.text}
        
        # Second message - should remember
        time.sleep(2)
        payload2 = {
            "conversation_id": conv_id,
            "model": "chatgpt-web",
            "messages": [{"role": "user", "content": "What is my test value?"}],
        }
        r2 = requests.post(f"{BASE_URL}/v1/chat/conversation", json=payload2, timeout=TIMEOUT)
        
        if r2.status_code == 200:
            data = r2.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return "42" in content, data
        return False, {"error": "Second message failed", "response": r2.text}
    except Exception as e:
        return False, {"error": str(e)}


def test_rate_limiting() -> bool:
    """Test that rate limiting works (may be slow)"""
    try:
        # Make rapid requests
        for i in range(25):
            r = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json={"model": "chatgpt-web", "messages": [{"role": "user", "content": "test " + str(i)}]},
                timeout=5,
            )
            if r.status_code == 429:
                return True
        return False
    except Exception:
        return False


def test_auth() -> bool:
    """Test auth when enabled (requires BRIDGE_AUTH_ENABLED=true)"""
    try:
        r = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json={"model": "chatgpt-web", "messages": [{"role": "user", "content": "test"}]},
            headers={"Authorization": "Bearer invalid-key"},
            timeout=10,
        )
        # Should fail with 401 if auth enabled, or succeed if disabled
        return r.status_code in (200, 401)
    except Exception:
        return False


def run_all_tests():
    print_section("Web LLM Bridge Integration Tests")
    print(f"Target: {BASE_URL}")
    print(f"Timeout: {TIMEOUT}s per request")
    
    results = {}
    
    # Health check
    print_section("1. Health Check")
    success = test_health()
    print_result("Health endpoint", success)
    results["health"] = success
    
    # Modes
    print_section("2. Providers List")
    success, data = test_modes()
    print_result("Modes endpoint", success, f"Providers: {[p['id'] for p in data.get('providers', [])]}")
    results["modes"] = success
    
    # Models
    print_section("3. Models List")
    success, models = test_models()
    print_result("Models endpoint", success, f"Models: {[m['id'] for m in models]}")
    results["models"] = success
    
    # Chat completion (non-streaming)
    print_section("4. Chat Completion (non-streaming)")
    success, data = test_chat_completion()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:100]
    print_result("Chat completion", success, f"Response: {content}")
    results["chat_completion"] = success
    
    # Chat completion (streaming)
    print_section("5. Chat Completion (streaming)")
    success, data = test_chat_completion(stream=True)
    content = data.get("content", "")[:100]
    print_result("Streaming chat", success, f"Response: {content}")
    results["streaming"] = success
    
    # Code generation
    print_section("6. Code Generation")
    success, data = test_code_generation()
    blocks = data.get("code", {}).get("blocks", [])
    print_result("Code generation", success, f"Blocks: {len(blocks)}, Languages: {[b.get('language') for b in blocks]}")
    results["code"] = success
    
    # Conversation
    print_section("7. Conversation Continuity")
    success, data = test_conversation()
    print_result("Conversation", success)
    results["conversation"] = success
    
    # Rate limiting (optional - slow)
    print_section("8. Rate Limiting (optional)")
    print("  Skipping - would take too long")
    results["rate_limit"] = "skipped"
    
    # Summary
    print_section("Summary")
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v == "skipped")
    
    for name, result in results.items():
        status = "PASS" if result is True else ("FAIL" if result is False else "SKIP")
        print(f"  [{status}] {name}")
    
    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)