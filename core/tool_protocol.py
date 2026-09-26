import json
import re
import uuid
from typing import Optional

from core.unicode_norm import normalize_unicode


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
        + "\n\nYour response is parsed by a machine. ALWAYS reply with exactly one valid JSON object inside one fenced `json` code block.\n"
          "The code block is required because the Web Chat renderer can otherwise alter underscores, backslashes, and quotes inside tool arguments.\n"
          "Reliability rules: emit AT MOST ONE tool call per response; never batch multiple calls.\n"
          "Every string argument MUST be valid JSON. Escape internal double quotes, backslashes, control characters, and newlines.\n"
          "For write/edit/source-code arguments, keep the entire content inside one correctly escaped JSON string; never place raw triple quotes outside JSON escaping.\n"
          "If a tool is required, use this envelope with exactly one item in `tool_calls`:\n"
          '```json\n{"tool_calls":[{"name":"<function_name>","arguments":{}}]}\n```\n'
          "If no tool is required and you can answer now, use this exact envelope:\n"
          '```json\n{"final":"<your complete answer>"}\n```\n'
          "Do not add prose, explanations, or an imagined result outside the single fenced JSON block.\n"
          "After the gateway sends a [TOOL RESULT ...] message, use that returned data to answer the user. "
          "If another tool is still required, emit exactly one next tool call instead."
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
            envelope = json.dumps({"tool_calls": calls}, ensure_ascii=False)
            if content.strip():
                content = content.rstrip() + "\n"
            content += "```json\n" + envelope + "\n```"
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


