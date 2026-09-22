"""Bounded secret-leakage scanner for HWG release evidence."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = [ROOT / "config.yaml", ROOT / "logs", ROOT / ".runtime-dev" / "ng-store", ROOT / "docs" / "evidence"]
TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".log", ".md", ".txt"}

HIGH_RISK_PATTERNS = [
    ("bearer_token", re.compile(r"Bearer\s+(?!\[REDACTED\])([A-Za-z0-9._~+/-]{12,})", re.I)),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
]
SENSITIVE_KEY = re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret|cookie)")
KEY_VALUE = re.compile(r"^\s*[\"']?([A-Za-z_][A-Za-z0-9_.-]{0,79})[\"']?\s*[:=]\s*(.+?)\s*$")
SAFE_VALUES = {"", "{}", "[]", "null", "none", "false", "true", "[redacted]", "\"[redacted]\"", "'[redacted]'"}


def scan_text(text: str, source: str = "<memory>") -> list[dict]:
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, pattern in HIGH_RISK_PATTERNS:
            if pattern.search(line):
                findings.append({"source": source, "line": lineno, "kind": kind})
        m = KEY_VALUE.match(line)
        if not m:
            continue
        key, raw = m.group(1).strip(), m.group(2).strip().rstrip(',')
        value = raw.strip().strip('"').strip("'")
        if not SENSITIVE_KEY.search(key):
            continue
        if raw.lower() in SAFE_VALUES or value.lower() in SAFE_VALUES:
            continue
        if value.startswith("sha256:") or value.startswith("${") or value.startswith("env:"):
            continue
        findings.append({"source": source, "line": lineno, "kind": "sensitive_value", "key": key})
    return findings


def iter_files():
    for entry in SCOPE:
        if entry.is_file():
            yield entry
        elif entry.is_dir():
            for path in entry.rglob('*'):
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                    yield path


def main() -> int:
    findings = []
    scanned = 0
    for path in iter_files():
        scanned += 1
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        findings.extend(scan_text(text, str(path.relative_to(ROOT))))
    print(f"scanned_files={scanned}")
    print(f"findings={len(findings)}")
    for item in findings[:100]:
        print(item)
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
