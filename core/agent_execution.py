from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as ToolTimeoutError
from dataclasses import dataclass
import hashlib
import json
import time


@dataclass(frozen=True)
class AgentLoopPolicy:
    max_steps: int = 6
    per_tool_timeout_seconds: float = 10.0
    max_result_chars: int = 50000
    duplicate_call_limit: int = 1
    max_loop_seconds: float = 180.0

    @classmethod
    def from_config(cls, config: dict | None) -> "AgentLoopPolicy":
        cfg = config or {}
        return cls(
            max_steps=max(1, min(int(cfg.get("max_steps", 6)), 20)),
            per_tool_timeout_seconds=max(0.1, min(float(cfg.get("per_tool_timeout_seconds", 10)), 60.0)),
            max_result_chars=max(1000, min(int(cfg.get("max_result_chars", 50000)), 200000)),
            duplicate_call_limit=max(1, min(int(cfg.get("duplicate_call_limit", 1)), 5)),
            max_loop_seconds=max(5.0, min(float(cfg.get("max_loop_seconds", 180)), 600.0)),
        )


def tool_call_fingerprint(name: str, arguments) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw": arguments}
    canonical = json.dumps(arguments or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{name}:{canonical}".encode("utf-8")).hexdigest()


def _bounded_result(result, max_chars: int) -> tuple[str, bool]:
    raw = json.dumps(result, ensure_ascii=False, default=str)
    if len(raw) <= max_chars:
        return raw, False
    wrapper = {
        "truncated": True,
        "original_chars": len(raw),
        "preview": raw[:max_chars],
    }
    return json.dumps(wrapper, ensure_ascii=False), True


def execute_tool_call(registry, call: dict, policy: AgentLoopPolicy, seen: dict[str, int], step: int):
    fn = call.get("function") or {}
    name = str(fn.get("name") or "")
    raw_args = fn.get("arguments") or {}
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}
    else:
        args = dict(raw_args)
    fingerprint = tool_call_fingerprint(name, args)
    seen[fingerprint] = seen.get(fingerprint, 0) + 1
    duplicate = seen[fingerprint] > policy.duplicate_call_limit
    started = time.monotonic()
    status = "ok"
    error = None
    result = None

    if duplicate:
        status = "duplicate_blocked"
        error = "Duplicate tool call blocked by agent loop policy"
        result = {"error": error, "tool": name}
    else:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hwg-agent-tool")
        future = pool.submit(registry.execute, name, args)
        try:
            result = future.result(timeout=policy.per_tool_timeout_seconds)
        except ToolTimeoutError:
            future.cancel()
            status = "timeout"
            error = f"Tool exceeded {policy.per_tool_timeout_seconds:g}s timeout"
            result = {"error": error, "tool": name}
        except Exception as exc:
            status = "error"
            error = str(exc)
            result = {"error": error, "tool": name}
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    content, truncated = _bounded_result(result, policy.max_result_chars)
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    message = {
        "role": "tool",
        "tool_call_id": call.get("id"),
        "name": name,
        "content": content,
    }
    descriptor = registry.describe(name) if hasattr(registry, "describe") else None
    risk_class = (descriptor or {}).get("risk_class", "READ_ONLY")
    authorization_mode = (descriptor or {}).get("authorization_mode", "none")
    evidence = {
        "step": step,
        "tool": name,
        "source": (descriptor or {}).get("source", "local"),
        "risk_class": risk_class,
        "execution_state": status,
        "duration_ms": duration_ms,
        "truncated": truncated,
        "authorization_state": "not_required_read_only" if authorization_mode == "none" else authorization_mode,
        "input_summary": args,
    }
    if error:
        evidence["error"] = error[:500]
    return message, evidence, duplicate


def remaining_loop_seconds(started: float, policy: AgentLoopPolicy) -> float:
    return max(0.0, policy.max_loop_seconds - (time.monotonic() - started))


def summarize_terminal_state(state: str, steps: int, evidence: list[dict], started: float) -> dict:
    return {
        "state": state,
        "steps": steps,
        "tool_executions": len(evidence),
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }
