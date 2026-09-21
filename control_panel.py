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
from core.profile_contract import project_ng_inventory
from core.profile_store import load_ng_inventory, migrate_legacy_inventory, rollback_legacy_migration, update_account_session, reconcile_isolation_metadata
from core.work_register import load_register, summarize_register, validate_register
from core.discovery_orchestrator import (
    attach_baseline as discovery_attach_baseline,
    attach_exploration as discovery_attach_exploration,
    attach_research as discovery_attach_research,
    begin_certification as discovery_begin_certification,
    begin_exploration as discovery_begin_exploration,
    complete_certification as discovery_complete_certification,
    list_runs as list_discovery_runs,
    load_run as load_discovery_run,
    new_run as new_discovery_run,
    review_candidate as discovery_review_candidate,
    synthesize as discovery_synthesize,
    request_rebaseline as discovery_request_rebaseline,
)
from core.discovery_runtime import explore_cdp as discovery_explore_cdp, probe_cdp_behavior as discovery_probe_cdp_behavior
from core.provider_self_use_gate import self_use_status as provider_self_use_status
from core.self_use_roundtrip_probe import controlled_roundtrip as controlled_self_use_roundtrip
from core.browser_behavior_probe import BehaviorAction, ProbePolicy
from core.discovery_ai_service import execute_ai_assistance
from core.blind_discovery import probe_auth_cdp as discovery_probe_auth_cdp
from core.account_session import normalize_session
from core.functional_readiness import run_functional_probe, save_readiness, load_readiness, invalidate_readiness

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
        "readiness": load_readiness(provider.provider_id) or {"state":"UNKNOWN","ready":False,"current":False},
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


def _desktop_agent_status():
    settings = load_orchestration_settings(CONFIG_PATH)
    url = str(settings.get("desktop_agent_url") or "").rstrip("/")
    task = str(settings.get("desktop_agent_task") or "")
    reachable = False
    try:
        with urllib.request.urlopen(url + "/health", timeout=1.5) as response:
            reachable = 200 <= response.status < 300
    except Exception:
        reachable = False
    task_exists = False
    if task:
        try:
            result = subprocess.run(["schtasks", "/Query", "/TN", task], capture_output=True, text=True, timeout=4)
            task_exists = result.returncode == 0
        except Exception:
            task_exists = False
    return {"url": url, "reachable": reachable, "task": task, "task_exists": task_exists}


@control_panel_bp.route('/api/runtime/orchestration')
def api_runtime_orchestration():
    return jsonify({"desktop_agent": _desktop_agent_status()})


@control_panel_bp.route('/api/ng/inventory')
def api_ng_inventory():
    return jsonify(load_ng_inventory(CONFIG_PATH))


@control_panel_bp.route('/api/readiness')
def api_readiness_inventory():
    rows=[]
    for provider in provider_registry.list_providers(enabled_only=False):
        record=load_readiness(provider.provider_id)
        rows.append(record or {"provider_id":provider.provider_id,"state":"UNKNOWN","ready":False,"current":False})
    return jsonify({"providers":rows})


@control_panel_bp.route('/api/providers/<provider_id>/readiness')
def api_provider_readiness(provider_id):
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error":"Provider not found"}), 404
    return jsonify(load_readiness(provider_id) or {"provider_id":provider_id,"state":"UNKNOWN","ready":False,"current":False})


