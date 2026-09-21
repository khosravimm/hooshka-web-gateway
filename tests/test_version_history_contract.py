import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def test_release_version_sources_are_synchronized():
    version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    manifest = _json("MANIFEST.json")
    ui = _json("control_panel_ui/UI_VERSION.json")
    assert version == "1.0.0-dev.6"
    assert manifest["version"] == version
    assert ui["version"] == version
    assert manifest["build_date"] == "2026-09-22"
    assert ui["released"] == "2026-09-22"


def test_dev6_change_history_and_schema_contracts_exist():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    record = ROOT / "docs/governance/HWG_1.0.0-dev.6_CHANGE_RECORD_20260922.md"
    assert "## 1.0.0-dev.6 - 2026-09-22" in changelog
    assert record.is_file()
    for name in ("hwg-provider-profile-v1.schema.json", "hwg-account-instance-v1.schema.json"):
        schema = _json("schemas/" + name)
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["$id"].endswith("1.0.0")
