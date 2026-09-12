import json
import re
import uuid
from typing import Optional


def build_tool_instruction(tools: list[dict], tool_choice=None) -> str:
    definitions = []
    for tool in tools or []:
        fn = (tool or {}).get("function", {})
        if not fn.get("name"):
            continue
        definitions.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        })
    choice_rule = ""
    if tool_choice == "required":
        choice_rule = "A tool call is REQUIRED for this turn. Do not answer with prose.\n"
    elif isinstance(tool_choice, dict):
        forced_name = ((tool_choice.get("function") or {}).get("name"))
        if forced_name:
            choice_rule = (
                f"You MUST call the function named {forced_name!r} for this turn. "
                "Do not answer with prose.\n"
            )

    return (
        "You are operating behind an external tool gateway. You cannot execute these tools yourself.\n"
        "You MUST NOT guess, simulate, fabricate, or claim a tool result before the gateway returns it.\n"
        "If the user's request requires local-machine state, files, shell commands, current external data, "
        "or explicitly asks you to use a listed tool, you MUST emit a tool call.\n"
        + choice_rule
        + "Available tools/functions:\n"
        + json.dumps(definitions, ensure_ascii=False, indent=2)
        + "\n\nYour response is parsed by a machine. ALWAYS reply with exactly one valid JSON object.\n"
          "If a tool is required, use this exact envelope:\n"
          '{"tool_calls":[{"name":"<function_name>","arguments":{}}]}\n'
          "If no tool is required and you can answer now, use this exact envelope:\n"
          '{"final":"<your complete answer>"}\n'
          "Do not add prose, markdown, explanations, or an imagined result outside the JSON object.\n"
          "After the gateway sends a [TOOL RESULT ...] message, use that returned data to answer the user. "
          "If another tool is still required, emit another tool call instead."
    )


def serialize_messages(messages: list[dict], tools: Optional[list[dict]] = None, tool_choice=None) -> str:
    if tool_choice == "none":
        tools = None
    parts = []
    if tools:
        parts.append("[SYSTEM TOOL INSTRUCTIONS]\n" + build_tool_instruction(tools, tool_choice=tool_choice))
    for msg in messages or []:
        role = str(msg.get("role", "user")).upper()
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") in ("text", "input_text")
            )
        content = "" if content is None else str(content)
        if msg.get("tool_calls"):
            calls = []
            for tc in msg["tool_calls"]:
                fn = (tc or {}).get("function", {})
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = raw_args
                calls.append({"name": fn.get("name"), "arguments": args, "id": tc.get("id")})
            content += "\n" + json.dumps({"tool_calls": calls}, ensure_ascii=False)
        if role == "TOOL":
            call_id = msg.get("tool_call_id", "")
            name = msg.get("name", "")
            parts.append(f"[TOOL RESULT id={call_id} name={name}]\n{content}")
        else:
            parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


def _first_json_object(text: str):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1].strip(), (start, idx + 1)
    return None


def _json_loads_tolerant(raw: str):
    try:
        return json.loads(raw)
    except Exception as first_error:
        # Web chat models often emit Windows paths inside JSON strings with
        # raw backslashes, e.g. {"filePath":"D:\\Code\\repo\\README.md"}
        # after DOM extraction this may become JSON-invalid as D:\Code.
        # Escape only backslashes that are not valid JSON escapes.
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        try:
            return json.loads(fixed)
        except Exception:
            raise first_error


def _normalize_tool_name_and_args(name: str, args):
    # Do not globally rename tools here. API clients may intentionally expose
    # read_file instead of Kilo's read. Only normalize argument aliases that
    # Web-chat models commonly emit.
    if isinstance(args, dict):
        args = dict(args)
        if "filePath" not in args:
            for key in ("file_path", "filepath", "path", "file"):
                if key in args:
                    args["filePath"] = args[key]
                    break
        if "oldString" not in args:
            for key in ("old_string", "old", "oldText", "old_text"):
                if key in args:
                    args["oldString"] = args[key]
                    break
        if "newString" not in args:
            for key in ("new_string", "new", "newText", "new_text"):
                if key in args:
                    args["newString"] = args[key]
                    break
        if "command" not in args:
            for key in ("cmd", "shell_command", "powershell"):
                if key in args:
                    args["command"] = args[key]
                    break
        if "pattern" not in args:
            for key in ("query", "regex", "search"):
                if key in args:
                    args["pattern"] = args[key]
                    break
    return name, args


def _call(name: str, arguments) -> dict:
    if not isinstance(arguments, str):
        name, arguments = _normalize_tool_name_and_args(name, arguments)
    if isinstance(arguments, str):
        try:
            parsed_arguments = _json_loads_tolerant(arguments)
            name, parsed_arguments = _normalize_tool_name_and_args(name, parsed_arguments)
            args_str = json.dumps(parsed_arguments if parsed_arguments is not None else {}, ensure_ascii=False)
        except Exception:
            args_str = arguments
    else:
        args_str = json.dumps(arguments if arguments is not None else {}, ensure_ascii=False)
    return {
        "id": f"call_{uuid.uuid4().hex[:8]}",
        "type": "function",
        "function": {"name": name, "arguments": args_str},
    }