@control_panel_bp.route('/api/providers/<provider_id>/readiness/probe', methods=['POST'])
def api_provider_readiness_probe(provider_id):
    from core.governance import audit_logger
    import asyncio
    import concurrent.futures
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error":"Provider not found"}), 404
    data = request.get_json(silent=True) or {}
    authority = str(data.get("execution_authority") or "")
    if authority not in {"automated_validation","interactive_validation"}:
        return jsonify({"error":"execution_authority_required"}), 400
    runtime_cfg = inventory_by_id(CONFIG_PATH).get(provider_id) or {}
    runtime_state = _check_cdp(runtime_cfg.get("cdp_url"))
    session_body, _session_status = _evaluate_provider_session(provider_id)
    access_info = dict(session_body.get("access") or {})
    access = ((session_body.get("lifecycle") or {}).get("access_state") or "UNKNOWN")
    account_id = session_body.get("account_id")
    page_interactive = bool(access_info.get("page_url")) and not any(
        token in set(access_info.get("evidence") or [])
        for token in ("no_browser_context", "no_provider_page")
    )
    loop = current_app.config.get("HWG_ASYNC_LOOP")
    if loop is None or not loop.is_running():
        return jsonify({"error":"Gateway async runtime unavailable"}), 503
    ttl = max(30, min(3600, int(data.get("ttl_seconds") or 300)))
    feature_observation = {"observed_control_kinds": []}
    if runtime_state.get("ready") and page_interactive and access == "AUTHENTICATED":
        try:
            ff = asyncio.run_coroutine_threadsafe(
                discovery_explore_cdp(provider_id, runtime_cfg.get("cdp_url"), runtime_cfg.get("home_url")), loop)
            findings, _drift = ff.result(timeout=35)
            controls = ((findings.get("frontend") or {}).get("controls") or [])
            feature_observation = {
                "observed_control_kinds": sorted({str(c.get("kind")) for c in controls if c.get("kind")}),
                "page_url": findings.get("page_url"),
            }
        except Exception as exc:
            logger.warning("Readiness feature observation failed for %s", provider_id, exc_info=True)
            feature_observation = {"observed_control_kinds": [], "error": type(exc).__name__}
    try:
        future = asyncio.run_coroutine_threadsafe(
            run_functional_probe(provider, account_id=account_id,
                                 runtime_ready=bool(runtime_state.get("ready")),
                                 page_interactive=page_interactive,
                                 access_state=access,
                                 feature_observation=feature_observation,
                                 ttl_seconds=ttl), loop)
        record = dict(future.result(timeout=110))
    except concurrent.futures.TimeoutError:
        return jsonify({"error":"readiness_probe_timeout","provider":provider_id}), 504
    except Exception as exc:
        logger.warning("Functional readiness probe failed for %s", provider_id, exc_info=True)
        return jsonify({"error":f"readiness_probe_failed:{type(exc).__name__}","provider":provider_id}), 502
    record["execution_authority"] = authority
    record["runtime"] = runtime_state
    record["access_state"] = access
    record["page_interactive"] = page_interactive
    record["feature_observation"] = feature_observation
    save_readiness(record)
    audit_logger.log({"event":"functional_readiness_probe","provider":provider_id,
                      "account_id":account_id,"state":record.get("state"),"ready":record.get("ready")})
    return jsonify(record)


@control_panel_bp.route('/api/ng/migrate', methods=['POST'])
def api_ng_migrate():
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") is not True:
        return jsonify({"error":"confirmation_required","message":"Persistent NG migration requires confirm=true"}), 400
    try:
        return jsonify(migrate_legacy_inventory(CONFIG_PATH)), 201
    except FileExistsError as exc:
        return jsonify({"error":"already_migrated","message":str(exc)}), 409


@control_panel_bp.route('/api/ng/reconcile-isolation', methods=['POST'])
def api_ng_reconcile_isolation():
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") is not True:
        return jsonify({"error":"confirmation_required","message":"Isolation metadata reconciliation requires confirm=true"}), 400
    try:
        return jsonify(reconcile_isolation_metadata(CONFIG_PATH))
    except FileNotFoundError as exc:
        return jsonify({"error":"persistent_store_not_initialized","message":str(exc)}), 404


