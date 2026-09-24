from core.visual_discovery import classify_user_view_state


def test_region_blocked_state():
    out=classify_user_view_state({"body_tail":"Qwen is not available in your region.","upload_busy":False,"send_present":False,"send_enabled":False})
    assert out["state"]=="region_blocked"


def test_login_required_state():
    out=classify_user_view_state({"body_tail":"Sign in to continue","upload_busy":False,"send_present":False,"send_enabled":False})
    assert out["state"]=="login_required"


def test_upload_busy_precedes_ready():
    out=classify_user_view_state({"body_tail":"Uploading","upload_busy":True,"send_present":True,"send_enabled":True})
    assert out["state"]=="upload_busy"


def test_ready_state():
    out=classify_user_view_state({"body_tail":"","upload_busy":False,"send_present":True,"send_enabled":True})
    assert out["state"]=="ready"


def test_access_mapping_for_blocked_view():
    from core.visual_discovery import user_view_access_state
    assert user_view_access_state({"state":"region_blocked"})=="BLOCKED"
    assert user_view_access_state({"state":"challenge"})=="BLOCKED"


def test_access_mapping_for_authenticated_view():
    from core.visual_discovery import user_view_access_state
    assert user_view_access_state({"state":"ready"})=="AUTHENTICATED"
    assert user_view_access_state({"state":"upload_busy"})=="AUTHENTICATED"


def test_login_required_state_persian_visible_text():
    out=classify_user_view_state({"body_tail":"ورود\nبا ورود به سامانه قوانین استفاده را می‌پذیرید.","upload_busy":False,"send_present":False,"send_enabled":False})
    assert out["state"]=="login_required"
    assert out["evidence"]=="ورود"


def test_enabled_composer_counts_as_ready_without_send_button():
    out = classify_user_view_state({
        "body_tail": "",
        "upload_busy": False,
        "send_present": False,
        "send_enabled": False,
        "composer_present": True,
        "composer_enabled": True,
    })
    assert out["state"] == "ready"
    assert out["evidence"] == "visible enabled chat composer"


def test_quota_limited_state_persian_visible_text():
    from core.visual_discovery import user_view_access_state
    out=classify_user_view_state({"body_tail":"محدودیت پردازش فایل در بسته‌ی رایگان. پس از آزادسازی سهمیه دوباره تلاش کنید.","upload_busy":False,"send_present":False,"send_enabled":False})
    assert out["state"]=="quota_limited"
    assert user_view_access_state(out)=="BLOCKED"


def test_visible_login_control_with_composer_is_auth_ambiguous():
    from core.visual_discovery import classify_user_view_state, user_view_access_state
    out=classify_user_view_state({"body_tail":"","visible_control_text":"Sign In","composer_present":True,"composer_enabled":True,"send_present":False,"send_enabled":False,"upload_busy":False})
    assert out["state"]=="auth_ambiguous"
    assert user_view_access_state(out)=="UNKNOWN"


def test_strong_login_surface_precedes_background_composer():
    from core.visual_discovery import classify_user_view_state
    out=classify_user_view_state({"body_tail":"","visible_control_text":"Sign In\nContinue with Google\nSign in with Email","composer_present":True,"composer_enabled":True,"send_present":False,"send_enabled":False,"upload_busy":False})
    assert out["state"]=="login_required"
    assert out["evidence"].lower() in {"continue with google","sign in with email"}


def test_blocking_overlay_precedes_ready_composer():
    from core.visual_discovery import user_view_access_state
    out=classify_user_view_state({
        "body_tail":"NoteGPT has a surprise for you!",
        "blocking_overlays":[{"kind":"viewport_blocking_overlay","coverage":1.0,"text":"NoteGPT has a surprise for you!"}],
        "blocking_dialogs":[],"upload_busy":False,"send_present":True,"send_enabled":True,
        "composer_present":True,"composer_enabled":True,
    })
    assert out["state"]=="blocking_overlay"
    assert user_view_access_state(out)=="BLOCKED"
