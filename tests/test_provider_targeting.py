from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

from core.provider_targeting import TargetingError, resolve_inference_target


def test_default_deepseek_profile_account_resolves_real_provider():
    target = resolve_inference_target({
        "provider": "deepseek-web",
        "profile_id": "deepseek-web:default",
        "account_id": "deepseek-web:default-account",
    }, str(ROOT / "config.yaml"))
    assert target.provider_id == "deepseek-web"
    assert target.profile_id == "deepseek-web:default"
    assert target.account_id == "deepseek-web:default-account"
    assert target.dedicated_runtime is False


def test_target_provider_mismatch_fails_closed():
    with pytest.raises(TargetingError) as exc:
        resolve_inference_target({
            "provider": "chatgpt-web",
            "account_id": "deepseek-web:default-account",
        }, str(ROOT / "config.yaml"))
    assert exc.value.code == "target_provider_mismatch"
    assert exc.value.status == 409

def test_unknown_account_fails_closed():
    with pytest.raises(TargetingError) as exc:
        resolve_inference_target({"account_id": "missing-account"}, str(ROOT / "config.yaml"))
    assert exc.value.code == "unknown_account"
    assert exc.value.status == 404