def _repair_arguments_json_string(raw: str) -> str:
    """Repair a narrow Web-chat defect: arguments as an unescaped JSON string.

    Example from browser DOM:
    {"tool_calls":[{"function":{"arguments":"{"marker":"X"}"}}]}

    The repair is intentionally scoped to the value of an `arguments` field.
    It converts that quoted inner object to a normal JSON object and leaves all
    other fields untouched.
    """
    key_pattern = re.compile(r'"arguments"\s*:\s*"(?=\s*\{)')
    out = []
    pos = 0
    for match in key_pattern.finditer(raw):
        quote_start = match.end() - 1
        inner_start = quote_start + 1
        idx = inner_start
        depth = 0
        in_string = False
        escape = False
        end_obj = None
        while idx < len(raw):
            ch = raw[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_obj = idx
                        break
            idx += 1
        if end_obj is None:
            continue
        close_quote = end_obj + 1
        while close_quote < len(raw) and raw[close_quote].isspace():
            close_quote += 1
        if close_quote >= len(raw) or raw[close_quote] != '"':
            continue
        inner = raw[inner_start:end_obj + 1]
        out.append(raw[pos:quote_start])
        out.append(inner)
        pos = close_quote + 1
    if not out:
        return raw
    out.append(raw[pos:])
    return "".join(out)


def _repair_deescaped_command_string(raw: str) -> str:
    """Repair a de-escaped JSON string specifically for a shell `command` field.

    Browser DOM extraction can remove the JSON escaping from a model response,
    producing a shape such as::

        {"command":"New-Item -Path "src\\taskflow", "tests" -Force", "description":"..."}

    The command terminator is identified only when the quote is followed by a
    JSON sibling key (`, "name":`) or by the enclosing object close. Quotes
    inside the command are re-escaped, and backslashes are re-escaped so a
    Windows path such as ``src\\taskflow`` is not decoded as a tab escape.
    The repaired document is still required to pass normal ``json.loads``.
    """
    key_re = re.compile(r'"command"\s*:\s*"')
    pos = 0
    chunks: list[str] = []
    changed = False
    while True:
        match = key_re.search(raw, pos)
        if not match:
            break
        start = match.end()
        idx = start
        end = None
        while idx < len(raw):
            if raw[idx] != '"':
                idx += 1
                continue
            # A real JSON string terminator is followed by either a sibling
            # property or the closing brace of the arguments object.
            tail = raw[idx + 1:]
            if re.match(r'\s*,\s*"[A-Za-z_][A-Za-z0-9_]*"\s*:', tail) or re.match(r'\s*}', tail):
                end = idx
                break
            idx += 1
        if end is None:
            break
        body = raw[start:end]
        # DOM de-escaping removes both path escaping and embedded-quote
        # escaping. Restore them only inside the bounded command value.
        repaired_body = body.replace('\\', '\\\\').replace('"', '\\"')
        chunks.append(raw[pos:start])
        chunks.append(repaired_body)
        pos = end
        changed = changed or repaired_body != body
        # Continue after the closing quote; it is copied by the next slice.
        key_next = key_re.search(raw, end + 1)
        if key_next is None:
            break
    if not chunks:
        return raw
    chunks.append(raw[pos:])
    return ''.join(chunks) if changed else raw


def _repair_truncated_json_closers(raw: str, max_missing: int = 4) -> str:
    """Append only missing terminal JSON closers for a bounded truncation.

    The repair is accepted only when all observed closing delimiters match, the
    payload does not end inside a JSON string, and at most ``max_missing``
    terminal ``]``/``}`` characters are absent.  It never invents keys, values,
    commas, quotes, or string contents.
    """
    stack: list[str] = []
    in_string = False
    escape = False
    pairs = {"}": "{", "]": "["}
    for ch in raw:
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
        elif ch in "[{":
            stack.append(ch)
        elif ch in "}]":
            if not stack or stack[-1] != pairs[ch]:
                return raw
            stack.pop()
    if in_string or not stack or len(stack) > max_missing:
        return raw
    closers = ''.join('}' if ch == '{' else ']' for ch in reversed(stack))
    return raw + closers


def _repair_missing_container_closers(raw: str, max_repairs: int = 4) -> str:
    """Insert only structurally implied missing ``}``/``]`` delimiters.

    This is a bounded repair for Web-chat tool envelopes such as an object item
    whose closing ``}`` was dropped immediately before the surrounding ``]``.
    It never repairs strings, commas, keys, or values. Any unterminated string,
    extra closer, or repair count above the bound fails closed by returning the
    original input.
    """
    stack: list[str] = []
    out: list[str] = []
    in_string = False
    escape = False
    repairs = 0
    opener_for = {"}": "{", "]": "["}
    closer_for = {"{": "}", "[": "]"}

    for ch in raw:
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            out.append(ch)
            in_string = True
            continue
        if ch in "[{":
            stack.append(ch)
            out.append(ch)
            continue
        if ch in "}]":
            wanted = opener_for[ch]
            while stack and stack[-1] != wanted:
                if repairs >= max_repairs:
                    return raw
                out.append(closer_for[stack.pop()])
                repairs += 1
            if not stack:
                return raw
            stack.pop()
            out.append(ch)
            continue
        out.append(ch)

    if in_string:
        return raw
    while stack:
        if repairs >= max_repairs:
            return raw
        out.append(closer_for[stack.pop()])
        repairs += 1
    return "".join(out) if repairs else raw


def _json_loads_tolerant(raw: str):
    # A model may encode a Windows drive root as \"D:\\"; the trailing
    # backslash then escapes the JSON quote. Canonicalize only this narrow
    # drive-root form to a Windows-compatible forward-slash path.
    raw = re.sub(r'([A-Za-z]):\\(?=\"[,}])', r'\1:/', raw)
    try:
        return json.loads(raw)
    except Exception as first_error:
        truncated_repaired = _repair_truncated_json_closers(raw)
        if truncated_repaired != raw:
            try:
                return json.loads(truncated_repaired)
            except Exception:
                pass
        container_repaired = _repair_missing_container_closers(raw)
        if container_repaired != raw:
            try:
                return json.loads(container_repaired)
            except Exception:
                pass
        # A common coding-agent variant is a de-escaped shell command whose
        # embedded quotes and Windows path separators make the surrounding JSON
        # invalid. Repair only the bounded `command` field, then require strict
        # JSON parsing.
        command_repaired = _repair_deescaped_command_string(raw)
        if command_repaired != raw:
            try:
                return json.loads(command_repaired)
            except Exception:
                pass
        # Some Web-chat DOM surfaces de-escape the JSON string carried in an
        # `arguments` field, yielding e.g.:
        # {"tool_calls":[{"function":{"arguments":"{"marker":"X"}"}}]}
        # Repair only that bounded field shape, then require normal json.loads
        # to succeed. This keeps the recovery fail-closed.
        arguments_repaired = _repair_arguments_json_string(raw)
        if arguments_repaired != raw:
            try:
                return json.loads(arguments_repaired)
            except Exception:
                pass
        # Web chat models often emit Windows paths inside JSON strings with
        # raw backslashes, e.g. {"filePath":"D:\\Code\\repo\\README.md"}
        # after DOM extraction this may become JSON-invalid as D:\Code.
        # Escape only backslashes that are not valid JSON escapes.
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        try:
            return json.loads(fixed)
        except Exception:
            repaired = _repair_unescaped_string_quotes(fixed)
            try:
                return json.loads(repaired)
            except Exception:
                raise first_error


def _repair_unescaped_string_quotes(raw: str) -> str:
    """Repair unescaped quotes inside Web-chat JSON string values.

    The scanner tracks whether the current JSON string is an object key or a
    value. A quote followed by ``:`` closes a key, but the same shape inside a
    value (for example Python source ``"id": value``) is escaped as literal
    content. Value strings close only at a structurally valid value boundary.
    The repaired payload must still pass ``json.loads``; no code is evaluated.
    """
    out: list[str] = []
    in_string = False
    escape = False
    string_kind = "value"
    containers: list[str] = []
    length = len(raw)

    def previous_significant(index: int) -> str:
        j = index - 1
        while j >= 0 and raw[j].isspace():
            j -= 1
        return raw[j] if j >= 0 else ""

    def next_significant(index: int) -> tuple[str, int]:
        j = index + 1
        while j < length and raw[j].isspace():
            j += 1
        return (raw[j] if j < length else "", j)

    for idx, ch in enumerate(raw):
        if not in_string:
            if ch == '"':
                prev = previous_significant(idx)
                top = containers[-1] if containers else ""
                string_kind = "key" if top == "{" and prev in {"{", ","} else "value"
                out.append(ch)
                in_string = True
                escape = False
                continue
            out.append(ch)
            if ch in "[{":
                containers.append(ch)
            elif ch == "}" and containers and containers[-1] == "{":
                containers.pop()
            elif ch == "]" and containers and containers[-1] == "[":
                containers.pop()
            continue

        if escape:
            out.append(ch)
            escape = False
            continue

        if ch == "\\":
            out.append(ch)
            escape = True
            continue

        if ch != '"':
            out.append(ch)
            continue

        next_ch, next_idx = next_significant(idx)

        if string_kind == "key":
            if next_ch == ":":
                out.append(ch)
                in_string = False
            else:
                out.append('\\"')
            continue

        # JSON value string. A colon cannot terminate a value string; this is
        # commonly source code such as {"id": value} embedded in tool content.
        if next_ch == "":
            out.append(ch)
            in_string = False
            continue

        if next_ch in {"}", "]"}:
            # A brace/bracket immediately after a quote may belong to source
            # code embedded in a tool string. Treat it as a real JSON value
            # terminator only when the character after that delimiter also
            # continues/finishes JSON structure rather than returning to text.
            after_idx = next_idx + 1
            while after_idx < length and raw[after_idx].isspace():
                after_idx += 1
            after = raw[after_idx] if after_idx < length else ""
            if after in {",", "}", "]"} or after == "":
                out.append(ch)
                in_string = False
            else:
                out.append('\"')
            continue

        if next_ch == ",":
            top = containers[-1] if containers else ""
            if top == "{":
                tail = raw[next_idx + 1:]
                # In an object, a real value terminator must be followed by a
                # JSON key. Shell/source text like "a", "b" is not a key pair.
                if re.match(r'\s*"[^"\r\n]+"\s*:', tail):
                    out.append(ch)
                    in_string = False
                else:
                    out.append('\\"')
            else:
                # Array values may legitimately be followed by another value.
                out.append(ch)
                in_string = False
            continue

        out.append('\\"')

    return "".join(out)


def _repair_path_control_chars(value: str) -> str:
    """Recover Windows path separators swallowed by JSON control escapes.

    Web-chat models sometimes emit a single backslash in JSON paths, so a
    segment like ``\\taskflow`` is decoded as a tab plus ``askflow``. Windows
    paths cannot contain ASCII control characters 0x00-0x1F, therefore these
    decoded controls are unambiguous transport corruption for path-like tool
    arguments and can be restored to their textual backslash escape.
    """
    if not isinstance(value, str):
        return value
    mapping = {
        chr(9): r"\t",
        chr(10): r"\n",
        chr(13): r"\r",
        chr(8): r"\b",
        chr(12): r"\f",
    }
    for control, escaped in mapping.items():
        value = value.replace(control, escaped)
    return value


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
        for key in ("filePath", "file_path", "filepath", "path", "file", "workdir", "cwd"):
            if isinstance(args.get(key), str):
                args[key] = _repair_path_control_chars(args[key])
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
            compact = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,;]+)\s*", arguments)
            if compact:
                parsed_arguments = {compact.group(1): compact.group(2).strip()}
                name, parsed_arguments = _normalize_tool_name_and_args(name, parsed_arguments)
                args_str = json.dumps(parsed_arguments, ensure_ascii=False)
            else:
                args_str = arguments
    else:
        args_str = json.dumps(arguments if arguments is not None else {}, ensure_ascii=False)
    return {
        "id": f"call_{uuid.uuid4().hex[:8]}",
        "type": "function",
        "function": {"name": name, "arguments": args_str},
    }



