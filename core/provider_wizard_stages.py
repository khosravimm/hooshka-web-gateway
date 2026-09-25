from __future__ import annotations

MISSION = (
    "تبدیل یک URL ناشناخته Web Chat به Provider Profile غیرفعال، قابل‌ممیزی و دارای Evidence "
    "برای Access، مدل‌ها، Chat، Tool Calling و قابلیت‌های Account/Session جاری."
)

STAGES = [
    {"id":"S1","name":"ACCESS_BOOTSTRAP","title":"دسترسی و ورود","exit":"Guest/Auth usable یا Human Gate واقعی"},
    {"id":"S2","name":"MODEL_ENTITLEMENT_DISCOVERY","title":"مدل‌ها و دسترسی حساب","exit":"حالت انتخاب، مدل جاری و inventory ثبت شود"},
    {"id":"S3","name":"BASELINE_CHAT","title":"چت پایه","exit":"Round-trip واقعی E2"},
    {"id":"S4","name":"BASIC_AGENT_TOOLS","title":"ابزارهای پایه","exit":"Tool call → اجرا → continuation"},
    {"id":"CP-A","name":"AGENT_BASIC_READY","title":"وب‌چت پایه آماده","exit":"S1 تا S4 معتبر"},
    {"id":"S5","name":"FULL_TOOL_PROTOCOL","title":"پروتکل کامل ابزارها","exit":"Tool matrix ثبت شود"},
    {"id":"S6","name":"EXTENDED_CAPABILITIES","title":"قابلیت‌های توسعه‌یافته","exit":"Search/Thinking/Media/Native evidence"},
    {"id":"S7","name":"PER_MODEL_QUALIFICATION","title":"اعتبارسنجی مدل‌ها","exit":"Evidence مستقل مدل‌های مهم"},
    {"id":"S8","name":"PROFILE_MATERIALIZATION","title":"ساخت Profile","exit":"فقط facts اثبات‌شده، enabled=false"},
    {"id":"S9","name":"FINAL_READINESS","title":"آمادگی نهایی","exit":"Readiness + limitations + revalidation"},
]

HUMAN_GATES = ["login","captcha_or_challenge","terms_or_consent","account_choice","destructive_action","provider_enable","ambiguous_high_impact_choice"]


def infer_stage(observation: dict | None, technical: dict | None = None) -> dict:
    observation=observation or {}; technical=technical or {}
    state=str((observation.get("classification") or {}).get("state") or "unknown")
    access=str((observation.get("access_semantics") or {}).get("state") or "UNKNOWN").upper()
    if state in {"login_required","challenge"} or access=="LOGIN_REQUIRED":
        return {"stage_id":"S1","stage_state":"USER_GATE","next_required":"complete_access_gate"}
    if state not in {"ready","auth_ambiguous"} or access not in {"ACCESS_AVAILABLE","AUTHENTICATED","UNKNOWN"}:
        return {"stage_id":"S1","stage_state":"RUNNING","next_required":"establish_access"}
    model=(observation.get("deterministic_discovery") or {}).get("model_surface") or technical.get("model_surface") or {}
    if model.get("status") != "observed":
        return {"stage_id":"S2","stage_state":"RUNNING","next_required":"discover_model_entitlements"}
    qual=technical.get("submit_qualification") or {}
    if technical.get("workflow_state") == "ROUNDTRIP_QUALIFIED" or qual.get("status") == "E2_VERIFIED":
        return {"stage_id":"S4","stage_state":"READY_TO_RUN","next_required":"basic_agent_tool_qualification"}
    return {"stage_id":"S3","stage_state":"READY_TO_RUN","next_required":"baseline_chat_qualification"}


def public_model() -> dict:
    return {"mission":MISSION,"stages":STAGES,"human_gates":HUMAN_GATES}