@control_panel_bp.route('/api/ng/rollback', methods=['POST'])
def api_ng_rollback():
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") is not True:
        return jsonify({"error":"confirmation_required","message":"NG migration rollback requires confirm=true"}), 400
    try:
        result = rollback_legacy_migration()
        return jsonify({"rollback":result,"inventory":load_ng_inventory(CONFIG_PATH)})
    except FileNotFoundError as exc:
        return jsonify({"error":"migration_not_found","message":str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error":"rollback_refused","message":str(exc)}), 409


@control_panel_bp.route('/api/governance/work-register')
def api_governance_work_register():
    doc = load_register()
    errors = validate_register(doc)
    return jsonify({
        "valid": not errors,
        "errors": errors,
        "summary": summarize_register(doc),
        "items": doc.get("items", []),
    })


@control_panel_bp.route('/api/discovery/runs', methods=['GET', 'POST'])
def api_discovery_runs():
    if request.method == 'GET':
        statuses = {}
        for provider in provider_registry.list_providers(enabled_only=False):
            statuses[provider.provider_id] = provider_self_use_status(provider)
        return jsonify({"runs": list_discovery_runs(), "self_use": statuses})
    payload = request.get_json(silent=True) or {}
    provider_id = str(payload.get("provider_id") or "").strip()
    account_id = str(payload.get("account_id") or "").strip() or None
    recipe_version = str(payload.get("recipe_version") or "webchat-standard-v1").strip()
    known = {x.get("provider_id") for x in load_ng_inventory(CONFIG_PATH).get("provider_profiles", [])}
    if provider_id not in known:
        return jsonify({"error": "unknown_provider", "message": "Provider is not registered in the NG inventory"}), 404
    run = new_discovery_run(provider_id, recipe_version, account_id)
    path = run.save()
    return jsonify({"run": run.to_dict(), "record": str(path), "next_required": "attach_research"}), 201


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/research', methods=['POST'])
def api_discovery_research(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    sources = payload.get("sources") or []
    try:
        run = load_discovery_run(provider_id, run_id)
        discovery_attach_research(run, sources)
        path = run.save()
        return jsonify({"run": run.to_dict(), "record": str(path), "next_required": "capture_baseline"})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/baseline', methods=['POST'])
def api_discovery_baseline(provider_id, run_id):
    try:
        run = load_discovery_run(provider_id, run_id)
        item = inventory_by_id(CONFIG_PATH).get(provider_id)
        if not item:
            return jsonify({"error": "runtime_not_found"}), 404
        runtime = _check_cdp(item.get("cdp_url"))
        pages = []
        if runtime.get("ready"):
            try:
                with urllib.request.urlopen(item.get("cdp_url").rstrip("/") + "/json", timeout=2) as response:
                    pages = json.loads(response.read().decode("utf-8"))
            except Exception:
                pages = []
        session = {"state": "unknown", "supported": False, "access_state": "UNKNOWN"}
        provider = provider_registry.get(provider_id)
        check = _provider_session_checker(provider) if provider else None
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is not None and loop.is_running() and runtime.get("ready"):
            import asyncio
            access_future = asyncio.run_coroutine_threadsafe(discovery_probe_auth_cdp(item.get("cdp_url"), item.get("home_url")), loop)
            access = dict(access_future.result(timeout=30) or {})
            session["access_state"] = str(access.get("state") or "UNKNOWN")
            session["access_evidence"] = access
        if check and loop is not None and loop.is_running():
            import asyncio
            future = asyncio.run_coroutine_threadsafe(check(), loop)
            provider_session = dict(future.result(timeout=60) or {})
            session.update(provider_session)
            session["supported"] = True
        baseline = {
            "runtime": {"cdp_url": item.get("cdp_url"), "profile": item.get("profile"), "ready": runtime.get("ready"), "status": runtime.get("status")},
            "session": session,
            "page": {"home_url": item.get("home_url"), "targets": [{"url": p.get("url"), "title": p.get("title")} for p in pages[:20]]},
            "account": {"account_id": run.account_id, "provider_id": provider_id},
        }
        if run.state in {"WAITING_FOR_LOGIN", "WAITING_FOR_USER_INTERACTION", "DIAGNOSTIC_REQUIRED", "BLOCKED"}:
            discovery_request_rebaseline(run, "access state re-check requested")
        discovery_attach_baseline(run, baseline)
        path = run.save()
        next_required = "explore" if run.state == "EXPLORATION_READY" else "resolve_access_then_rebaseline"
        return jsonify({"run": run.to_dict(), "record": str(path), "next_required": next_required})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409
    except Exception as exc:
        logger.warning("Discovery baseline failed for %s", provider_id, exc_info=True)
        return jsonify({"error": "baseline_failed", "message": type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/explore', methods=['POST'])
def api_discovery_explore(provider_id, run_id):
    try:
        run = load_discovery_run(provider_id, run_id)
        item = inventory_by_id(CONFIG_PATH).get(provider_id)
        if not item:
            return jsonify({"error": "runtime_not_found"}), 404
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is None or not loop.is_running():
            return jsonify({"error": "async_runtime_unavailable"}), 503
        discovery_begin_exploration(run)
        import asyncio
        future = asyncio.run_coroutine_threadsafe(discovery_explore_cdp(provider_id, item.get("cdp_url"), item.get("home_url")), loop)
        findings, drift = future.result(timeout=45)
        discovery_attach_exploration(run, findings, drift)
        discovery_synthesize(run)
        path = run.save()
        return jsonify({"run": run.to_dict(), "record": str(path), "drift_count": len(drift)})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409
    except Exception as exc:
        logger.warning("Discovery exploration failed for %s", provider_id, exc_info=True)
        return jsonify({"error": "exploration_failed", "message": type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/behavior', methods=['POST'])
def api_discovery_behavior(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        if run.state != "EXPLORATION_READY":
            return jsonify({"error":"invalid_transition","message":"Behavior probes require EXPLORATION_READY"}), 409
        item = inventory_by_id(CONFIG_PATH).get(provider_id)
        if not item:
            return jsonify({"error":"runtime_not_found"}), 404
        kind = str(payload.get("kind") or "").strip().lower()
        selector = str(payload.get("selector") or "").strip()
        purpose = str(payload.get("purpose") or "behavior observation").strip()
        if kind not in {"hover","focus","click"} or not selector:
            return jsonify({"error":"invalid_behavior_request"}), 400
        confirmed = payload.get("confirmed_by_user") is True
        if kind == "click" and not confirmed:
            return jsonify({"error":"user_confirmation_required","message":"Click probes require explicit user confirmation"}), 400
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is None or not loop.is_running():
            return jsonify({"error":"async_runtime_unavailable"}), 503
        action = BehaviorAction(kind=kind, selector=selector, purpose=purpose, risk_class="interactive" if kind == "click" else "read_only")
        policy = ProbePolicy(allow_click=confirmed and kind == "click")
        import asyncio
        future = asyncio.run_coroutine_threadsafe(discovery_probe_cdp_behavior(provider_id, item.get("cdp_url"), item.get("home_url"), action, policy), loop)
        obs = future.result(timeout=30).to_dict()
        run.findings.setdefault("behavior_probes", []).append(obs)
        path = run.save()
        return jsonify({"run":run.to_dict(),"record":str(path),"observation":obs})
    except FileNotFoundError:
        return jsonify({"error":"run_not_found"}), 404
    except PermissionError as exc:
        return jsonify({"error":"behavior_blocked","message":str(exc)}), 403
    except Exception as exc:
        logger.warning("Discovery behavior probe failed for %s", provider_id, exc_info=True)
        return jsonify({"error":"behavior_probe_failed","message":type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/ai-assist', methods=['POST'])
def api_discovery_ai_assist(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        if run.state not in {"EXPLORATION_READY", "UPDATE_CANDIDATE"}:
            return jsonify({"error":"invalid_transition","message":"AI assistance is only available during governed discovery/review"}), 409
        if payload.get("confirmed_by_user") is not True:
            return jsonify({"error":"user_confirmation_required","message":"AI assistance requires explicit user approval"}), 400
        questions = [str(x).strip() for x in (payload.get("unresolved_questions") or []) if str(x).strip()]
        if not questions:
            return jsonify({"error":"unresolved_questions_required"}), 400
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is None or not loop.is_running():
            return jsonify({"error":"async_runtime_unavailable"}), 503
        import asyncio
        future = asyncio.run_coroutine_threadsafe(execute_ai_assistance(
            provider_registry, provider_id, run_id, questions, run.findings,
            user_approved=True,
            routing_policy=str(payload.get("routing_policy") or "least_loaded"),
            exact_provider_id=str(payload.get("provider_id") or "").strip() or None,
            exact_model=str(payload.get("model") or "").strip() or None,
            allow_target_provider=payload.get("allow_target_provider") is True,
        ), loop)
        finding = future.result(timeout=120)
        run.findings.setdefault("ai_assistance", []).append(finding)
        path = run.save()
        return jsonify({"run":run.to_dict(),"record":str(path),"finding":finding})
    except FileNotFoundError:
        return jsonify({"error":"run_not_found"}), 404
    except PermissionError as exc:
        return jsonify({"error":"ai_assistance_blocked","message":str(exc)}), 403
    except LookupError as exc:
        return jsonify({"error":"no_ai_route","message":str(exc)}), 409
    except Exception as exc:
        logger.warning("Discovery AI assistance failed for %s", provider_id, exc_info=True)
        return jsonify({"error":"ai_assistance_failed","message":type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/self-use-qualify', methods=['POST'])
def api_discovery_self_use_qualify(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        if run.state not in {"EXPLORATION_READY", "UPDATE_CANDIDATE", "CERTIFICATION_REQUIRED"}:
            return jsonify({"error":"invalid_transition","message":"Self-use qualification is only available after baseline discovery"}), 409
        provider = provider_registry.get(provider_id)
        if provider is None:
            return jsonify({"error":"provider_not_found"}), 404
        model = str(payload.get("model") or (provider.config.config or {}).get("default_model") or "").strip()
        if not model:
            models = list(getattr(provider.capabilities, "supported_models", []) or [])
            model = str(models[0]) if models else ""
        if not model:
            return jsonify({"error":"model_required"}), 400
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is None or not loop.is_running():
            return jsonify({"error":"async_runtime_unavailable"}), 503
        import asyncio
        future = asyncio.run_coroutine_threadsafe(controlled_self_use_roundtrip(provider, model, execution_authority="automated_validation"), loop)
        result = future.result(timeout=120)
        run.findings.setdefault("self_use_qualification", []).append(result)
        path = run.save()
        code = 200 if result.get("allowed") else 409
        return jsonify({"run":run.to_dict(),"record":str(path),"qualification":result}), code
    except FileNotFoundError:
        return jsonify({"error":"run_not_found"}), 404
    except (PermissionError, ValueError) as exc:
        return jsonify({"error":"self_use_qualification_blocked","message":str(exc)}), 409
    except Exception as exc:
        logger.warning("Discovery self-use qualification failed for %s", provider_id, exc_info=True)
        return jsonify({"error":"self_use_qualification_failed","message":type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/review', methods=['POST'])
def api_discovery_review(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        discovery_review_candidate(run, str(payload.get("decision") or ""), str(payload.get("note") or ""))
        path = run.save()
        return jsonify({"run": run.to_dict(), "record": str(path)})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/certification/start', methods=['POST'])
def api_discovery_certification_start(provider_id, run_id):
    try:
        run = load_discovery_run(provider_id, run_id)
        discovery_begin_certification(run)
        path = run.save()
        return jsonify({"run": run.to_dict(), "record": str(path), "next_required": "automated_or_interactive_certification"})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/certification/auto', methods=['POST'])
def api_discovery_certification_auto(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        if run.state == "CERTIFICATION_REQUIRED":
            discovery_begin_certification(run)
        elif run.state != "CERTIFYING":
            return jsonify({"error":"invalid_transition","message":"Automated certification requires CERTIFICATION_REQUIRED or CERTIFYING"}), 409
        provider = provider_registry.get(provider_id)
        if provider is None:
            return jsonify({"error":"provider_not_found"}), 404
        model = str(payload.get("model") or (provider.config.config or {}).get("default_model") or "").strip()
        if not model:
            models = list(getattr(provider.capabilities, "supported_models", []) or [])
            model = str(models[0]) if models else ""
        if not model:
            return jsonify({"error":"model_required"}), 400
        loop = current_app.config.get("HWG_ASYNC_LOOP")
        if loop is None or not loop.is_running():
            return jsonify({"error":"async_runtime_unavailable"}), 503
        import asyncio
        future = asyncio.run_coroutine_threadsafe(controlled_self_use_roundtrip(provider, model, execution_authority="automated_validation"), loop)
        result = future.result(timeout=120)
        evidence_record = str(result.get("record_path") or "")
        discovery_complete_certification(run, bool(result.get("passed") and result.get("allowed")), evidence_record, False, "automated_validation")
        run.findings.setdefault("automated_certification_probe", []).append(result)
        path = run.save()
        return jsonify({"run":run.to_dict(),"record":str(path),"probe":result}), (200 if run.state == "CERTIFIED" else 409)
    except FileNotFoundError:
        return jsonify({"error":"run_not_found"}), 404
    except (PermissionError, ValueError) as exc:
        return jsonify({"error":"automated_certification_blocked","message":str(exc)}), 409
    except Exception as exc:
        logger.warning("Automated Discovery certification failed for %s", provider_id, exc_info=True)
        return jsonify({"error":"automated_certification_failed","message":type(exc).__name__}), 502


@control_panel_bp.route('/api/discovery/runs/<provider_id>/<run_id>/certification/complete', methods=['POST'])
def api_discovery_certification_complete(provider_id, run_id):
    payload = request.get_json(silent=True) or {}
    try:
        run = load_discovery_run(provider_id, run_id)
        passed = bool(payload.get("passed"))
        evidence_record = str(payload.get("evidence_record") or "").strip()
        confirmed = payload.get("confirmed_by_user") is True
        if passed and not evidence_record:
            return jsonify({"error": "evidence_required", "message": "Passing E2 certification requires an evidence record"}), 400
        discovery_complete_certification(run, passed, evidence_record, confirmed, "interactive_validation")
        path = run.save()
        return jsonify({"run": run.to_dict(), "record": str(path)})
    except FileNotFoundError:
        return jsonify({"error": "run_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_transition", "message": str(exc)}), 409


def _browser_runtime_groups():
    inventory = inventory_by_id(CONFIG_PATH)
    groups = {}
    for item in inventory.values():
        cdp = str(item.get("cdp_url") or "").strip()
        profile = str(item.get("profile") or "").strip()
        key = f"{cdp}|{profile}"
        group = groups.setdefault(key, {
            "runtime_id": f"browser-{len(groups)+1}",
            "runtime_key": key,
            "cdp_url": cdp, "port": item.get("port"), "profile": profile,
            "providers": [],
        })
        group["providers"].append({
            "id": item.get("id"), "label": item.get("label"),
            "home_url": item.get("home_url"), "enabled": item.get("enabled"),
        })
    rows = []
    for group in groups.values():
        live = _check_cdp(group.get("cdp_url"))
        providers = group["providers"]
        group.update({
            "ready": live.get("ready"), "status": live.get("status"),
            "shared": len(providers) > 1, "provider_count": len(providers),
            "representative_provider": providers[0]["id"] if providers else None,
        })
        rows.append(group)
    return rows


@control_panel_bp.route('/api/runtimes')
def api_runtimes():
    # Backward-compatible provider-centric view.
    inventory = inventory_by_id(CONFIG_PATH)
    rows = []
    for item in inventory.values():
        live = _check_cdp(item.get("cdp_url"))
        rows.append({"id": item.get("id"), "label": item.get("label"),
                     "port": item.get("port"), "profile": item.get("profile"),
                     "home_url": item.get("home_url"), "cdp_url": item.get("cdp_url"),
                     "ready": live.get("ready"), "status": live.get("status")})
    return jsonify({"runtimes": rows})


@control_panel_bp.route('/api/browser-runtimes')
def api_browser_runtimes():
    return jsonify({"browser_runtimes": _browser_runtime_groups()})


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


SUPPORTED_BROWSER_PROVIDER_TYPES = {
    "chatgpt_web": {"home_url": "https://chatgpt.com/", "label": "ChatGPT Web"},
    "qwen_web": {"home_url": "https://chat.qwen.ai/", "label": "Qwen Web"},
    "zai_web": {"home_url": "https://chat.z.ai/", "label": "Z.ai Web"},
    "deepseek_web": {"home_url": "https://chat.deepseek.com/", "label": "DeepSeek Web"},
}

def _browser_runtime_by_key(runtime_key):
    for group in _browser_runtime_groups():
        if group.get("runtime_key") == runtime_key:
            return group
    return None

def _provider_adapter_config(provider_type, runtime, home_url):
    cdp = str(runtime.get("cdp_url") or "").strip()
    profile = str(runtime.get("profile") or "").strip()
    base = {"cdp_url": cdp, "require_authenticated": True}
    if provider_type == "chatgpt_web":
        base.update({"chatgpt_url": home_url.rstrip('/'), "adapter": "dom"})
    elif provider_type == "qwen_web":
        base.update({"profile_dir": profile, "transport_mode": "browser_controller"})
    elif provider_type == "zai_web":
        base.update({"profile_dir": profile, "base_url": home_url.rstrip('/'), "transport_mode": "browser_ui_capture"})
    elif provider_type == "deepseek_web":
        base.update({"base_url": home_url, "transport_mode": "browser_ui"})
    return base

@control_panel_bp.route('/api/providers', methods=['GET', 'POST'])
def api_providers():
    if request.method == 'GET':
        providers = provider_registry.list_providers(enabled_only=False)
        return jsonify({"providers": [_provider_payload(p) for p in providers]})

    # POST: create a governed provider definition bound to an existing Browser Runtime.
    data = request.get_json(force=True) or {}
    provider_id = str(data.get("id") or "").strip()
    provider_type = str(data.get("type") or "").strip()
    runtime_key = str(data.get("runtime_key") or "").strip()
    if not provider_id or provider_type not in SUPPORTED_BROWSER_PROVIDER_TYPES:
        return jsonify({"error": "valid id and supported provider type are required"}), 400
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", provider_id):
        return jsonify({"error": "provider id must use lowercase letters, digits, dot, dash or underscore"}), 400
    runtime = _browser_runtime_by_key(runtime_key) if runtime_key else None
    if runtime is None:
        return jsonify({"error": "existing browser runtime selection is required"}), 400
    priority = int(data.get("priority", 50))
    if priority < 1 or priority > 100:
        return jsonify({"error": "priority must be between 1 and 100"}), 400
    spec = SUPPORTED_BROWSER_PROVIDER_TYPES[provider_type]
    home_url = str(data.get("home_url") or spec["home_url"]).strip()
    runtime_doc = {
        "kind": "chrome_cdp",
        "cdp_url": runtime.get("cdp_url"),
        "profile_dir": runtime.get("profile"),
        "home_url": home_url,
        "label": f"HWG-NG-{spec['label'].replace(' ', '-')}",
    }
    adapter_config = _provider_adapter_config(provider_type, runtime, home_url)
    new_provider = {
        "id": provider_id,
        "type": provider_type,
        "enabled": False,
        "priority": priority,
        "runtime": runtime_doc,
        "config": adapter_config,
        "feature_defaults": {"thinking": False, "search": False},
        "feature_controls": {"thinking": False, "search": False},
    }
    cfg = _load_config_file()
    providers_list = cfg.setdefault("providers", [])
    if any(p.get("id") == provider_id for p in providers_list):
        return jsonify({"error": f"Provider {provider_id} already exists"}), 409
    providers_list.append(new_provider)
    _save_config_file(cfg)
    _sync_auth_keys()
    try:
        restart = _schedule_restart_all(f"provider-added:{provider_id}")
    except Exception as exc:
        restart = {"scheduled": False, "error": str(exc), "warning": "Config saved but restart not scheduled"}
    return jsonify({
        "success": True, "provider": new_provider, "restart": restart,
        "next_required": "login_discovery_certification_before_enable"
    }), 201


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
        marker = path / ".hwg-profile.json"
        marker.write_text(json.dumps({
            "name": name,
            "created_at": datetime.now().isoformat(),
            "purpose": "chrome_user_data_dir",
            "state": "empty_until_browser_launch",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({
            "success": True, "name": name, "profile_dir": _profile_relative(path),
            "meaning": "Chrome user-data directory; it becomes useful after browser launch/login",
        }), 201
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
    shared_cfg = (((cfg.get("runtime_orchestration") or {}).get("shared_browser") or {}))
    shared_path = None
    try:
        shared_path = _safe_profile_path(shared_cfg.get("profile_dir")) if shared_cfg.get("profile_dir") else None
    except ValueError:
        shared_path = None
    for raw in sorted(paths):
        path = Path(raw)
        rel = _profile_relative(path)
        users = assigned.get(str(path), [])
        kind = "shared" if shared_path and path == shared_path else ("managed" if "profiles" in path.relative_to(_profile_root()).parts else "legacy")
        initialized = path.exists() and any(path.iterdir())
        profiles.append({
            "name": path.name, "profile_dir": rel, "assigned_to": users,
            "kind": kind, "initialized": initialized, "exists": path.exists(),
            "deletable": not users,
        })
    return jsonify({"profiles": profiles})


@control_panel_bp.route('/api/runtime/profiles', methods=['DELETE'])
def api_runtime_profile_delete_by_path():
    data = request.get_json(force=True) or {}
    try:
        path = _safe_profile_path(data.get("profile_dir"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if path == _profile_root():
        return jsonify({"error": "Runtime profile root cannot be deleted"}), 400
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
        return jsonify({"error": "Profile is assigned; detach providers first", "assigned_to": users}), 409
    if not path.exists():
        return jsonify({"error": "Profile not found"}), 404
    shutil.rmtree(path)
    return jsonify({"success": True, "profile_dir": _profile_relative(path)})


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


def _account_for_provider(provider_id):
    inv = load_ng_inventory(CONFIG_PATH)
    profile_ids = {p.get("profile_id") for p in inv.get("provider_profiles", []) if p.get("provider_id") == provider_id}
    for account in inv.get("account_instances", []):
        if account.get("provider_profile_id") in profile_ids:
            return account, inv.get("authority")
    return None, inv.get("authority")


def _provider_for_account(account_id):
    inv = load_ng_inventory(CONFIG_PATH)
    account = next((a for a in inv.get("account_instances", []) if a.get("account_id") == account_id), None)
    if not account:
        return None, None, inv.get("authority")
    profile_id = account.get("provider_profile_id")
    profile = next((p for p in inv.get("provider_profiles", []) if p.get("profile_id") == profile_id), None)
    return (profile or {}).get("provider_id"), account, inv.get("authority")


def _provider_session_checker(provider):
    """Return the provider's session checker, preferring read-only validation."""
    for name in ("validate_session", "session_status", "_session_status"):
        fn = getattr(provider, name, None)
        if callable(fn):
            return fn
    return None


def _evaluate_provider_session(provider_id):
    from core.governance import audit_logger
    provider = provider_registry.get(provider_id)
    if not provider:
        return {"error": "Provider not found"}, 404
    loop = current_app.config.get("HWG_ASYNC_LOOP")
    if loop is None or not loop.is_running():
        return {"error": "Gateway async runtime unavailable"}, 503
    import asyncio
    import concurrent.futures
    started = time.time()
    runtime = inventory_by_id(CONFIG_PATH).get(provider_id) or {}
    access = {"state": "UNKNOWN", "reason": "structural_probe_unavailable"}
    if runtime.get("cdp_url") and runtime.get("home_url"):
        try:
            af = asyncio.run_coroutine_threadsafe(
                discovery_probe_auth_cdp(runtime["cdp_url"], runtime["home_url"]), loop)
            access = dict(af.result(timeout=30) or access)
        except concurrent.futures.TimeoutError:
            access = {"state": "UNKNOWN", "reason": "structural_probe_timeout"}
        except Exception:
            logger.warning("Account access probe failed for %s", provider_id, exc_info=True)

    terminal = {"BLOCKED", "LOGIN_REQUIRED", "USER_INTERACTION_REQUIRED"}
    body = {}
    if str(access.get("state") or "UNKNOWN").upper() not in terminal:
        check = _provider_session_checker(provider)
        if check is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(check(), loop)
                body = dict(future.result(timeout=60) or {})
            except concurrent.futures.TimeoutError:
                body = {"authenticated": False, "session_probe": "timeout"}
            except Exception as exc:
                logger.warning("Provider session check error for %s", provider_id, exc_info=True)
                body = {"authenticated": False, "session_probe": f"error:{type(exc).__name__}"}
        else:
            body = {"authenticated": None, "session_probe": "unsupported"}
    account, authority = _account_for_provider(provider_id)
    previous = ((account or {}).get("session") or {}).get("access_state")
    lifecycle = normalize_session(body, access.get("state"), previous)
    persisted = False
    persist_error = None
    if account and authority == "persistent_ng_store":
        try:
            update_account_session(account["account_id"], lifecycle)
            persisted = True
        except Exception as exc:
            persist_error = type(exc).__name__
            logger.warning("Account session persistence failed for %s", provider_id, exc_info=True)
    if lifecycle.get("access_state") != "AUTHENTICATED":
        invalidate_readiness(provider_id, f"session:{lifecycle.get('access_state')}")
    body.update({"provider": provider_id,
                 "account_id": (account or {}).get("account_id"),
                 "checked_at": datetime.now().isoformat(),
                 "duration_ms": int((time.time() - started) * 1000),
                 "access": access,
                 "lifecycle": lifecycle,
                 "persistence": {"authority": authority, "persisted": persisted, "error": persist_error}})
    audit_logger.log({"event": "provider_session_checked", "provider": provider_id,
                      "account_id": body.get("account_id"),
                      "access_state": lifecycle.get("access_state"),
                      "authenticated": lifecycle.get("authenticated")})
    return body, 200


@control_panel_bp.route('/api/providers/<provider_id>/session')
def api_provider_session(provider_id):
    """Read-only provider/account login-session validation (NG-ACC-002)."""
    body, status = _evaluate_provider_session(provider_id)
    return jsonify(body), status


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
    account, authority = _account_for_provider(provider_id)
    persisted = False
    lifecycle = normalize_session({"authenticated": False, "reason": "explicit_logout"}, "LOGIN_REQUIRED")
    if account and authority == "persistent_ng_store":
        try:
            update_account_session(account["account_id"], lifecycle)
            persisted = True
        except Exception:
            logger.warning("Account session persistence failed after logout for %s", provider_id, exc_info=True)
    audit_logger.log({"event": "provider_logout", "provider": provider_id,
                      "account_id": account.get("account_id") if account else None,
                      "origin": origin, "cleared": cleared, "access_state": "LOGIN_REQUIRED"})
    invalidate_readiness(provider_id, "explicit_logout")
    return jsonify({"success": True, "provider": provider_id,
                    "origin": origin, "cleared": cleared, "session": lifecycle,
                    "persistence": {"authority": authority, "persisted": persisted},
                    "message": "Session cleared for this origin. Re-login via Open Browser."})


async def _logout_origin(cdp_url: str, origin: str) -> dict:
    """Clear only the target origin in a shared browser context."""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=20000)
        ctx = browser.contexts[0] if browser.contexts else None
        if ctx is None:
            raise RuntimeError("No browser context")
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "all"})
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


@control_panel_bp.route('/api/accounts/<path:account_id>/session')
def api_account_session(account_id):
    provider_id, account, _authority = _provider_for_account(account_id)
    if not account or not provider_id:
        return jsonify({"error": "Account instance not found"}), 404
    return api_provider_session(provider_id)


@control_panel_bp.route('/api/accounts/<path:account_id>/login/open', methods=['POST'])
def api_account_login_open(account_id):
    provider_id, account, _authority = _provider_for_account(account_id)
    if not account or not provider_id:
        return jsonify({"error": "Account instance not found"}), 404
    return api_open_provider_browser(provider_id)


@control_panel_bp.route('/api/accounts/<path:account_id>/reauth', methods=['POST'])
def api_account_reauth(account_id):
    provider_id, account, _authority = _provider_for_account(account_id)
    if not account or not provider_id:
        return jsonify({"error": "Account instance not found"}), 404
    opened = api_open_provider_browser(provider_id)
    return opened


@control_panel_bp.route('/api/accounts/<path:account_id>/logout', methods=['POST'])
def api_account_logout(account_id):
    provider_id, account, _authority = _provider_for_account(account_id)
    if not account or not provider_id:
        return jsonify({"error": "Account instance not found"}), 404
    return api_provider_logout(provider_id)


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

