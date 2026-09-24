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
