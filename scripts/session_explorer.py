import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

CLONE_EXCLUDE_DIRS = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "ShaderCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "Crashpad",
    "component_crx_cache",
}

CLONE_EXCLUDE_FILES = {"SingletonLock", "SingletonCookie", "SingletonSocket"}


def load_provider_info(config_path=None) -> dict:
    config_path = Path(config_path or (ROOT / "config.yaml"))
    if not config_path.exists():
        raise SystemExit(f"config file not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    info = {}
    for p in data.get("providers", []) or []:
        pid = p.get("id")
        if not pid:
            continue
        runtime = p.get("runtime", {}) or {}
        pconfig = p.get("config", {}) or {}
        home = (
            runtime.get("home_url")
            or pconfig.get("base_url")
            or pconfig.get("chatgpt_url")
            or ""
        )
        info[pid] = {
            "type": p.get("type"),
            "home": home,
            "enabled": bool(p.get("enabled", True)),
        }
    return info


def http_get_json(url, timeout=6):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def discover_ports(ports):
    report = []
    for port in ports:
        entry = {"port": port, "up": False}
        try:
            info = http_get_json(f"http://127.0.0.1:{port}/json/version")
            entry.update(
                up=True,
                browser=info.get("Browser"),
                protocol=info.get("Protocol-Version"),
            )
            targets = http_get_json(f"http://127.0.0.1:{port}/json/list")
            entry["page_targets"] = sum(1 for t in targets if t.get("type") == "page")
        except Exception:
            pass
        report.append(entry)
    return report


def profile_dirs_by_name(root, name_contains=("profile",)):
    root = Path(root)
    if not root.exists():
        return []
    found = []
    for d in root.iterdir():
        if d.is_dir() and any(k in d.name.lower() for k in name_contains):
            found.append(d)
    return sorted(found)


def inspect_profile(profile_dir):
    profile_dir = Path(profile_dir)
    cookies_db = profile_dir / "Default" / "Network" / "Cookies"
    login_data = profile_dir / "Default" / "Login Data"
    prefs = profile_dir / "Default" / "Preferences"
    size = 0
    for p in profile_dir.rglob("*"):
        if p.is_file():
            try:
                size += p.stat().st_size
            except OSError:
                pass
    mtimes = []
    for p in profile_dir.rglob("*"):
        if p.is_file():
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                pass
    return {
        "profile": str(profile_dir),
        "exists": profile_dir.exists(),
        "cookies_db": cookies_db.exists(),
        "cookies_db_bytes": cookies_db.stat().st_size if cookies_db.exists() else None,
        "login_data": login_data.exists(),
        "preferences": prefs.exists(),
        "size_bytes": size,
        "last_write": max(mtimes, default=0),
    }


def clone_profile(source, dest):
    source = Path(source)
    dest = Path(dest)
    if not source.exists():
        raise SystemExit(f"source profile missing: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        "robocopy",
        str(source),
        str(dest),
        "/E",
        "/R:2",
        "/W:2",
        "/NFL",
        "/NDL",
        "/NP",
        "/NJH",
        "/NJS",
    ]
    for d in CLONE_EXCLUDE_DIRS:
        cmd += ["/XD", d]
    for f in CLONE_EXCLUDE_FILES:
        cmd += ["/XF", f]
    result = subprocess.run(cmd, capture_output=True, text=True)
    rc = result.returncode
    if rc >= 16:
        raise SystemExit(f"robocopy fatal rc={rc}")
    for f in CLONE_EXCLUDE_FILES:
        (dest / f).unlink(missing_ok=True)
    entry = inspect_profile(dest)
    entry["copy_rc"] = rc
    if rc not in (0, 1):
        entry["copy_note"] = (
            "some source files were locked by a running browser and skipped; "
            "use 'transfer' to move the live session in memory"
        )
    return entry


def write_inventory(entries, inventory_path):
    payload = {
        "generated_at": int(time.time()),
        "note": "metadata only; no secrets stored",
        "profiles": entries,
    }
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _filter_cookies(cookies, domains):
    domains = [d.lower() for d in domains.split(",") if d]
    return [
        c
        for c in cookies
        if any(d in (c.get("domain") or "").lower() for d in domains)
    ]


def _normalize_cookies(cookies):
    normalized = []
    for c in cookies:
        entry = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite", "Lax"),
        }
        if c.get("expires") and c["expires"] > 0:
            entry["expires"] = int(c["expires"])
        if entry["sameSite"] == "None" and not entry["secure"]:
            entry["secure"] = True
        normalized.append(entry)
    return normalized


