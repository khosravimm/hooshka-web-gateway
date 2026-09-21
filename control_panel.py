import os
import json
import time
import logging
import subprocess
import secrets
import shutil
import re
import yaml
import psutil
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template_string, jsonify, request, current_app
from core.provider_registry import provider_registry
from core.mcp import mcp_session_manager
from core.governance import auth_manager, rate_limiter
from core.config import load_config, deep_merge, get_default_config
from core.feature_settings import persist_provider_feature_defaults, provider_feature_state
from core.runtime_inventory import inventory_by_id, load_orchestration_settings

control_panel_bp = Blueprint('control_panel', __name__, url_prefix='/panel')

logger = logging.getLogger(__name__)

CONFIG_PATH = str(Path(__file__).parent / "config.yaml")


def _write_restart_state(state_path, request_id, state, success, reason, errors=None):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "request_id": request_id, "state": state, "success": success,
        "reason": reason, "updated_at": datetime.now().isoformat(),
        "errors": list(errors or []),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _schedule_restart_all(reason="config-save"):
    """Schedule restart-all through an independent SYSTEM Scheduled Task and return a traceable request id.

    If the scheduled task is not installed (e.g. running outside the service),
    return a non-fatal warning instead of raising, so that config/provider
    changes still persist.
    """
    request_id = secrets.token_hex(8)
    state_path = Path(__file__).parent / ".runtime" / "restart_state.json"
    _write_restart_state(state_path, request_id, "scheduled", False, reason)
    task_name = str(load_orchestration_settings(CONFIG_PATH)["restart_all_task"])
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", task_name],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()[:200]
            _write_restart_state(state_path, request_id, "schedule_failed", False, reason, [detail or "schtasks_failed"])
            return {"scheduled": False, "reason": reason, "request_id": request_id,
                    "task": task_name,
                    "warning": "Scheduled task not available; restart will not happen automatically",
                    "detail": detail}
    except FileNotFoundError:
        _write_restart_state(state_path, request_id, "schedule_failed", False, reason, ["schtasks_not_found"])
        return {"scheduled": False, "reason": reason, "request_id": request_id,
                "task": task_name,
                "warning": "schtasks not available; restart will not happen automatically"}
    return {"scheduled": True, "reason": reason, "request_id": request_id, "task": task_name}


def _restart_state():
    state_path = Path(__file__).parent / ".runtime" / "restart_state.json"
    if not state_path.exists():
        return {"state": "idle", "success": None, "errors": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"state": "invalid", "success": False, "errors": [type(exc).__name__]}


def _schedule_gateway_restart(reason="panel-service-restart"):
    """Schedule gateway restart outside the service process so it cannot kill its own restart worker."""
    request_id = secrets.token_hex(8)
    state_path = Path(__file__).parent / ".runtime" / "service_restart_state.json"
    _write_restart_state(state_path, request_id, "scheduled", False, reason)
    task_name = str(load_orchestration_settings(CONFIG_PATH)["restart_gateway_task"])
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", task_name],
            capture_output=True, text=True, timeout=8,
        )
    except FileNotFoundError as exc:
        _write_restart_state(state_path, request_id, "schedule_failed", False, reason, ["schtasks_not_found"])
        raise RuntimeError("schtasks not available; gateway restart was not scheduled") from exc
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip() or "Failed to start gateway restart task"
        _write_restart_state(state_path, request_id, "schedule_failed", False, reason, [detail[:200]])
        raise RuntimeError(detail)
    return {"scheduled": True, "reason": reason, "request_id": request_id, "task": task_name}


def _gateway_restart_state():
    state_path = Path(__file__).parent / ".runtime" / "service_restart_state.json"
    if not state_path.exists():
        return {"state": "idle", "success": None, "errors": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"state": "invalid", "success": False, "errors": [type(exc).__name__]}


