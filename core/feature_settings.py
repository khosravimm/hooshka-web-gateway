from __future__ import annotations

from typing import Any
import yaml

from core.providers import ChatCompletionRequest, Provider, ProviderError


FEATURE_NAMES = ("thinking", "search")


def feature_defaults(provider: Provider) -> dict[str, bool]:
    raw = (provider.config.config or {}).get("feature_defaults") or {}
    return {name: bool(raw.get(name, False)) for name in FEATURE_NAMES}


def feature_controls(provider: Provider) -> dict[str, bool]:
    raw = (provider.config.config or {}).get("feature_controls") or {}
    return {name: bool(raw.get(name, False)) for name in FEATURE_NAMES}


def apply_feature_defaults(request: ChatCompletionRequest, provider: Provider) -> ChatCompletionRequest:
    options = request.provider_options if request.provider_options is not None else {}
    defaults = feature_defaults(provider)
    controls = feature_controls(provider)

    for name in FEATURE_NAMES:
        value = options.get(name)
        if value is None:
            value = defaults[name]
        if not isinstance(value, bool):
            raise ProviderError(
                f"{name} must be boolean",
                "invalid_feature_setting",
                provider.provider_id,
                {"feature": name, "value_type": type(value).__name__},
            )
        if value and not controls[name]:
            raise ProviderError(
                f"{provider.provider_id} does not expose a controllable {name} feature",
                f"unsupported_{name}",
                provider.provider_id,
                {"feature": name},
            )
        options[name] = value

    request.provider_options = options
    return request


def provider_feature_state(provider: Provider) -> dict[str, Any]:
    return {
        "defaults": feature_defaults(provider),
        "controls": feature_controls(provider),
    }


def persist_provider_feature_defaults(
    provider: Provider,
    requested: dict[str, Any],
    config_path: str,
) -> dict[str, Any]:
    controls = feature_controls(provider)
    defaults = feature_defaults(provider)
    for name in FEATURE_NAMES:
        if name not in requested:
            continue
        value = requested[name]
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be boolean")
        if value and not controls[name]:
            raise ValueError(f"{provider.provider_id} does not expose controllable {name}")
        defaults[name] = value

    with open(config_path, "r", encoding="utf-8") as f:
        tracked = yaml.safe_load(f) or {}
    entry = next((x for x in tracked.get("providers", []) if x.get("id") == provider.provider_id), None)
    if entry is None:
        raise ValueError(f"Provider {provider.provider_id} not found in config")
    entry.setdefault("config", {})["feature_defaults"] = dict(defaults)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(tracked, f, sort_keys=False, allow_unicode=True)
    provider.config.config["feature_defaults"] = dict(defaults)
    return provider_feature_state(provider)