from io import BytesIO
from pathlib import Path

import pytest

from core.upload_store import UploadStoreError, delete_upload, resolve_upload, save_upload


def test_upload_store_uses_opaque_id_and_hides_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HWG_UPLOAD_ROOT", str(tmp_path))
    meta = save_upload(BytesIO(b"HWG_UPLOAD_MARKER"), "report.txt", "text/plain", ttl_seconds=60)
    assert len(meta["id"]) == 32
    assert "path" not in meta
    path, resolved = resolve_upload(meta["id"])
    assert Path(path).read_bytes() == b"HWG_UPLOAD_MARKER"
    assert resolved["name"] == "report.txt"
    assert delete_upload(meta["id"]) is True
