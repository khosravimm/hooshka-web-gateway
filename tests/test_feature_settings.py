from pathlib import Path

import yaml

from adapters.qwen_web_provider import create_qwen_web_provider
from core.feature_settings import (
    apply_feature_defaults,
    persist_provider_feature_defaults,
    provider_feature_state,
)
from core.providers import ChatCompletionRequest


def test_feature_defaults_and_request_override():
    provider = create_qwen_web_provider(
        feature_defaults={"thinking": False, "search": True},
        feature_controls={"thinking": True, "search": True},
    )
    req = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
        provider_options={"thinking": True, "search": None},
    )
    apply_feature_defaults(req, provider)
    assert req.provider_options["thinking"] is True
    assert req.provider_options["search"] is True


def test_persist_provider_feature_defaults(tmp_path: Path):
    provider = create_qwen_web_provider(
        feature_defaults={"thinking": False, "search": False},
        feature_controls={"thinking": True, "search": True},
    )
    cfg = {
        "providers": [
            {
                "id": "qwen-web",
                "type": "qwen_web",
                "config": {
                    "feature_defaults": {"thinking": False, "search": False},
                    "feature_controls": {"thinking": True, "search": True},
                },
            }
        ]
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    state = persist_provider_feature_defaults(
        provider,
        {"thinking": True, "search": True},
        str(path),
    )

    assert state["defaults"] == {"thinking": True, "search": True}
    stored = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = stored["providers"][0]["config"]["feature_defaults"]
    assert defaults == {"thinking": True, "search": True}
    assert provider_feature_state(provider)["defaults"] == defaults
