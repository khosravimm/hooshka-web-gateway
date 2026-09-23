from io import BytesIO
from pathlib import Path

import main

ROOT = Path(__file__).resolve().parents[1]


def test_v1_upload_lifecycle_returns_opaque_id(monkeypatch, tmp_path):
    monkeypatch.setenv("HWG_UPLOAD_ROOT", str(tmp_path))
    app = main.create_app(str(ROOT / "config.yaml"))
    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.post("/v1/uploads", data={"files": (BytesIO(b"abc"), "sample.txt")}, content_type="multipart/form-data")
    assert resp.status_code == 201
    row = resp.get_json()["data"][0]
    assert row["name"] == "sample.txt"
    assert "path" not in row and len(row["id"]) == 32
    deleted = client.delete("/v1/uploads/" + row["id"])
    assert deleted.status_code == 200 and deleted.get_json()["deleted"] is True


def test_embedded_chat_wires_canonical_upload_ids():
    html = (ROOT / "control_panel_ui/index.html").read_text(encoding="utf-8-sig")
    js = (ROOT / "control_panel_ui/chat.js").read_text(encoding="utf-8-sig")
    assert 'id="chat-file-input"' in html
    assert "fetch('/v1/uploads'" in js
    assert "upload_ids: attachedUploads.map" in js
    assert "providerAcceptsAttachments" in js
    assert "بدون endpoint آپلود" not in js
