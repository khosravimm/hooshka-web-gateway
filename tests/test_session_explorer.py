import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import session_explorer as se


def test_discover_ports_reports_down_for_unreachable():
    report = se.discover_ports([1, 2])
    assert [r["up"] for r in report] == [False, False]
    assert {r["port"] for r in report} == {1, 2}


def test_inspect_profile_detects_structure(tmp_path):
    profile = tmp_path / "chatgpt-profile"
    (profile / "Default" / "Network").mkdir(parents=True)
    (profile / "Default" / "Network" / "Cookies").write_bytes(b"x" * 100)
    (profile / "Default" / "Login Data").write_bytes(b"y")
    info = se.inspect_profile(profile)
    assert info["exists"] is True
    assert info["cookies_db"] is True
    assert info["cookies_db_bytes"] == 100
    assert info["login_data"] is True


def test_inspect_profile_missing():
    info = se.inspect_profile(Path("Z:/definitely/not/a/profile"))
    assert info["exists"] is False


def test_clone_excludes_caches_and_locks(tmp_path):
    src = tmp_path / "src"
    (src / "Default" / "Cache").mkdir(parents=True)
    (src / "Default" / "Network").mkdir(parents=True)
    (src / "Default" / "Network" / "Cookies").write_bytes(b"cookie-db")
    (src / "SingletonLock").write_bytes(b"")
    (src / "Default" / "Preferences").write_bytes(b"{}")
    dest = tmp_path / "dest"
    info = se.clone_profile(src, dest)
    assert info["cookies_db"] is True
    assert info["copy_rc"] == 1
    assert not (dest / "SingletonLock").exists()
    assert not (dest / "Default" / "Cache").exists()
    assert (dest / "Default" / "Preferences").exists()


def test_inventory_writes_metadata_only(tmp_path):
    profile = tmp_path / "p"
    (profile / "Default" / "Network").mkdir(parents=True)
    (profile / "Default" / "Network" / "Cookies").write_bytes(b"ab")
    out = tmp_path / "inv.json"
    payload = se.write_inventory([se.inspect_profile(profile)], out)
    raw = out.read_text(encoding="utf-8")
    for forbidden in ('"value"', "password", "Bearer", "authorization"):
        assert forbidden.lower() not in raw.lower()
    assert payload["profiles"][0]["cookies_db"] is True


def test_ports_parser():
    assert se._ports("1,2,3") == [1, 2, 3]
    assert se._ports("10,,20") == [10, 20]


def test_filter_cookies_by_domain():
    cookies = [
        {"domain": ".chatgpt.com", "name": "a"},
        {"domain": ".openai.com", "name": "b"},
        {"domain": ".example.org", "name": "c"},
    ]
    selected = se._filter_cookies(cookies, "chatgpt.com,openai.com")
    assert [c["name"] for c in selected] == ["a", "b"]


def test_normalize_cookies_keeps_needed_fields():
    cooked = se._normalize_cookies(
        [
            {
                "name": "sid",
                "value": "abc",
                "domain": ".chatgpt.com",
                "path": "/",
                "expires": 1789999999.7,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            }
        ]
    )
    one = cooked[0]
    assert one["name"] == "sid"
    assert one["expires"] == 1789999999
    assert one["httpOnly"] is True
    assert one["sameSite"] == "None"


def test_normalize_cookies_force_secure_for_samesite_none():
    cooked = se._normalize_cookies(
        [
            {
                "name": "x",
                "value": "v",
                "domain": ".x.com",
                "path": "/",
                "secure": False,
                "sameSite": "None",
            }
        ]
    )
    assert cooked[0]["secure"] is True