def _parse_xmlish_tool_calls(text: str):
    """Parse Web-chat XML-ish tool calls such as explicit tool_call wrappers."""
    if "tool_call" not in text:
        return None
    pattern = re.compile(r'<\s*tool_call\b[^>]*>([\s\S]*?)<\s*/\s*tool_call\s*>', re.IGNORECASE)
    calls = []
    spans = []
    for match in pattern.finditer(text):
        inner = match.group(1).strip()
        if not inner:
            continue
        if inner.startswith("{"):
            try:
                data = _json_loads_tolerant(inner)
            except Exception:
                data = None
            items = []
            if isinstance(data, dict) and isinstance(data.get("tool_calls"), list):
                items = data["tool_calls"]
            elif isinstance(data, dict) and data.get("name") and ("arguments" in data or "parameters" in data):
                items = [data]
            for item in items:
                fn = item.get("function") if isinstance(item, dict) and isinstance(item.get("function"), dict) else item
                name = fn.get("name") if isinstance(fn, dict) else None
                if not name:
                    continue
                args = fn.get("arguments", fn.get("parameters", {}))
                calls.append(_call(str(name).strip(), args))
            if items:
                spans.append(match.span())
                continue
        first_tag = inner.find("<")
        name = (inner[:first_tag] if first_tag >= 0 else inner).strip().strip(':=- ')
        if not name or re.search(r'\s', name):
            continue
        args = {}
        pair_re = re.compile(
            r'<\s*arg_key\s*>\s*([\s\S]*?)\s*<\s*/\s*arg_key\s*>\s*'
            r'<\s*arg_value\s*>\s*([\s\S]*?)\s*<\s*/\s*arg_value\s*>',
            re.IGNORECASE,
        )
        for pm in pair_re.finditer(inner):
            key = re.sub(r'\s+', '', pm.group(1).strip())
            if not key:
                continue
            args[key] = pm.group(2).strip()
        if not args:
            continue
        calls.append(_call(name, args))
        spans.append(match.span())
    if not calls:
        return None
    cleaned = text
    for start, end in reversed(spans):
        cleaned = cleaned[:start] + cleaned[end:]
    return cleaned.strip() or None, calls

