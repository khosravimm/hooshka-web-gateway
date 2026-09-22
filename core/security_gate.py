"""Release-blocking security policy checks for HWG runtime exposure."""
from __future__ import annotations

import ipaddress


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_loopback_host(host: str) -> bool:
    value = str(host or "").strip().lower().strip("[]")
    if value in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def validate_remote_exposure(config: dict) -> list[str]:
    """Return policy errors. An empty list means the bind is allowed."""
    server = config.get("server", {}) or {}
    if is_loopback_host(server.get("host", "127.0.0.1")):
        return []

    governance = config.get("governance", {}) or {}
    remote = governance.get("remote_access", {}) or {}
    errors = []
    if governance.get("auth", {}).get("enabled") is not True:
        errors.append("remote bind requires API-key authentication")
    if governance.get("rate_limiting", {}).get("enabled") is not True:
        errors.append("remote bind requires rate limiting")
    if governance.get("audit", {}).get("enabled") is not True:
        errors.append("remote bind requires audit logging")
    if remote.get("enabled") is not True:
        errors.append("remote bind requires explicit remote_access.enabled=true")
    if remote.get("tls_termination") is not True:
        errors.append("remote bind requires declared TLS termination")
    if remote.get("network_acl") is not True:
        errors.append("remote bind requires declared network ACL/firewall")
    return errors


def assert_remote_exposure_safe(config: dict) -> None:
    errors = validate_remote_exposure(config)
    if errors:
        raise RuntimeError("Unsafe non-loopback bind refused: " + "; ".join(errors))


def validate_multimodal_enablement(config: dict) -> list[str]:
    providers = config.get("providers", []) or []
    requested = []
    for provider in providers:
        caps = provider.get("capabilities", {}) or {}
        if caps.get("files") is True or caps.get("vision") is True:
            requested.append(str(provider.get("id") or "unknown"))
    if not requested:
        return []
    policy = (((config.get("governance", {}) or {}).get("input_validation", {}) or {}).get("file_upload", {}) or {})
    errors = []
    if policy.get("enabled") is not True:
        errors.append("file/vision capability requires input_validation.file_upload.enabled=true")
    if int(policy.get("max_file_bytes") or 0) <= 0:
        errors.append("file/vision capability requires bounded max_file_bytes")
    if not list(policy.get("allowed_mime_types") or []):
        errors.append("file/vision capability requires non-empty allowed_mime_types")
    if policy.get("reject_unknown_type") is not True:
        errors.append("file/vision capability requires reject_unknown_type=true")
    if errors:
        errors.insert(0, "providers requesting file/vision: " + ",".join(sorted(requested)))
    return errors


def assert_release_security_config(config: dict) -> None:
    errors = validate_remote_exposure(config) + validate_multimodal_enablement(config)
    if errors:
        raise RuntimeError("Unsafe security configuration refused: " + "; ".join(errors))
