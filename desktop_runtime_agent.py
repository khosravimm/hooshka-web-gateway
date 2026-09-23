import ctypes
import json
import os
import shutil
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil

from core.runtime_inventory import inventory_by_id, load_runtime_inventory, load_orchestration_settings
from core.profile_store import load_persistent_inventory, account_runtime

_agent_url = load_orchestration_settings()["desktop_agent_url"]
from urllib.parse import urlparse, unquote, quote
_agent_parsed = urlparse(str(_agent_url))
HOST = _agent_parsed.hostname or "127.0.0.1"
PORT = int(_agent_parsed.port or 5181)
ROOT = os.path.dirname(os.path.abspath(__file__))


def chrome_executable():
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    found = shutil.which("chrome") or shutil.which("chrome.exe")
    if found:
        return found
    raise RuntimeError("Chrome executable not found")


def providers():
    return inventory_by_id()


def account_runtimes():
    try:
        inv = load_persistent_inventory()
    except FileNotFoundError:
        return {}
    out = {}
    for account in inv.get("account_instances", []):
        if account.get("runtime"):
            aid = str(account.get("account_id") or "")
            if aid:
                out[aid] = account_runtime(aid)
    return out


def cdp_ready(item):
    try:
        with urllib.request.urlopen(item["cdp_url"] + "/json/version", timeout=1.2) as response:
            return response.status == 200
    except Exception:
        return False


def provider_page_ready(item):
    """Return True only when this provider host has a real page on the CDP runtime."""
    host = (urlparse(str(item.get("home_url") or "")).hostname or "").lower()
    if not host:
        return False
    try:
        with urllib.request.urlopen(item["cdp_url"] + "/json", timeout=1.5) as response:
            rows = json.loads(response.read().decode("utf-8") or "[]")
        return any(
            str(row.get("type") or "") == "page"
            and (urlparse(str(row.get("url") or "")).hostname or "").lower() == host
            for row in rows if isinstance(row, dict)
        )
    except Exception:
        return False


def open_provider_tab(item):
    """Open the requested provider home in an already-running shared CDP browser."""
    try:
        target = item["cdp_url"] + "/json/new?" + quote(str(item["home_url"]), safe=":/?=&")
        req = urllib.request.Request(target, method="PUT")
        with urllib.request.urlopen(req, timeout=4) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def profile_pids(profile):
    out = []
    needle = os.path.normcase(os.path.abspath(profile))
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (proc.info["name"] or "").lower() != "chrome.exe":
                continue
            cmd = " ".join(proc.info["cmdline"] or [])
            if needle in os.path.normcase(cmd):
                out.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def start_runtime_item(item):
    os.makedirs(item["profile"], exist_ok=True)
    args = [
        chrome_executable(),
        f'--remote-debugging-port={item["port"]}',
        "--remote-debugging-address=127.0.0.1",
        f'--user-data-dir={item["profile"]}',
        "--no-first-run", "--disable-default-apps", "--new-window",
        item["home_url"],
    ]
    subprocess.Popen(args, close_fds=True)
    for _ in range(24):
        if cdp_ready(item):
            return True
        time.sleep(0.5)
    return False


def stop_runtime_item(item):
    for pid in profile_pids(item["profile"]):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=8)
        except Exception:
            pass
    time.sleep(0.7)


def start_provider(provider_id):
    return start_runtime_item(providers()[provider_id])


def stop_provider(provider_id):
    stop_runtime_item(providers()[provider_id])


def visible_window_for_profile(profile):
    pids = set(profile_pids(profile))
    if not pids:
        return None
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            found.append({"hwnd": int(hwnd), "pid": int(pid.value), "title": buf.value})
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _foreground(window):
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow(window["hwnd"], 9)
        user32.SetForegroundWindow(window["hwnd"])
    except Exception:
        pass


def _launch_visible_window_item(item):
    subprocess.Popen([
        chrome_executable(),
        f'--remote-debugging-port={item["port"]}',
        "--remote-debugging-address=127.0.0.1",
        f'--user-data-dir={item["profile"]}',
        "--no-first-run", "--disable-default-apps", "--new-window",
        item["home_url"],
    ], close_fds=True)
    for _ in range(16):
        window = visible_window_for_profile(item["profile"])
        if window:
            _foreground(window)
            return window
        time.sleep(0.25)
    return None


def open_runtime_item(item):
    if not cdp_ready(item) and not start_runtime_item(item):
        return False
    # A shared browser being alive does not prove the requested provider tab
    # exists. Ensure host-specific presence before reporting success.
    if not provider_page_ready(item):
        if not open_provider_tab(item):
            return False
        for _ in range(12):
            if provider_page_ready(item):
                break
            time.sleep(0.25)
        if not provider_page_ready(item):
            return False
    window = visible_window_for_profile(item["profile"])
    if window:
        _foreground(window)
        return True
    if _launch_visible_window_item(item):
        return provider_page_ready(item)
    return False


def _launch_visible_window(provider_id):
    return _launch_visible_window_item(providers()[provider_id])


def open_provider(provider_id):
    return open_runtime_item(providers()[provider_id])


def _item_status(item):
    return {
        "ready": cdp_ready(item),
        "port": item["port"],
        "cdp_url": item["cdp_url"],
        "profile": item["profile"],
        "pids": profile_pids(item["profile"]),
    }


def status():
    result = {}
    for item in load_runtime_inventory():
        result[item["id"]] = {"enabled": item["enabled"], **_item_status(item)}
    return result


def account_status():
    return {aid: _item_status(item) for aid, item in account_runtimes().items()}


def runtime_action(item, action):
    if action == "start":
        return cdp_ready(item) or start_runtime_item(item)
    if action == "restart":
        stop_runtime_item(item); return start_runtime_item(item)
    if action == "stop":
        stop_runtime_item(item); return not cdp_ready(item)
    if action == "repair":
        return cdp_ready(item) or start_runtime_item(item)
    if action == "open":
        return open_runtime_item(item)
    raise ValueError("invalid_action")


class H(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def out(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.out(200, {"ok": True, "service": "hwg-desktop-runtime-agent", "port": PORT})
        if self.path == "/status":
            return self.out(200, {"ok": True, "providers": status(), "accounts": account_status(), "session": os.environ.get("SESSIONNAME", "")})
        return self.out(404, {"error": "not_found"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 3:
            return self.out(404, {"error": "not_found"})
        scope, raw_id, action = parts
        resource_id = unquote(raw_id)
        if scope == "providers":
            current = providers()
        elif scope == "accounts":
            current = account_runtimes()
        else:
            return self.out(404, {"error": "not_found"})
        item = current.get(resource_id)
        if item is None:
            return self.out(404, {"error": "not_found"})
        try:
            ok = runtime_action(item, action)
            payload = {"ok": ok, "scope": scope, "id": resource_id,
                       "action": action, "status": _item_status(item)}
            return self.out(200 if ok else 503, payload)
        except ValueError as exc:
            return self.out(400, {"error": str(exc)})
        except Exception as exc:
            return self.out(500, {"ok": False, "error": type(exc).__name__, "message": str(exc)})


def ensure_enabled():
    for item in load_runtime_inventory():
        if not item["enabled"]:
            continue
        if not cdp_ready(item):
            try:
                start_provider(item["id"])
            except Exception:
                pass


if __name__ == "__main__":
    ensure_enabled()
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
