"""Hooshka Web Gateway agent/chat boundary controls.

This module separates human chat answers from executable/agentic output before
an unofficial Web-chat provider response leaves the Gateway. It deliberately
keeps only classification metadata in provider_meta and never exposes raw held
commands/code there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from core.providers import ChatCompletionRequest


HOOSHKA_CONTEXT_MARKERS = (
    "hooshka",
    "هوشکا",
    "cag",
    "controlled action gateway",
    "کنترل",
    "نقشه‌یار",
    "نقشه یار",
    "naghsheyar",
    "sotoon",
    "ستون",
    "tavana",
    "توانا",
    "command center",
    "اتاق فرمان",
)

HOOSHKA_GATEWAY_SYSTEM_PROMPT = """Gateway boundary instruction for Hooshka context:
- In this project, CAG means Hooshka Controlled Action Gateway. It is not Client Access Gateway.
- Do not invent project/service status. State uncertainty when no CAG evidence or provided data exists.
- Do not put shell commands, executable code blocks, terminal snippets, Copy/Download artifacts, or step-by-step agent execution commands in the final human chat answer.
- If execution is needed, describe it as an Action Plan / CAG candidate only. Actual execution must go through CAG and approval/evidence controls.
- Keep the human answer Persian, concise, and operational; never claim execution unless controlled evidence is present."""

COMMAND_LANGS = {"bash", "sh", "shell", "cmd", "bat", "powershell", "ps1", "pwsh", "terminal", "console"}
TEXTUAL_EXEC_LANGS = {"text", "plain", "plaintext"}

COMMAND_PREFIXES = (
    "git ", "python ", "python -m ", "py ", "pip ", "npm ", "node ", "dotnet ",
    "powershell", "pwsh", "cmd ", "curl ", "wget ", "invoke-webrequest", "invoke-restmethod",
    "docker ", "docker-compose ", "kubectl ", "ssh ", "scp ", "netsh ", "sc ", "reg ",
    "icacls ", "systemctl ", "journalctl ", "service ", "cat ", "tail ", "grep ", "sed ", "awk ",
    "chmod ", "chown ", "rm ", "rmdir", "del ", "erase ", "remove-item", "restart-computer",
    "set-service", "start-service", "stop-service", "restart-service", "mkdir ", "copy ", "move ",
    "cd ", "dir ", "ls ", ".\\", "./",
)

_COPY_ARTIFACTS = {"text", "copy", "download", "کپی", "دانلود"}

MENTIONED_COMMAND_WORDS = (
    "systemctl", "journalctl", "curl", "wget", "powershell", "pwsh", "cmd.exe", "netsh",
    "restart-computer", "remove-item", "invoke-webrequest", "invoke-restmethod", "docker", "kubectl",
    "ssh", "scp", "icacls", "reg.exe", "git status", "git log", "python -m",
)

_FENCE_RE = re.compile(r"```\s*([A-Za-z0-9_+.-]*)?\s*\n([\s\S]*?)```", re.MULTILINE)
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:\\")
_EXEC_PATH_RE = re.compile(r"(^|\s)(?:\.\\|\.\/|[A-Za-z]:\\)[^\s]+\.(?:ps1|cmd|bat|exe|sh|py|js|mjs|ts|tsx)\b", re.I)
_BAD_CAG_RE = re.compile(r"client\s+(?:access\s+)?gateway|client\s*[→\-]>?\s*(?:access\s*[→\-]>?\s*)?gateway\s*[→\-]>?\s*core", re.I)


@dataclass
class AgentBoundaryResult:
    safe_content: str
    hidden_executable_count: int = 0
    hidden_copy_artifact_count: int = 0
    hidden_hallucination_count: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.hidden_executable_count
            or self.hidden_copy_artifact_count
            or self.hidden_hallucination_count
        )

    def meta(self) -> dict[str, Any]:
        return {
            "active": True,
            "policy": "hooshka_wg_agent_boundary_v1",
            "delivery": "safe_chat_only",
            "canonical_cag": "Hooshka Controlled Action Gateway",
            "hidden_executable_count": self.hidden_executable_count,
            "hidden_copy_artifact_count": self.hidden_copy_artifact_count,
            "hidden_hallucination_count": self.hidden_hallucination_count,
            "raw_payload_omitted": True,
        }


def _message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return "" if content is None else str(content)


def boundary_is_active_for_request(request: ChatCompletionRequest | None) -> bool:
    if request is None:
        return False
    opts = request.provider_options or {}
    if opts.get("agent_boundary") is True or opts.get("hooshka_context") is True:
        return True
    haystack = "\n".join(_message_text(m) for m in (request.messages or []) if isinstance(m, dict)).lower()
    return any(marker in haystack for marker in HOOSHKA_CONTEXT_MARKERS)


def apply_request_context_boundary(request: ChatCompletionRequest) -> ChatCompletionRequest:
    if not boundary_is_active_for_request(request):
        return request
    messages = list(request.messages or [])
    already = any(
        isinstance(m, dict)
        and m.get("role") == "system"
        and "Hooshka Controlled Action Gateway" in _message_text(m)
        for m in messages
    )
    if not already:
        messages.insert(0, {"role": "system", "content": HOOSHKA_GATEWAY_SYSTEM_PROMPT})
    opts = dict(request.provider_options or {})
    opts["agent_boundary"] = True
    opts["hooshka_context"] = True
    request.messages = messages
    request.provider_options = opts
    return request


def _strip_markdown_prefix(line: str) -> str:
    t = (line or "").strip()
    t = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)", "", t)
    t = t.strip("` ")
    return t.strip()


def _is_copy_artifact(line: str) -> bool:
    t = _strip_markdown_prefix(line).lower()
    return t in _COPY_ARTIFACTS


def looks_executable(line: str) -> bool:
    t = _strip_markdown_prefix(line).lower()
    if not t:
        return False
    if t.startswith("#"):
        return False
    if any(t.startswith(prefix) for prefix in COMMAND_PREFIXES):
        return True
    if _EXEC_PATH_RE.search(t):
        return True
    if (" && " in t or " | " in t or "; " in t) and any(prefix.strip() in t for prefix in COMMAND_PREFIXES):
        return True
    # A bare Windows path such as D:\Code\... is useful documentation and should remain.
    if _WINDOWS_PATH_RE.match(t) and not re.search(r"\.(ps1|cmd|bat|exe|sh|py|js|mjs|ts|tsx)\b", t, re.I):
        return False
    return False


def _fence_is_agentic(lang: str, body: str) -> bool:
    low_lang = (lang or "").strip().lower()
    if low_lang in COMMAND_LANGS:
        return True
    body_lines = body.splitlines()
    if low_lang in TEXTUAL_EXEC_LANGS and any(looks_executable(x) or _is_copy_artifact(x) for x in body_lines):
        return True
    executable_lines = sum(1 for x in body_lines if looks_executable(x))
    copy_lines = sum(1 for x in body_lines if _is_copy_artifact(x))
    return executable_lines > 0 or copy_lines >= 2


def enforce_response_boundary(content: str | None) -> AgentBoundaryResult:
    text = (content or "").replace("\r\n", "\n")
    hidden_exec = 0
    hidden_copy = 0
    hidden_hallucination = 0

    def replace_fence(match: re.Match) -> str:
        nonlocal hidden_exec, hidden_copy
        lang = match.group(1) or ""
        body = match.group(2) or ""
        if _fence_is_agentic(lang, body):
            hidden_exec += 1
            hidden_copy += sum(1 for x in body.splitlines() if _is_copy_artifact(x))
            return "\n[یک قطعه اجرایی در مرز Hooshka WG متوقف شد و وارد پاسخ چت نشد.]\n"
        return match.group(0)

    text = _FENCE_RE.sub(replace_fence, text)

    safe_lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if _is_copy_artifact(line):
            hidden_copy += 1
            continue
        if _BAD_CAG_RE.search(line):
            hidden_hallucination += 1
            continue
        lower_line = line.lower()
        if any(word in lower_line for word in MENTIONED_COMMAND_WORDS):
            hidden_exec += 1
            continue
        if looks_executable(line):
            hidden_exec += 1
            continue
        safe_lines.append(line)

    safe = "\n".join(safe_lines)
    safe = re.sub(r"\n{3,}", "\n\n", safe).strip()
    notes: list[str] = []
    if hidden_hallucination:
        notes.append("برداشت نادرست از CAG در مرز Gateway حذف شد؛ در هوشکا، CAG یعنی Hooshka Controlled Action Gateway.")
    if hidden_exec:
        notes.append("دستور یا code اجرایی در مرز Gateway متوقف شد و باید از مسیر Action Plan / CAG بررسی شود.")
    if hidden_copy:
        notes.append("artifactهای نمایشی رابط کاربری از پاسخ چت حذف شدند.")
    if not safe:
        safe = "پاسخ مدل شامل محتوای اجرایی یا برداشت نادرست از CAG بود؛ محتوای خام به چت تحویل داده نشد. ادامه باید از مسیر Action Plan / CAG انجام شود."
    if notes:
        safe = safe + "\n\n" + "\n".join(f"> {n}" for n in notes)
    return AgentBoundaryResult(
        safe_content=safe,
        hidden_executable_count=hidden_exec,
        hidden_copy_artifact_count=hidden_copy,
        hidden_hallucination_count=hidden_hallucination,
        notes=notes,
    )