def parse_tool_calls(text: str):
    if not text:
        return text, None
    text = normalize_unicode(text)
    # Repair malformed Windows drive-root JSON before structural scanning;
    # otherwise the trailing backslash makes the closing quote look escaped.
    text = re.sub(r'([A-Za-z]):\\(?=\"[,}])', r'\1:/', text)

    if "DSML" in text and "invoke" in text:
        dsml = text.replace("\uff5c", "|")
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

    xmlish = _parse_xmlish_tool_calls(text)
    if xmlish:
        return xmlish

    block = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
    span = None
    raw = None
    if block:
        raw, span = block.group(1).strip(), block.span()
    else:
        found = _first_json_object(text)
        if found:
            raw, span = found
        else:
            # A Web-chat response may be truncated only at the terminal outer
            # delimiters. In addition, rendered fenced-code surfaces can expose
            # small UI labels (json/Copy/Download) before the actual envelope.
            # Accept only that known renderer chrome; arbitrary prose before a
            # tool envelope remains fail-closed.
            stripped = text.strip()
            candidate = stripped
            candidate_offset = text.find(stripped)
            tool_pos = stripped.find('{"tool_calls"')
            if tool_pos > 0:
                prefix_lines = [line.strip().lower() for line in stripped[:tool_pos].splitlines() if line.strip()]
                if prefix_lines and all(line in {"json", "copy", "download"} for line in prefix_lines):
                    candidate = stripped[tool_pos:]
                    candidate_offset += tool_pos
            if candidate.startswith("{") and "\"tool_calls\"" in candidate[:160]:
                raw, span = candidate, (candidate_offset, candidate_offset + len(candidate))
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
    if cleaned:
        chrome_lines = [line.strip().lower() for line in cleaned.splitlines() if line.strip()]
        if chrome_lines and all(line in {"json", "copy", "download"} for line in chrome_lines):
            cleaned = ""
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
    re.compile(r"\u062f\u0631\s*\u062f\u0633\u062a\u0631\u0633\s*\u0646\u06cc\u0633\u062a"),
    re.compile(r"\u062f\u0633\u062a\u0631\u0633\u06cc\s*\u0646\u062f\u0627\u0631"),
    re.compile(r"\u0627\u0645\u06a9\u0627\u0646\s*(\u0627\u062c\u0631\u0627|\u0627\u062c\u0631\u0627\u06cc|\u062f\u0633\u062a\u0631\u0633\u06cc)[^.]{0,100}(\u0648\u062c\u0648\u062f\s*\u0646\u062f\u0627\u0631\u062f|\u0646\u06cc\u0633\u062a)"),
    re.compile(r"\u0646\u0645\u06cc[\u200c\s]?\u062a\u0648\u0627\u0646(\u0645|\u06cc\u062f|\u0633\u062a)?[^.]{0,64}(\u0627\u062c\u0631\u0627|\u062f\u0633\u062a\u0631\u0633\u06cc|\u0627\u0633\u062a\u0641\u0627\u062f\u0647|\u0641\u0631\u0627\u062e\u0648\u0627\u0646)"),
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
        if token and token in user_lower and re.search(r"\b(use|run|call|invoke|execute|\u0627\u062c\u0631\u0627|\u0627\u0633\u062a\u0641\u0627\u062f\u0647|\u0641\u0631\u0627\u062e\u0648\u0627\u0646)\b", user_lower):
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
