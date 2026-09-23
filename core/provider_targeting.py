from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from core.profile_store import load_ng_inventory
from core.providers import Provider, ProviderType
from core.media_qualification import apply_persisted_media_certification
from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from adapters.qwen_web_provider import create_qwen_web_provider
from adapters.zai_web_provider import create_zai_web_provider
from adapters.deepseek_web_provider import create_deepseek_web_provider

class TargetingError(ValueError):
    def __init__(self, message: str, code: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details or {}

@dataclass
class InferenceTarget:
    provider_id: str
    profile_id: str | None = None
    account_id: str | None = None
    account: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    dedicated_runtime: bool = False

    def metadata(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "profile_id": self.profile_id,
                "account_id": self.account_id, "dedicated_runtime": self.dedicated_runtime}

def resolve_inference_target(data: dict[str, Any], config_path: str) -> InferenceTarget | None:
    requested_provider=str(data.get("provider") or "").strip() or None
    requested_profile=str(data.get("profile_id") or "").strip() or None
    requested_account=str(data.get("account_id") or "").strip() or None
    if not requested_profile and not requested_account:
        if not requested_provider:
            return None
        inv=load_ng_inventory(config_path)
        known={str(p.get("provider_id") or "") for p in inv.get("provider_profiles",[]) if p.get("provider_id")}
        if requested_provider not in known:
            raise TargetingError(f"Unknown provider: {requested_provider}","unknown_provider",404,{"provider":requested_provider})
        return InferenceTarget(provider_id=requested_provider)
    inv=load_ng_inventory(config_path)
    profiles={str(p.get("profile_id")):p for p in inv.get("provider_profiles",[]) if p.get("profile_id")}
    accounts={str(a.get("account_id")):a for a in inv.get("account_instances",[]) if a.get("account_id")}
    profile=profiles.get(requested_profile) if requested_profile else None
    if requested_profile and profile is None:
        raise TargetingError(f"Unknown profile: {requested_profile}","unknown_profile",404)
    account=accounts.get(requested_account) if requested_account else None
    if requested_account and account is None:
        raise TargetingError(f"Unknown account: {requested_account}","unknown_account",404)
    if account:
        linked=str(account.get("provider_profile_id") or "")
        linked_profile=profiles.get(linked)
        if linked_profile is None:
            raise TargetingError("Account references an unknown provider profile","invalid_account_profile",409,{"account_id":requested_account,"provider_profile_id":linked})
        if profile and profile.get("profile_id") != linked:
            raise TargetingError("profile_id does not match account","account_profile_mismatch",409,{"account_id":requested_account,"profile_id":requested_profile,"account_profile_id":linked})
        profile=linked_profile
    provider_id=str((profile or {}).get("provider_id") or requested_provider or "").strip()
    if not provider_id:
        raise TargetingError("Target does not resolve to a provider","target_provider_missing",409)
    if requested_provider and requested_provider != provider_id:
        raise TargetingError("provider does not match profile/account","target_provider_mismatch",409,{"provider":requested_provider,"resolved_provider":provider_id})
    if account and account.get("enabled") is not True:
        raise TargetingError("Account is not enabled for inference","account_disabled",409,{"account_id":requested_account})
    runtime=dict((account or {}).get("runtime") or {})
    return InferenceTarget(provider_id=provider_id,profile_id=str((profile or {}).get("profile_id") or "") or None,
                           account_id=requested_account,account=account,profile=profile,dedicated_runtime=bool(runtime))

def bind_provider_to_target(base: Provider, target: InferenceTarget | None, config_path: str) -> tuple[Provider, bool]:
    if target is None or not target.dedicated_runtime:
        return base, False
    runtime=dict((target.account or {}).get("runtime") or {})
    cfg=dict(base.config.config or {})
    cfg["cdp_url"]=str(runtime.get("cdp_url") or "").strip()
    home=str(runtime.get("home_url") or "").strip()
    profile=str(runtime.get("profile_dir") or "").strip()
    if not cfg["cdp_url"]:
        raise TargetingError("Account runtime has no CDP URL","account_runtime_invalid",409,{"account_id":target.account_id})
    if base.provider_type == ProviderType.CHATGPT_WEB:
        cfg["chatgpt_url"]=home.rstrip("/") or str(cfg.get("chatgpt_url") or "https://chatgpt.com")
        cfg["adapter"]=cfg.get("adapter","dom")
        adapter=cfg.pop("adapter")
        cdp=cfg.pop("cdp_url")
        url=cfg.pop("chatgpt_url")
        instance=create_chatgpt_web_provider(base.provider_id,adapter=adapter,cdp_url=cdp,chatgpt_url=url,priority=base.config.priority,enabled=True,**cfg)
    elif base.provider_type == ProviderType.QWEN_WEB:
        if profile: cfg["profile_dir"]=profile
        cfg["transport_mode"]="browser_controller"
        instance=create_qwen_web_provider(base.provider_id,priority=base.config.priority,enabled=True,**cfg)
    elif base.provider_type == ProviderType.ZAI_WEB:
        if profile: cfg["profile_dir"]=profile
        if home: cfg["base_url"]=home.rstrip("/")
        cfg["transport_mode"]="browser_ui_capture"
        instance=create_zai_web_provider(base.provider_id,priority=base.config.priority,enabled=True,**cfg)
    elif base.provider_type == ProviderType.DEEPSEEK_WEB:
        if home: cfg["base_url"]=home
        cfg["transport_mode"]="browser_ui"
        instance=create_deepseek_web_provider(base.provider_id,priority=base.config.priority,enabled=True,**cfg)
    else:
        raise TargetingError("Provider type cannot bind an Account Runtime","account_target_unsupported",400,{"provider":base.provider_id})
    apply_persisted_media_certification(instance,load_ng_inventory(config_path))
    return instance, True
