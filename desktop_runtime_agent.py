import ctypes
import json
import os
import shutil
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil

from core.runtime_inventory import inventory_by_id, load_runtime_inventory

HOST = "127.0.0.1"
PORT = 5091
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


def cdp_ready(item):
    try:
        with urllib.request.urlopen(item["cdp_url"] + "/json/version", timeout=1.2) as response:
            return response.status == 200
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


def start_provider(provider_id):
    item = providers()[provider_id]
    os.makedirs(item["profile"], exist_ok=True)
    args = [
        chrome_executable(),
        f'--remote-debugging-port={item["port"]}',
        "--remote-debugging-address=127.0.0.1",
        f'--user-data-dir={item["profile"]}',
        "--no-first-run",
        "--disable-default-apps",
        "--new-window",
        item["home_url"],
    ]
    subprocess.Popen(args, close_fds=True)
    for _ in range(24):
        if cdp_ready(item):
            return True
        time.sleep(0.5)
    return False


def stop_provider(provider_id):
    item = providers()[provider_id]
    for pid in profile_pids(item["profile"]):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=8)
        except Exception:
            pass
    time.sleep(0.7)


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


def _launch_visible_window(provider_id):
    item = providers()[provider_id]
    subprocess.Popen(
        [
            chrome_executable(),
            f'--remote-debugging-port={item["port"]}',
            "--remote-debugging-address=127.0.0.1",
            f'--user-data-dir={item["profile"]}',
            "--no-first-run",
            "--disable-default-apps",
            "--new-window",
            item["home_url"],
        ],
        close_fds=True,
    )
    for _ in range(16):
        window = visible_window_for_profile(item["profile"])
        if window:
            _foreground(window)
            return window
        time.sleep(0.25)
    return None


def open_provider(provider_id):
    item = providers()[provider_id]
    if not cdp_ready(item) and not start_provider(provider_id):
        return False
    window = visible_window_for_profile(item["profile"])
    if window:
        _foreground(window)
        return True
    if _launch_visible_window(provider_id):
        return True
    # A stale Chrome singleton can absorb --new-window. One controlled restart
    # is allowed here because Open Browser is an explicit user action.
    stop_provider(provider_id)
    if not start_provider(provider_id):
        return False
    return visible_window_for_profile(item["profile"]) is not None


def status():
    result = {}
    for item in load_runtime_inventory():
        result[item["id"]] = {
            "enabled": item["enabled"],
            "ready": cdp_ready(item),
            "port": item["port"],
            "cdp_url": item["cdp_url"],
            "profile": item["profile"],
            "pids": profile_pids(item["profile"]),
        }
    return result


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
        if self.path == "/status":
            return self.out(200, {"ok": True, "providers": status(), "session": os.environ.get("SESSIONNAME", "")})
        return self.out(404, {"error": "not_found"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        current = providers()
        if len(parts) != 3 or parts[0] != "providers" or parts[1] not in current:
            return self.out(404, {"error": "not_found"})
        provider_id, action = parts[1], parts[2]
        item = current[provider_id]
        try:
            if action == "start":
                ok = cdp_ready(item) or start_provider(provider_id)
            elif action == "restart":
                stop_provider(provider_id)
                ok = start_provider(provider_id)
            elif action == "stop":
                stop_provider(provider_id)
                ok = not cdp_ready(item)
            elif action == "repair":
                ok = cdp_ready(item) or start_provider(provider_id)
            elif action == "open":
                ok = open_provider(provider_id)
            else:
                return self.out(400, {"error": "invalid_action"})
            return self.out(200 if ok else 503, {"ok": ok, "provider": provider_id, "action": action, "status": status()[provider_id]})
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