def transfer_cookies(src_cdp, dst_cdp, domains):
    with sync_playwright() as pw:
        dst_ctx = None
        with pw.chromium.connect_over_cdp(f"http://127.0.0.1:{src_cdp}") as src_browser:
            src_ctx = src_browser.contexts[0] if src_browser.contexts else None
            if src_ctx is None:
                raise SystemExit("source browser has no contexts")
            selected = _normalize_cookies(_filter_cookies(src_ctx.cookies(), domains))
        with pw.chromium.connect_over_cdp(f"http://127.0.0.1:{dst_cdp}") as dst_browser:
            dst_ctx = dst_browser.contexts[0] if dst_browser.contexts else dst_browser.new_context()
            if selected:
                dst_ctx.add_cookies(selected)
    return {
        "transferred": len(selected),
        "memory_only": True,
        "no_file_written": True,
    }


def _chatgpt_login_check(page):
    return page.evaluate(
        "async () => {"
        "  const r = await fetch('/api/auth/session', {credentials:'include'});"
        "  if (!r.ok) return {authenticated:false, session_mode:'unknown'};"
        "  const d = await r.json();"
        "  return {authenticated: !!(d && d.user), session_mode: (d && d.user) ? 'authenticated' : 'anonymous'};"
        "}"
    )


def check_login(cdp_port, provider, config_path=None):
    info = load_provider_info(config_path).get(provider)
    if not info or not info.get("home"):
        raise SystemExit(f"provider not declared in config: {provider}")
    result = {
        "provider": provider,
        "cdp": cdp_port,
        "provider_type": info["type"],
        "home": info["home"],
    }
    with sync_playwright() as pw:
        with pw.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}") as browser:
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(info["home"], timeout=45000, wait_until="domcontentloaded")
            if info["type"] == "chatgpt_web":
                result.update(_chatgpt_login_check(page))
            else:
                result.update(
                    {
                        "authenticated": False,
                        "session_mode": "unknown",
                        "url": page.url,
                        "title": (page.title() or "")[:60],
                    }
                )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Session explorer engine for HWG provider runtimes (metadata only)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("discover")
    p.add_argument("--ports", default="9223,9224,9226,9323,9324,9325,9326")
    p.set_defaults(func=lambda a: print(json.dumps(discover_ports(_ports(a.ports)), indent=2)))

    p = sub.add_parser("profiles")
    p.add_argument("--root", required=True)
    p.set_defaults(
        func=lambda a: print(
            json.dumps(
                [inspect_profile(d) for d in profile_dirs_by_name(a.root)],
                indent=2,
            )
        )
    )

    p = sub.add_parser("clone")
    p.add_argument("--source", required=True)
    p.add_argument("--dest", required=True)
    p.set_defaults(func=lambda a: print(json.dumps(clone_profile(a.source, a.dest), indent=2)))

    p = sub.add_parser("inventory")
    p.add_argument("--out", default=str(ROOT / ".runtime-dev" / "session-inventory.json"))
    p.add_argument("--profiles", nargs="+", required=True)
    p.set_defaults(
        func=lambda a: print(
            json.dumps(
                write_inventory([inspect_profile(x) for x in a.profiles], Path(a.out)),
                indent=2,
            )
        )
    )

    p = sub.add_parser("transfer")
    p.add_argument("--src-cdp", type=int, required=True)
    p.add_argument("--dst-cdp", type=int, required=True)
    p.add_argument("--domains", required=True)
    p.set_defaults(
        func=lambda a: print(
            json.dumps(transfer_cookies(a.src_cdp, a.dst_cdp, a.domains), indent=2)
        )
    )

    p = sub.add_parser("check-login")
    p.add_argument("--cdp", type=int, required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.set_defaults(
        func=lambda a: print(json.dumps(check_login(a.cdp, a.provider, a.config), indent=2))
    )

    args = parser.parse_args()
    args.func(args)


def _ports(raw):
    return [int(x) for x in raw.split(",") if x.strip()]


if __name__ == "__main__":
    main()