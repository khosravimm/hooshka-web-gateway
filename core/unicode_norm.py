"""Unicode normalization for tool-call parsing (ported from hwg-next-0.9.3).

Full-width characters (common in CJK IME output) are mapped to their ASCII
equivalents BEFORE structural extraction so full-width braces are treated
as real braces. Pure stdlib, no new dependencies.
"""

from __future__ import annotations

FULLWIDTH_MAP = str.maketrans({
    "｛": "{", "｝": "}", "［": "[", "］": "]",
    "：": ":", "，": ",", "“": '"', "”": '"',
    "｜": "|", "＼": "\\", "／": "/",
})


def normalize_unicode(s: str) -> str:
    return s.translate(FULLWIDTH_MAP)