def _read_version():
    try:
        return (Path(__file__).parent / "VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except Exception:
        return "unknown"


def _git_value(*args):
    roots = []
    here = Path(__file__).parent
    for candidate in (
        here,
        here.resolve(),
        Path("D:/Code/mcp-web-bridge"),
        Path("D:/Code/hooshka-web-gateway"),
    ):
        if candidate not in roots:
            roots.append(candidate)
    try:
        for root in roots:
            result = subprocess.run(
                ["git", *args],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=3,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_panel_meta():
    commit = _git_value("rev-parse", "--short", "HEAD")
    branch = _git_value("branch", "--show-current")
    if commit == "unknown" or branch == "unknown":
        head_path = Path(__file__).parent / ".git" / "HEAD"
        if head_path.exists():
            try:
                head = head_path.read_text(encoding="utf-8").strip()
                if head.startswith("ref:"):
                    ref = head.split(" ", 1)[1].strip()
                    branch = ref.rsplit("/", 1)[-1]
                    ref_path = head_path.parent / ref.replace("/", os.sep)
                    if ref_path.exists():
                        commit = ref_path.read_text(encoding="utf-8").strip()[:7]
                elif head:
                    branch = "detached"
                    commit = head[:7]
            except Exception:
                pass
    return {
        "version": _read_version(),
        "commit": commit,
        "branch": branch,
        "evidence": _panel_evidence(),
    }


def _panel_evidence():
    manifest_path = Path(__file__).parent / "MANIFEST.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        gates = (data.get("gates") or {}) if isinstance(data, dict) else {}
        passed = [k for k, v in gates.items() if isinstance(v, dict) and str(v.get("status") or "").upper() == "PASS"]
        if passed:
            return "gates: " + ", ".join(passed)
        return "gates: none marked PASS"
    except Exception:
        return "gates: unknown"


def _check_cdp(cdp_url):
    if not cdp_url:
        return {"cdp_url": None, "ready": None, "status": "not_applicable"}
    try:
        with urllib.request.urlopen(cdp_url.rstrip("/") + "/json/version", timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ready = response.status == 200 and bool(payload.get("webSocketDebuggerUrl"))
            return {"cdp_url": cdp_url, "ready": ready, "status": "ready" if ready else "unverified"}
    except Exception as exc:
        return {"cdp_url": cdp_url, "ready": False, "status": "unavailable", "error": type(exc).__name__}


def _provider_model_state(provider):
    cfg = provider.config.config or {}
    default_model = cfg.get("default_upstream_model") or cfg.get("upstream_model") or provider.provider_id
    configured = cfg.get("selectable_upstream_models") or []
    if isinstance(configured, str):
        configured = [configured]
    model_options = []
    for item in [default_model, *configured, *list(provider.capabilities.supported_models or [])]:
        if item and item not in model_options:
            model_options.append(item)
    return {
        "default": default_model,
        "options": model_options,
        "config_key": "default_upstream_model",
    }


def _provider_payload(provider):
    _cfg, persisted = _provider_config_entry(provider.provider_id) if '_provider_config_entry' in globals() else ({}, None)
    persisted = persisted or {}
    runtime_cfg = persisted.get("runtime", {}) or {}
    return {
        "id": provider.provider_id,
        "type": provider.provider_type.value,
        "enabled": bool(persisted.get("enabled", provider.config.enabled)),
        "priority": int(persisted.get("priority", provider.config.priority)),
        "profile_dir": runtime_cfg.get("profile_dir") or provider.config.config.get("profile_dir") or "",
        "capabilities": {
            "chat_completion": provider.capabilities.chat_completion,
            "streaming": provider.capabilities.streaming,
            "tools": provider.capabilities.tools,
            "vision": provider.capabilities.vision,
            "embeddings": provider.capabilities.embeddings,
            "max_context_tokens": provider.capabilities.max_context_tokens,
            "supported_models": provider.capabilities.supported_models,
        },
        "features": provider_feature_state(provider),
        "runtime": _check_cdp(provider.config.config.get("cdp_url")),
        "model": _provider_model_state(provider),
    }


def _persist_provider_config_value(provider_id, key, value):
    config = _load_config_file()
    for item in config.get("providers", []) or []:
        if item.get("id") == provider_id:
            provider_cfg = item.setdefault("config", {})
            provider_cfg[key] = value
            _save_config_file(config)
            provider = provider_registry.get(provider_id)
            if provider:
                provider.config.config[key] = value
                attr = f"_{key}"
                if hasattr(provider, attr):
                    setattr(provider, attr, value)
            return True
    return False


def _load_config_file():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config_file(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _sync_auth_keys():
    """Sync API keys without dropping the runtime environment key.

    The Windows service supplies the bootstrap key through BRIDGE_API_KEY.
    Rebuilding the runtime map only from config.yaml invalidates that key after
    visiting the control panel key APIs, so keep it as a non-persistent runtime
    key and then add persistent config keys.
    """
    config = _load_config_file()
    raw_keys = config.get("governance", {}).get("auth", {}).get("api_keys", {}) or {}
    auth_manager._api_keys.clear()

    env_key = os.getenv("BRIDGE_API_KEY")
    if env_key:
        env_identity = os.getenv("BRIDGE_API_IDENTITY", "local-user")
        auth_manager._api_keys[env_key] = {
            "identity": env_identity,
            "metadata": {"source": "environment", "persistent": False},
        }

    for key, identity in raw_keys.items():
        if isinstance(identity, dict):
            identity_value = identity.get("identity", str(identity))
        else:
            identity_value = str(identity)
        auth_manager._api_keys[key] = {
            "identity": identity_value,
            "metadata": {"source": "config", "persistent": True},
        }

def _run_service_manager(action, provider=None):
    """Run a service action via the PowerShell script. Returns (success, output)."""
    script = f"""
    $ErrorActionPreference = 'Stop'
    & "{Path(__file__).parent / 'service_manager.ps1'}" {action} {provider or 'all'}
    """
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=45,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)


def _service_names():
    settings = load_orchestration_settings(CONFIG_PATH)
    return (
        str(settings["gateway_service"]),
        str(settings.get("legacy_gateway_service") or "").strip(),
    )


def _query_windows_service(name):
    """Return structured Windows Service state without parsing table output."""
    script = f"""
    $svc = Get-Service -Name '{name}' -ErrorAction SilentlyContinue
    if ($null -eq $svc) {{
      [pscustomobject]@{{exists=$false; name='{name}'; display_name=''; status='NotInstalled'; start_type=''; can_stop=$false; service_type=''; dependent_services=0}} | ConvertTo-Json -Compress
      exit 0
    }}
    $wmi = Get-CimInstance Win32_Service -Filter "Name='{name}'" -ErrorAction SilentlyContinue
    [pscustomobject]@{{
      exists=$true
      name=$svc.Name
      display_name=$svc.DisplayName
      status=$svc.Status.ToString()
      start_type=if ($wmi) {{ $wmi.StartMode }} else {{ '' }}
      can_stop=$svc.CanStop
      service_type=$svc.ServiceType.ToString()
      dependent_services=@($svc.DependentServices).Count
    }} | ConvertTo-Json -Compress
    """
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=10,
        )
        output = (result.stdout or "").strip()
        if result.returncode != 0:
            return {"exists": False, "name": name, "status": "Unknown", "error": (result.stderr or "").strip()}
        data = json.loads(output) if output else {}
        data.setdefault("exists", False)
        data.setdefault("name", name)
        data.setdefault("status", "Unknown")
        return data
    except Exception as exc:
        return {"exists": False, "name": name, "status": "Unknown", "error": str(exc)}


def _service_status_payload(output=""):
    service_name, legacy_name = _service_names()
    service = _query_windows_service(service_name)
    legacy = _query_windows_service(legacy_name) if legacy_name else {
        "exists": False, "name": "", "status": "NotConfigured"
    }
    return {
        "exists": bool(service.get("exists")),
        "status": service.get("status", "Unknown"),
        "service": service,
        "legacy_service": legacy,
        "output": output,
    }



def _panel_assets_dir():
    return str(Path(__file__).parent / "control_panel_ui")


PANEL_ASSET_MIMETYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


@control_panel_bp.route('/assets/<path:filename>')
def panel_assets(filename):
    base = Path(_panel_assets_dir()).resolve()
    target = (base / filename).resolve()
    if base != target and not str(target).startswith(str(base) + os.sep):
        return jsonify({"error": "invalid asset path"}), 400
    if not target.is_file():
        return jsonify({"error": "asset not found"}), 404
    mime = PANEL_ASSET_MIMETYPES.get(target.suffix.lower(), "application/octet-stream")
    resp = make_response(target.read_bytes())
    resp.headers["Content-Type"] = mime
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@control_panel_bp.route('/api/runtimes')
def api_runtimes():
    inventory = inventory_by_id(CONFIG_PATH)
    rows = []
    for item in inventory.values():
        live = _check_cdp(item.get("cdp_url"))
        rows.append({
            "id": item.get("id"),
            "label": item.get("label"),
            "port": item.get("port"),
            "profile": item.get("profile"),
            "home_url": item.get("home_url"),
            "cdp_url": item.get("cdp_url"),
            "ready": live.get("ready"),
            "status": live.get("status"),
        })
    return jsonify({"runtimes": rows})


from flask import make_response


@control_panel_bp.after_request
def _set_panel_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@control_panel_bp.route('/')
def dashboard():
    index_path = Path(_panel_assets_dir()) / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except OSError:
        html = ("<!DOCTYPE html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
                "<title>Panel UI missing</title><body style='font-family:sans-serif;padding:2rem'>"
                "<h1>control_panel_ui/index.html not found</h1></body></html>")
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def _get_initial_health():
    try:
        process = psutil.Process()
        memory = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
        cpu = f"{process.cpu_percent()}%"
        uptime_sec = time.time() - process.create_time()
        uptime = f"{int(uptime_sec//3600)}h {int((uptime_sec%3600)//60)}m"
        cdp_connected = False
        try:
            import urllib.request
            config = load_config()
            cdp_url = config.get("cdp", {}).get("url", "http://127.0.0.1:9224")
            req = urllib.request.urlopen(cdp_url + "/json", timeout=2)
            cdp_connected = req.status == 200
        except Exception:
            pass
        return {
            "status": "running",
            "api_responding": True,
            "cdp_connected": cdp_connected,
            "memory": memory,
            "cpu": cpu,
            "uptime": uptime,
        }
    except Exception as e:
        return {"status": "error", "api_responding": False, "cdp_connected": False, "memory": "-", "cpu": "-", "uptime": "-"}


def _get_initial_providers():
    try:
        providers = provider_registry.list_providers(enabled_only=False)
        return {"providers": [_provider_payload(p) for p in providers]}
    except Exception:
        return {"providers": []}


def _get_initial_sessions():
    try:
        sessions = mcp_session_manager.list_sessions()
        return {"sessions": sessions}
    except Exception:
        return {"sessions": []}


def _get_initial_stats():
    try:
        audit_log = "logs/audit.log"
        requests_1h = 0
        now = time.time()
        hour_ago = now - 3600
        if os.path.exists(audit_log):
            with open(audit_log, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("event") == "request_complete":
                            ts = entry.get("timestamp", 0)
                            if ts >= hour_ago:
                                requests_1h += 1
                    except Exception:
                        pass
        return {"requests_1h": requests_1h, "requests_history": []}
    except Exception:
        return {"requests_1h": 0, "requests_history": []}


def _get_initial_auth():
    try:
        config = _load_config_file()
        raw_keys = config.get("governance", {}).get("auth", {}).get("api_keys", {}) or {}
        auth_enabled = config.get("governance", {}).get("auth", {}).get("enabled", False)
        keys = []
        for key, identity in raw_keys.items():
            keys.append({
                "key": key,
                "identity": identity if isinstance(identity, str) else identity.get("identity", str(identity)),
                "created_at": "-",
            })
        return {"auth_enabled": auth_enabled, "api_keys": keys}
    except Exception:
        return {"auth_enabled": False, "api_keys": []}


def _get_initial_config():
    try:
        config_path = "config.yaml"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    except Exception:
        return ""


def _get_initial_service():
    return _service_status_payload()

@control_panel_bp.route('/api/health')
def api_health():
    from core.config import load_config
    
    config = load_config()
    cdp_url = config.get("cdp", {}).get("url", "http://127.0.0.1:9224")
    
    status = "running"
    
    # API is responding if this endpoint returns
    api_responding = True
    
    # Check CDP
    cdp_connected = False
    cdp_endpoint = "unknown"
    try:
        import urllib.request
        import json
        # Use the canonical CDP version endpoint without external dependencies.
        # The bridge health endpoint must work in minimal Python environments.
        with urllib.request.urlopen(cdp_url + "/json/version", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status == 200 and payload.get("webSocketDebuggerUrl"):
                cdp_connected = True
                cdp_endpoint = "available"
        if not cdp_connected:
            with urllib.request.urlopen(cdp_url + "/json", timeout=2) as response:
                cdp_connected = response.status == 200
                cdp_endpoint = "available" if cdp_connected else "unavailable"
    except Exception:
        cdp_endpoint = "unavailable"
    
    # System stats
    process = psutil.Process()
    memory = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
    cpu = f"{process.cpu_percent()}%"
    
    # Uptime
    uptime_sec = time.time() - process.create_time()
    uptime = f"{int(uptime_sec//3600)}h {int((uptime_sec%3600)//60)}m"
    
    return jsonify({
        "status": status,
        "api_responding": api_responding,
        "cdp_connected": cdp_connected,
        "memory": memory,
        "cpu": cpu,
        "uptime": uptime
    })

@control_panel_bp.route('/api/meta')
def api_meta():
    return jsonify(_get_panel_meta())


@control_panel_bp.route('/api/providers', methods=['GET', 'POST'])
def api_providers():
    if request.method == 'GET':
        providers = provider_registry.list_providers(enabled_only=False)
        return jsonify({"providers": [_provider_payload(p) for p in providers]})

    # POST: add new provider
    data = request.get_json(force=True) or {}
    provider_id = str(data.get("id", "")).strip()
    provider_type = data.get("type", "")
    if not provider_id or not provider_type:
        return jsonify({"error": "id and type are required"}), 400
    config = data.get("config", {})
    config = dict(config) if config else {}
    # Validate required runtime fields for browser providers
    runtime = config.get("runtime", {})
    home_url = config.get("home_url", "https://chatgpt.com/")
    if provider_type in ("chatgpt_web", "zai_web", "deepseek_web", "qwen_web"):
        if not runtime.get("cdp_url"):
            runtime["cdp_url"] = "http://127.0.0.1:9330"
        if not runtime.get("profile_dir"):
            runtime["profile_dir"] = ".runtime-dev/shared-profile"
        if not runtime.get("home_url"):
            runtime["home_url"] = home_url
        config["runtime"] = runtime
    new_provider = {
        "id": provider_id,
        "type": provider_type,
        "enabled": bool(data.get("enabled", True)),
        "priority": int(data.get("priority", 50)),
        "config": config,
        "feature_defaults": data.get("feature_defaults", {"thinking": False, "search": False}),
        "feature_controls": data.get("feature_controls", {"thinking": False, "search": False}),
    }
    # Append to config.yaml
    cfg = _load_config_file()
    providers_list = cfg.setdefault("providers", [])
    if any(p.get("id") == provider_id for p in providers_list):
        return jsonify({"error": f"Provider {provider_id} already exists"}), 409
    providers_list.append(new_provider)
    _save_config_file(cfg)
    _sync_auth_keys()
    try:
        restart = _schedule_restart_all(f"provider-added:{provider_id}")
    except Exception as e:
        restart = {"scheduled": False, "error": str(e), "warning": "Config saved but restart not scheduled"}
    return jsonify({"success": True, "provider": new_provider, "restart": restart}), 201


@control_panel_bp.route('/api/providers/<provider_id>', methods=['DELETE'])
def api_provider_delete(provider_id):
    """Remove a provider from config.yaml."""
    cfg = _load_config_file()
    providers_list = cfg.get("providers", [])
    original_len = len(providers_list)
    cfg["providers"] = [p for p in providers_list if p.get("id") != provider_id]
    if len(cfg["providers"]) == original_len:
        return jsonify({"error": f"Provider {provider_id} not found"}), 404
    _save_config_file(cfg)
    _sync_auth_keys()
    try:
        restart = _schedule_restart_all(f"provider-deleted:{provider_id}")
    except Exception as e:
        restart = {"scheduled": False, "error": str(e), "warning": "Config saved but restart not scheduled"}
    return jsonify({"success": True, "provider_id": provider_id, "restart": restart})


def _provider_config_entry(provider_id):
    cfg = _load_config_file()
    for item in cfg.get("providers", []) or []:
        if item.get("id") == provider_id:
            return cfg, item
    return cfg, None


def _profile_root():
    return (Path(__file__).parent / ".runtime-dev").resolve()


def _safe_profile_path(value):
    value = str(value or "").strip().replace("/", "\\")
    if not value:
        raise ValueError("profile_dir is required")
    candidate = Path(value)
    absolute = (candidate if candidate.is_absolute() else Path(__file__).parent / candidate).resolve()
    root = _profile_root()
    if absolute != root and root not in absolute.parents:
        raise ValueError("Profile must stay inside .runtime-dev")
    return absolute


def _profile_relative(path):
    return str(path.relative_to(Path(__file__).parent.resolve())).replace("/", "\\")


@control_panel_bp.route('/api/providers/<provider_id>/settings', methods=['PUT'])
def api_provider_settings(provider_id):
    data = request.get_json(force=True) or {}
    cfg, item = _provider_config_entry(provider_id)
    if item is None:
        return jsonify({"error": "Provider not found"}), 404
    if "enabled" in data:
        item["enabled"] = bool(data["enabled"])
    if "priority" in data:
        priority = int(data["priority"])
        if priority < 1 or priority > 100:
            return jsonify({"error": "priority must be between 1 and 100"}), 400
        item["priority"] = priority
    if "profile_dir" in data:
        try:
            profile = _safe_profile_path(data["profile_dir"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        profile.mkdir(parents=True, exist_ok=True)
        rel = _profile_relative(profile)
        item.setdefault("runtime", {})["profile_dir"] = rel
        item.setdefault("config", {})["profile_dir"] = rel
    _save_config_file(cfg)
    live = provider_registry.get(provider_id)
    if live is not None:
        if "enabled" in data:
            live.config.enabled = bool(data["enabled"])
        if "priority" in data:
            live.config.priority = int(data["priority"])
        if "profile_dir" in data:
            live.config.config["profile_dir"] = item.get("config", {}).get("profile_dir", "")
    try:
        restart = _schedule_restart_all(f"provider-settings:{provider_id}")
    except Exception as exc:
        restart = {"scheduled": False, "warning": str(exc)}
    return jsonify({"success": True, "provider": provider_id, "restart": restart})


@control_panel_bp.route('/api/runtime/profiles', methods=['GET', 'POST'])
def api_runtime_profiles():
    root = _profile_root()
    root.mkdir(parents=True, exist_ok=True)
    cfg = _load_config_file()
    assigned = {}
    for item in cfg.get("providers", []) or []:
        value = str((item.get("runtime") or {}).get("profile_dir") or "").strip()
        if value:
            try:
                assigned.setdefault(str(_safe_profile_path(value)), []).append(item.get("id"))
            except ValueError:
                pass
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        name = str(data.get("name") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
            return jsonify({"error": "Profile name may contain letters, numbers, dot, underscore and hyphen"}), 400
        path = (root / "profiles" / name).resolve()
        if path.exists():
            return jsonify({"error": "Profile already exists"}), 409
        path.mkdir(parents=True)
        return jsonify({"success": True, "name": name, "profile_dir": _profile_relative(path)}), 201
    paths = set(assigned)
    if root.exists():
        for path in root.iterdir():
            if path.is_dir() and path.name != "profiles":
                paths.add(str(path.resolve()))
        managed = root / "profiles"
        if managed.exists():
            for path in managed.iterdir():
                if path.is_dir():
                    paths.add(str(path.resolve()))
    profiles = []
    for raw in sorted(paths):
        path = Path(raw)
        profiles.append({"name": path.name, "profile_dir": _profile_relative(path), "assigned_to": assigned.get(str(path), [])})
    return jsonify({"profiles": profiles})


@control_panel_bp.route('/api/runtime/profiles/<profile_name>', methods=['DELETE'])
def api_runtime_profile_delete(profile_name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", profile_name):
        return jsonify({"error": "Invalid profile name"}), 400
    path = (_profile_root() / "profiles" / profile_name).resolve()
    try:
        _safe_profile_path(path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    cfg = _load_config_file()
    users = []
    for item in cfg.get("providers", []) or []:
        value = str((item.get("runtime") or {}).get("profile_dir") or "").strip()
        if value:
            try:
                if _safe_profile_path(value) == path:
                    users.append(item.get("id"))
            except ValueError:
                pass
    if users:
        return jsonify({"error": "Profile is assigned and cannot be deleted", "assigned_to": users}), 409
    if not path.exists():
        return jsonify({"error": "Profile not found"}), 404
    shutil.rmtree(path)
    return jsonify({"success": True, "name": profile_name})


@control_panel_bp.route('/api/providers/<provider_id>/features', methods=['GET', 'PUT'])
def api_provider_features(provider_id):
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404
    if request.method == 'GET':
        return jsonify({"provider": provider_id, "features": provider_feature_state(provider)})
    data = request.get_json(force=True) or {}
    try:
        state = persist_provider_feature_defaults(provider, data, CONFIG_PATH)
        return jsonify({"success": True, "provider": provider_id, "features": state})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Failed to update provider feature defaults")
        return jsonify({"error": str(exc)}), 500


@control_panel_bp.route('/api/providers/<provider_id>/model', methods=['PUT'])
def api_provider_model(provider_id):
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404
    data = request.get_json(force=True) or {}
    model = str(data.get("default_upstream_model") or data.get("model") or "").strip()
    if not model:
        return jsonify({"error": "default_upstream_model is required"}), 400
    options = _provider_model_state(provider).get("options", [])
    if options and model not in options:
        return jsonify({"error": "Model is not in selectable options", "options": options}), 400
    if not _persist_provider_config_value(provider_id, "default_upstream_model", model):
        return jsonify({"error": "Provider not found in config"}), 404
    return jsonify({
        "success": True,
        "provider": provider_id,
        "model": _provider_model_state(provider),
    })

@control_panel_bp.route('/api/sessions')
def api_sessions():
    sessions = mcp_session_manager.list_sessions()
    return jsonify({"sessions": sessions})

def _request_bucket(endpoint):
    endpoint = str(endpoint or "")
    if endpoint.startswith("/panel/"):
        return "panel"
    if endpoint.startswith("/v1/chat/") or endpoint.startswith("/v1/responses"):
        return "model"
    if endpoint.startswith("/v1/models") or endpoint.startswith("/health") or endpoint.startswith("/ready") or endpoint.startswith("/modes"):
        return "health_metadata"
    return "other"


def _build_request_history_window(now=None, minutes=60):
    now = time.time() if now is None else now
    end_minute = int(now // 60) * 60
    start_minute = end_minute - ((minutes - 1) * 60)
    minute_counts = {start_minute + (i * 60): 0 for i in range(minutes)}
    requests_1h = 0
    breakdown = {"success": 0, "failure": 0}
    audit_log = "logs/audit.log"

    if os.path.exists(audit_log):
        with open(audit_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("event") != "request_complete":
                        continue
                    ts = float(entry.get("timestamp", 0) or 0)
                    minute = int(ts // 60) * 60
                    if start_minute <= minute <= end_minute:
                        endpoint = str(entry.get("endpoint") or "")
                        provider = str(entry.get("provider") or "unknown")
                        if _request_bucket(endpoint) != "model" or provider in ("", "unknown", "default"):
                            continue
                        requests_1h += 1
                        status_code = int(entry.get("status_code", 0) or 0)
                        outcome = "success" if 200 <= status_code < 400 else "failure"
                        breakdown[outcome] += 1
                        minute_counts[minute] = minute_counts.get(minute, 0) + 1
                except Exception:
                    pass

    history = [
        {"timestamp": minute, "count": minute_counts.get(minute, 0)}
        for minute in sorted(minute_counts)
    ]
    return {"requests_1h": requests_1h, "requests_history": history, "breakdown": breakdown}


@control_panel_bp.route('/api/stats')
def api_stats():
    return jsonify(_build_request_history_window())

def _model_usage_window(now=None, seconds=3600):
    """Return measured model usage for the dashboard.

    Do not fabricate zero-request rows as statistics. Configured providers are
    returned separately as monitored targets; the models array contains only
    measured chat traffic from audit events.
    """
    now = time.time() if now is None else now
    start = now - seconds
    audit_log = "logs/audit.log"
    by_key = {}
    monitored = []
    excluded = {"panel": 0, "health_metadata": 0, "other": 0}
    chat_endpoints = ("/v1/chat/completions", "/v1/chat/code", "/v1/chat/conversation", "/v1/responses")

    try:
        for provider in provider_registry.list_providers(enabled_only=False):
            model_state = _provider_model_state(provider)
            monitored.append({
                "provider": provider.provider_id,
                "model": model_state.get("default") or provider.provider_id,
            })
    except Exception:
        pass

    def ensure_row(provider, model):
        key = (provider, model)
        return by_key.setdefault(key, {
            "provider": provider,
            "model": model,
            "requests": 0,
            "success_count": 0,
            "failure_count": 0,
            "latency_total_ms": 0,
            "latency_samples": 0,
            "avg_latency_ms": None,
            "last_activity": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "tokens_available": False,
            "tokens_estimated": False,
            "prompt_tokens_available": False,
            "completion_tokens_available": False,
            "total_tokens_available": False,
        })

    if os.path.exists(audit_log):
        with open(audit_log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("event") != "request_complete":
                        continue
                    ts = float(entry.get("timestamp", 0) or 0)
                    if ts < start or ts > now:
                        continue
                    endpoint = str(entry.get("endpoint") or "")
                    if not any(endpoint.startswith(prefix) for prefix in chat_endpoints):
                        bucket = _request_bucket(endpoint)
                        if bucket in excluded:
                            excluded[bucket] += 1
                        else:
                            excluded["other"] += 1
                        continue
                    provider = str(entry.get("provider") or "unknown")
                    model = str(entry.get("model") or "unknown")
                    if provider == "unknown" and model == "unknown":
                        continue
                    row = ensure_row(provider, model)
                    row["requests"] += 1
                    status_code = int(entry.get("status_code", 0) or 0)
                    if 200 <= status_code < 400:
                        row["success_count"] += 1
                    else:
                        row["failure_count"] += 1
                    latency_ms = int(entry.get("latency_ms", 0) or 0)
                    if latency_ms >= 0:
                        row["latency_total_ms"] += latency_ms
                        row["latency_samples"] += 1
                    row["last_activity"] = max(float(row["last_activity"] or 0), ts)
                    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        value = int(entry.get(field, 0) or 0)
                        row[field] += value
                        if value > 0:
                            row["tokens_available"] = True
                            row[field + "_available"] = True
                    if entry.get("usage_estimated") is True:
                        row["tokens_estimated"] = True
                except Exception:
                    pass
    for row in by_key.values():
        if row["latency_samples"]:
            row["avg_latency_ms"] = round(row["latency_total_ms"] / row["latency_samples"])
        row.pop("latency_total_ms", None)
        row.pop("latency_samples", None)
    rows = sorted(by_key.values(), key=lambda r: (r["total_tokens"], r["requests"], r["provider"]), reverse=True)
    return {
        "window_seconds": seconds,
        "models": rows,
        "monitored": monitored,
        "excluded": excluded,
        "status": "measured" if rows else "no_measured_traffic",
    }


@control_panel_bp.route('/api/model_usage')
def api_model_usage():
    return jsonify(_model_usage_window())


@control_panel_bp.route('/api/logs/<log_type>')
def api_logs(log_type):
    log_files = {
        "bridge": "logs/bridge.log",
        "audit": "logs/audit.log",
        "service_stdout": "logs/service_stdout.log",
        "service_stderr": "logs/service_stderr.log"
    }
    path = log_files.get(log_type, "logs/bridge.log")
    content = ""
    if os.path.exists(path):
        with open(path, 'r') as f:
            lines = f.readlines()
            content = "".join(lines[-100:])  # Last 100 lines
    return jsonify({"content": content})

def _config_summary_from_dict(config):
    providers=[]
    for item in config.get("providers", []) or []:
        pcfg=item.get("config", {}) or {}
        runtime=item.get("runtime", {}) or {}
        fdefaults=item.get("feature_defaults", {}) or {}
        providers.append({
            "id": item.get("id", ""),
            "enabled": bool(item.get("enabled", True)),
            "priority": item.get("priority", 0),
            "cdp_url": runtime.get("cdp_url") or pcfg.get("cdp_url", ""),
            "default_upstream_model": pcfg.get("default_upstream_model") or pcfg.get("upstream_model") or item.get("id", ""),
            "thinking": bool(fdefaults.get("thinking", False)),
            "search": bool(fdefaults.get("search", False)),
        })
    return {
        "server": {
            "host": config.get("server", {}).get("host", ""),
            "port": config.get("server", {}).get("port", 0),
            "debug": bool(config.get("server", {}).get("debug", False)),
            "threads": config.get("server", {}).get("threads", 0),
            "provider_concurrency": config.get("server", {}).get("provider_concurrency", 0),
        },
        "cdp": {
            "url": config.get("cdp", {}).get("url", ""),
            "timeout": config.get("cdp", {}).get("timeout", 0),
        },
        "auth": {"enabled": bool(config.get("governance", {}).get("auth", {}).get("enabled", False))},
        "providers": providers,
    }


def _apply_config_summary(config, data):
    server=data.get("server", {}) or {}; cdp=data.get("cdp", {}) or {}; auth=data.get("auth", {}) or {}
    config.setdefault("server", {})
    for key in ("host", "port", "debug", "threads", "provider_concurrency"):
        if key in server: config["server"][key]=server[key]
    config.setdefault("cdp", {})
    for key in ("url", "timeout"):
        if key in cdp: config["cdp"][key]=cdp[key]
    config.setdefault("governance", {}).setdefault("auth", {})
    if "enabled" in auth: config["governance"]["auth"]["enabled"]=bool(auth["enabled"])
    incoming={p.get("id"):p for p in data.get("providers", []) or [] if p.get("id")}
    for item in config.get("providers", []) or []:
        pid=item.get("id")
        if pid not in incoming: continue
        src=incoming[pid]
        if "enabled" in src: item["enabled"]=bool(src["enabled"])
        if "priority" in src: item["priority"]=int(src["priority"])
        pcfg=item.setdefault("config", {})
        if "cdp_url" in src:
            new_cdp_url=str(src.get("cdp_url") or "")
            pcfg["cdp_url"]=new_cdp_url
            runtime=item.get("runtime", {}) or {}
            if runtime.get("kind") == "chrome_cdp":
                item.setdefault("runtime", {})["cdp_url"]=new_cdp_url
        model=str(src.get("default_upstream_model") or "").strip()
        if model: pcfg["default_upstream_model"]=model
        fdefaults=item.setdefault("feature_defaults", {})
        if "thinking" in src: fdefaults["thinking"]=bool(src["thinking"])
        if "search" in src: fdefaults["search"]=bool(src["search"])
    return config




@control_panel_bp.route('/api/restart/status', methods=['GET'])
def api_restart_status():
    return jsonify(_restart_state())

@control_panel_bp.route('/api/config/summary', methods=['GET', 'PUT'])
def api_config_summary():
    config=_load_config_file()
    if request.method == 'GET':
        return jsonify(_config_summary_from_dict(config))
    data=request.get_json(force=True) or {}
    try:
        updated=_apply_config_summary(config, data)
        _save_config_file(updated); _sync_auth_keys()
        restart = _schedule_restart_all("config-summary-save")
        return jsonify({"success": True, "summary": _config_summary_from_dict(updated), "restart": restart})
    except Exception as exc:
        logger.exception("Failed to save config summary")
        return jsonify({"error": str(exc)}), 400


@control_panel_bp.route('/api/config', methods=['GET', 'PUT'])
def api_config():
    config_path = "config.yaml"
    if request.method == 'GET':
        content = ""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
        return jsonify({"content": content})
    else:
        data = request.get_json(force=True)
        content = data.get("content", "")
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({"error": f"YAML parse error: {e}"}), 400
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        _sync_auth_keys()
        restart = _schedule_restart_all("raw-config-save")
        return jsonify({"success": True, "restart": restart})

@control_panel_bp.route('/api/providers/runtime/<provider_id>/<action>', methods=['POST'])
def api_provider_runtime_action(provider_id, action):
    valid_actions = {'start', 'restart', 'repair'}
    if action not in valid_actions:
        return jsonify({'error': 'Invalid runtime action'}), 400
    runtimes = inventory_by_id(CONFIG_PATH)
    if provider_id == 'all':
        selected = list(runtimes.values()) if action == 'repair' else [r for r in runtimes.values() if r.get('enabled')]
    else:
        runtime = runtimes.get(provider_id)
        if not runtime:
            return jsonify({'error': 'Provider runtime is not configured'}), 404
        selected = [runtime]
    agent_base = str(load_orchestration_settings(CONFIG_PATH)['desktop_agent_url']).rstrip('/')
    results = []
    ok = True
    for runtime in selected:
        pid = runtime['id']
        try:
            req = urllib.request.Request(
                f"{agent_base}/providers/{urllib.parse.quote(pid)}/{urllib.parse.quote(action)}",
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=65) as response:
                body = json.loads(response.read().decode('utf-8') or '{}')
                item_ok = 200 <= response.status < 300 and body.get('ok') is True
                results.append({'provider': pid, 'success': item_ok, 'response': body})
                ok = ok and item_ok
        except Exception as exc:
            ok = False
            results.append({'provider': pid, 'success': False, 'error': type(exc).__name__})
    return jsonify({
        'success': ok,
        'action': action,
        'provider': provider_id,
        'message': ('Runtime action completed' if ok else 'One or more runtime actions failed'),
        'results': results,
    }), (200 if ok else 503)


@control_panel_bp.route('/api/providers/<provider_id>/open', methods=['POST'])
def api_open_provider_browser(provider_id):
    runtime = inventory_by_id(CONFIG_PATH).get(provider_id)
    if not runtime:
        return jsonify({"error": "Provider runtime is not configured"}), 404
    home = runtime["home_url"]
    cdp_url = runtime["cdp_url"]
    agent_base = str(load_orchestration_settings(CONFIG_PATH)['desktop_agent_url']).rstrip('/')

    # Primary path: interactive desktop agent in the logged-in user session.
    try:
        req = urllib.request.Request(
            f"{agent_base}/providers/{urllib.parse.quote(provider_id)}/open",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            body = json.loads(response.read().decode("utf-8") or "{}")
            if 200 <= response.status < 300 and body.get("ok") is True:
                return jsonify({"success": True, "provider": provider_id, "url": home, "launcher": "desktop_runtime_agent"})
    except Exception as agent_exc:
        logger.warning("Desktop runtime agent open failed for %s: %s", provider_id, agent_exc)

    # Fallback: CDP creates a provider tab; this may not foreground the window.
    if not cdp_url:
        return jsonify({"success": False, "message": "No browser runtime configured"}), 400
    try:
        req = urllib.request.Request(cdp_url + "/json/new?" + urllib.parse.quote(home, safe=":/?=&"), method="PUT")
        with urllib.request.urlopen(req, timeout=3) as response:
            ok = 200 <= response.status < 300
        return jsonify({"success": ok, "provider": provider_id, "url": home, "launcher": "cdp_fallback"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Browser open failed: {type(exc).__name__}"}), 503


@control_panel_bp.route('/api/test_provider/<provider_id>', methods=['POST'])
def api_test_provider(provider_id):
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404

    started = time.time()
    runtime_cfg = inventory_by_id(CONFIG_PATH).get(provider_id)
    cdp_url = runtime_cfg["cdp_url"] if runtime_cfg else provider.config.config.get("cdp_url")
    runtime = _check_cdp(cdp_url)
    ok = runtime.get("ready") is True
    status = runtime.get("status") or ("ready" if ok else "unavailable")
    return jsonify({
        "success": ok,
        "provider": provider_id,
        "check": "cdp_runtime",
        "runtime": runtime,
        "duration_ms": int((time.time() - started) * 1000),
        "message": f"Runtime check: {'OK' if ok else 'FAILED'} ({status})",
    })

@control_panel_bp.route('/api/sessions/<conversation_id>', methods=['DELETE'])
def api_delete_session(conversation_id):
    mcp_session_manager.delete_session(conversation_id)
    return jsonify({"success": True})


def _provider_session_checker(provider):
    """Return the provider's session checker, preferring read-only validation."""
    for name in ("validate_session", "session_status", "_session_status"):
        fn = getattr(provider, name, None)
        if callable(fn):
            return fn
    return None


@control_panel_bp.route('/api/providers/<provider_id>/session')
def api_provider_session(provider_id):
    """Read-only provider login/session validation (NG-ACC-002)."""
    from core.governance import audit_logger
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404
    check = _provider_session_checker(provider)
    if check is None:
        return jsonify({"error": "Session status not supported by provider"}), 501
    loop = current_app.config.get("HWG_ASYNC_LOOP")
    if loop is None or not loop.is_running():
        return jsonify({"error": "Gateway async runtime unavailable"}), 503
    import asyncio
    import concurrent.futures
    started = time.time()
    try:
        future = asyncio.run_coroutine_threadsafe(check(), loop)
        status = future.result(timeout=60)
    except concurrent.futures.TimeoutError:
        return jsonify({"error": "Session check timed out", "provider": provider_id}), 504
    except Exception as exc:
        logger.warning("Provider session check error for %s", provider_id, exc_info=True)
        return jsonify({"error": f"Session check failed: {type(exc).__name__}",
                        "provider": provider_id}), 502
    body = dict(status or {})
    body.update({"provider": provider_id,
                 "checked_at": datetime.now().isoformat(),
                 "duration_ms": int((time.time() - started) * 1000)})
    audit_logger.log({"event": "provider_session_checked", "provider": provider_id,
                      "authenticated": bool(body.get("authenticated"))})
    return jsonify(body)


@control_panel_bp.route('/api/providers/<provider_id>/logout', methods=['POST'])
def api_provider_logout(provider_id):
    """Clear the provider site session (explicit logout, NG-ACC-002).

    Requires {"confirm": true}. Uses CDP Storage.clearDataForOrigin on the
    provider origin; the audit log records the event (never secrets).
    """
    from core.governance import audit_logger
    from urllib.parse import urlparse
    body = request.get_json(force=True, silent=True) or {}
    if body.get("confirm") is not True:
        return jsonify({"error": "Logout requires explicit confirmation",
                        "hint": 'POST {"confirm": true}'}), 400
    runtime = inventory_by_id(CONFIG_PATH).get(provider_id)
    if not runtime:
        return jsonify({"error": "Provider runtime is not configured"}), 404
    origin = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(runtime["home_url"]))
    cdp_url = runtime["cdp_url"]
    loop = current_app.config.get("HWG_ASYNC_LOOP")
    if loop is None or not loop.is_running():
        return jsonify({"error": "Gateway async runtime unavailable"}), 503
    import asyncio
    import concurrent.futures
    try:
        future = asyncio.run_coroutine_threadsafe(_logout_origin(cdp_url, origin), loop)
        cleared = future.result(timeout=120)
    except concurrent.futures.TimeoutError:
        return jsonify({"success": False, "provider": provider_id,
                        "message": "Logout timed out"}), 504
    except Exception as exc:
        return jsonify({"success": False, "provider": provider_id,
                        "message": f"Logout failed: {type(exc).__name__}"}), 503
    audit_logger.log({"event": "provider_logout", "provider": provider_id,
                      "origin": origin, "cleared": cleared})
    return jsonify({"success": True, "provider": provider_id,
                    "origin": origin, "cleared": cleared,
                    "message": "Session cleared. Re-login via Open Browser."})


async def _logout_origin(cdp_url: str, origin: str) -> dict:
    """Clear cookies + storages for origin in the shared browser (Playwright)."""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=20000)
        ctx = browser.contexts[0] if browser.contexts else None
        if ctx is None:
            raise RuntimeError("No browser context")
        await ctx.clear_cookies()
        page = await ctx.new_page()
        async def _dismiss_dialog(dialog):
            try:
                await dialog.dismiss()
            except Exception:
                pass
        page.on("dialog", _dismiss_dialog)
        try:
            await page.goto(origin, wait_until="domcontentloaded", timeout=30000)
            await page.evaluate("() => { try { localStorage.clear(); } catch (e) {}"
                                " try { sessionStorage.clear(); } catch (e) {} }")
            await page.evaluate("""async () => {
                  try {
                    const dbs = await indexedDB.databases();
                    await Promise.all(dbs.map(d => new Promise((res) => {
                      try { const r = indexedDB.deleteDatabase(d.name);
                        r.onsuccess = res; r.onerror = res; r.onblocked = res;
                      } catch (e) { res(); }
                    })));
                  } catch (e) {}
                }""")
            left = await page.evaluate("() => ({cookies: document.cookie.length,"
                                       " ls: Object.keys(localStorage).length})")
        finally:
            page.remove_listener("dialog", _dismiss_dialog)
            await page.close()
        return {"cookies_chars_left": left["cookies"], "localstorage_keys_left": left["ls"]}
    finally:
        await pw.stop()


@control_panel_bp.route('/api/auth/keys')
def api_list_api_keys():
    _sync_auth_keys()
    config = _load_config_file()
    raw_keys = config.get("governance", {}).get("auth", {}).get("api_keys", {}) or {}
    auth_enabled = config.get("governance", {}).get("auth", {}).get("enabled", False)
    created_at = _get_key_created_at()
    keys = []
    for key, identity in raw_keys.items():
        keys.append({
            "key": key,
            "identity": identity if isinstance(identity, str) else identity.get("identity", str(identity)),
            "created_at": created_at.get(key, "-"),
        })
    return jsonify({
        "auth_enabled": auth_enabled,
        "api_keys": keys,
    })


def _get_key_created_at():
    """Load key creation timestamps from logs/audit.log entries."""
    created = {}
    audit_log = Path(__file__).parent / "logs" / "audit.log"
    if not audit_log.exists():
        return created
    try:
        with open(audit_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "api_key_created":
                        key = entry.get("key_ref") or entry.get("api_key", "")
                        if key:
                            ts = entry.get("timestamp", 0)
                            created[key] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                except (json.JSONDecodeError, KeyError):
                    pass
    except Exception:
        pass
    return created


@control_panel_bp.route('/api/auth/keys', methods=['POST'])
def api_add_api_key():
    from core.key_hash import hash_token
    token = secrets.token_urlsafe(24)
    ref = hash_token(token)  # only the hash is persisted; secret shown once below
    identity = f"user-{secrets.token_hex(3)}"
    config = _load_config_file()
    auth_section = config.setdefault("governance", {}).setdefault("auth", {})
    if not auth_section.get("api_keys"):
        auth_section["api_keys"] = {}
    auth_section["api_keys"][ref] = identity
    auth_section["enabled"] = True
    _save_config_file(config)
    _sync_auth_keys()
    auth_manager.add_key(token, identity)
    from core.governance import audit_logger
    audit_logger.log({
        "event": "api_key_created",
        "key_ref": ref,
        "key_suffix": token[-4:],
        "identity": identity,
    })
    return jsonify({"success": True, "key": token, "identity": identity})


@control_panel_bp.route('/api/auth/keys/<path:key>', methods=['DELETE'])
def api_delete_api_key(key):
    config = _load_config_file()
    auth_section = config.get("governance", {}).get("auth", {})
    keys = auth_section.get("api_keys", {}) or {}
    if key not in keys:
        return jsonify({"error": "Key not found"}), 404
    del keys[key]
    _save_config_file(config)
    _sync_auth_keys()
    return jsonify({"success": True, "message": f"Deleted key ending in {key[-8:]}"})


@control_panel_bp.route('/api/auth/settings', methods=['GET', 'POST'])
def api_auth_settings():
    config = _load_config_file()
    auth_section = config.setdefault("governance", {}).setdefault("auth", {})
    if request.method == 'GET':
        return jsonify({
            "enabled": auth_section.get("enabled", False),
        })
    data = request.get_json(force=True)
    auth_section["enabled"] = data.get("enabled", False)
    _save_config_file(config)
    _sync_auth_keys()
    return jsonify({"success": True})


@control_panel_bp.route('/api/service/status')
def api_service_status():
    success, output = _run_service_manager("status")
    payload = _service_status_payload(output)
    payload["success"] = success
    return jsonify(payload)


@control_panel_bp.route('/api/service/restart/status', methods=['GET'])
def api_service_restart_status():
    return jsonify(_gateway_restart_state())


@control_panel_bp.route('/api/service/<action>', methods=['POST'])
def api_service_action(action):
    if action not in ("start", "stop", "restart"):
        return jsonify({"error": "Invalid action"}), 400
    if action == "restart":
        try:
            restart = _schedule_gateway_restart("panel-service-restart")
            return jsonify({"success": True, "action": action, "restart": restart}), 202
        except Exception as exc:
            logger.exception("Failed to schedule independent gateway restart")
            return jsonify({"success": False, "action": action, "error": str(exc)}), 500
    success, output = _run_service_manager(action)
    payload = _service_status_payload(output)
    payload["success"] = success
    payload["action"] = action
    return jsonify(payload)

