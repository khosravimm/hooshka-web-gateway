from pathlib import Path

from control_panel import _looks_like_browser_profile, _profile_initialized


def test_internal_runtime_directory_without_browser_markers_is_not_profile(tmp_path):
    internal = tmp_path / "ng-store"
    internal.mkdir()
    (internal / "migration.json").write_text("{}", encoding="utf-8")
    assert _looks_like_browser_profile(internal) is False


def test_managed_marker_only_profile_is_not_initialized(tmp_path):
    profile = tmp_path / "profiles" / "new-account"
    profile.mkdir(parents=True)
    (profile / ".hwg-profile.json").write_text("{}", encoding="utf-8")
    assert _looks_like_browser_profile(profile, managed=True) is True
    assert _profile_initialized(profile) is False
    (profile / "Default").mkdir()
    assert _profile_initialized(profile) is True


def test_real_legacy_chrome_profile_markers_are_detected(tmp_path):
    profile = tmp_path / "legacy"
    profile.mkdir()
    (profile / "Local State").write_text("{}", encoding="utf-8")
    assert _looks_like_browser_profile(profile) is True
