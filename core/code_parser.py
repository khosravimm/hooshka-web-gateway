import re
from typing import List, Dict, Optional


def extract_code_blocks(text: str, language: Optional[str] = None) -> List[Dict[str, str]]:
    pattern = r"```([^\n]*)\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)

    blocks = []
    for lang, code in matches:
        detected = (lang or "").strip().lower()
        if language and detected and detected != language.lower():
            continue
        blocks.append({
            "language": detected or "text",
            "code": code,
        })

    if not blocks:
        return [{"language": "text", "code": text}]

    return blocks


def extract_code_block(text: str, language: Optional[str] = None) -> Dict[str, str]:
    blocks = extract_code_blocks(text, language=language)
    return blocks[0]


def save_code_block(code: str, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path