def parse_tool_calls(text: str):
    if not text:
        return text, None

    if "DSML" in text and "invoke" in text:
        dsml = text.replace("｜", "|")
        dsml = re.sub(r'\\(?=</\s*\|\s*\|\s*DSML)', '', dsml, flags=re.IGNORECASE)
        inv = re.compile(
            r'<\s*\|\s*\|\s*DSML\s*\|\s*\|\s*invoke\s+name="([^"]+)"\s*>\s*'
            r'([\s\S]*?)'
            r'<\s*/\s*\|\s*\|\s*DSML\s*\|\s*\|\s*invoke\s*>', re.IGNORECASE)
        par = re.compile(
            r'<\s*\|\s*\|\s*DSML\s*\|\s*\|\s*parameter\s+name="([^"]+)"(?:\s+string="([^"]+)")?\s*>\s*'
            r'([\s\S]*?)'
            r'<\s*/\s*\|\s*\|\s*DSML\s*\|\s*\|\s*parameter\s*>', re.IGNORECASE)
        calls, spans = [], []
        for match in inv.finditer(dsml):
            args = {}
            for pm in par.finditer(match.group(2)):
                raw = re.sub(r'\\([_:])', r'\1', pm.group(3).strip())
                if (pm.group(2) or "").lower() == "true":
                    value = raw
                else:
                    try:
                        value = json.loads(raw)
                    except Exception:
                        value = raw
                args[pm.group(1).strip()] = value
            calls.append(_call(match.group(1).strip(), args))
            spans.append(match.span())
        if calls:
            cleaned = dsml
            for start, end in reversed(spans):
                cleaned = cleaned[:start] + cleaned[end:]
            cleaned = re.sub(r'<\s*/?\s*\|\s*\|\s*DSML\s*\|\s*\|\s*calls\s*>', '', cleaned, flags=re.IGNORECASE).strip()
            return cleaned or None, calls

    block = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
    span = None
    raw = None
    if block:
        raw, span = block.group(1).strip(), block.span()
    else:
        found = _first_json_object(text)
        if found:
            raw, span = found
    if not raw:
        return text, None
    try:
        data = _json_loads_tolerant(raw)
    except Exception:
        return text, None
    if not isinstance(data, dict):
        return text, None
    if isinstance(data.get("tool_calls"), list):
        items = data["tool_calls"]
    elif data.get("name") and ("arguments" in data or "parameters" in data):
        items = [data]
    else:
        return text, None
    calls = []
    for item in items:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = fn.get("name") if isinstance(fn, dict) else None
        if not name:
            continue
        args = fn.get("arguments", fn.get("parameters", {}))
        calls.append(_call(name, args))
    if not calls:
        return text, None
    cleaned = (text[:span[0]] + text[span[1]:]).strip() if span else ""
    return cleaned or None, calls


def parse_tool_envelope(text: str):
    """Parse the gateway's strict tool/final JSON protocol.

    Returns ``(content, tool_calls, valid_protocol)``. DSML remains accepted
    for compatibility with clients/models that emit it despite the JSON
    instruction.
    """
    content, calls = parse_tool_calls(text)
    if calls:
        return content, calls, True

    if not text:
        return text, None, False

    block = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
    raw = block.group(1).strip() if block else None
    if raw is None:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            raw = stripped
    if raw:
        try:
            data = _json_loads_tolerant(raw)
        except Exception:
            data = None
        if isinstance(data, dict) and "final" in data:
            final = data.get("final")
            if final is None:
                final = ""
            if not isinstance(final, str):
                final = json.dumps(final, ensure_ascii=False)
            return final, None, True

    return text, None, False


_TOOL_REFUSAL_PATTERNS = [
    re.compile(r"\b(can(?:no|')t|could\s+not|unable\s+to|won'?t)\b[^.]{0,64}\b(access|use|run|execute|call|reach)\b[^.]{0,64}\b(tool|tools|shell|workspace|command|file|files|filesystem|directory)\b", re.I),
    re.compile(r"\b(tool|tools|shell|workspace|file|files|filesystem|command)\b[^.]{0,64}\b(not\s+available|unavailable|not\s+accessible|no\s+access|disabled|restricted|blocked)\b", re.I),
    re.compile(r"\bdon'?t\s+have\s+access\b", re.I),
    re.compile(r"در\s*دسترس\s*نیست"),
    re.compile(r"دسترسی\s*ندار"),
    re.compile(r"امکان\s*(اجرا|اجرای|دسترسی)[^.]{0,100}(وجود\s*ندارد|نیست)"),
    re.compile(r"نمی[‌\s]?توان(م|ید|ست)?[^.]{0,64}(اجرا|دسترسی|استفاده|فراخوان)"),
]

_SANDBOX_MARKERS = (
    "code interpreter",
    "python sandbox",
    "sandbox",
    "internal tool",
    "built-in tool",
    "workspace shell",
)


def strong_auto_tool_signal(
    response_text: str,
    tools: Optional[list[dict]],
    latest_user_text: str = "",
) -> Optional[str]:
    """Return a bounded reason for one corrective auto-tool review.

    This intentionally does *not* retry every text-with-no-tool response. AWA's
    live experience showed broad retry converts legitimate final answers into
    spurious tool calls. Only strong evidence triggers a review.
    """
    tool_names = []
    for tool in tools or []:
        name = (((tool or {}).get("function") or {}).get("name") or "").strip()
        if name:
            tool_names.append(name)

    response_lower = (response_text or "").lower()
    user_lower = (latest_user_text or "").lower()

    # Explicit user request naming an offered tool is the strongest request-side
    # signal and covers agent clients that say "use the bash tool" while leaving
    # ordinary tool-aware chat turns untouched.
    for name in tool_names:
        token = name.lower()
        if token and token in user_lower and re.search(r"\b(use|run|call|invoke|execute|اجرا|استفاده|فراخوان)\b", user_lower):
            return f"explicit_user_tool_request:{name}"

    for name in tool_names:
        if name.lower() in response_lower:
            return f"response_mentions_tool:{name}"

    for marker in _SANDBOX_MARKERS:
        if marker in response_lower:
            return f"sandbox_or_internal_marker:{marker}"

    if any(pattern.search(response_text or "") for pattern in _TOOL_REFUSAL_PATTERNS):
        return "tool_refusal"

    return None
