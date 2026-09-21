"""API-key hashing: stored keys are verify-only hashes, never secrets.

Format: ``sha256:<hex>`` of the token. Plaintext tokens exist only in
transit (creation response) and are never written to config, logs, or disk.
Uses stdlib hashlib; no new dependencies.
"""

from __future__ import annotations

import hashlib

PREFIX = "sha256:"


def hash_token(token: str) -> str:
    return PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_hash(ref: str) -> bool:
    return isinstance(ref, str) and ref.startswith(PREFIX) and len(ref) == len(PREFIX) + 64


def normalize_ref(token_or_hash: str) -> str:
    """Accept a plaintext token (legacy) or an existing hash ref."""
    if is_hash(token_or_hash):
        return token_or_hash
    return hash_token(token_or_hash)
