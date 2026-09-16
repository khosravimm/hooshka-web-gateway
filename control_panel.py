import os
import json
import time
import logging
import subprocess
import secrets
import yaml
import psutil
import urllib.request
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template_string, jsonify, request
from core.provider_registry import provider_registry
from core.mcp import mcp_session_manager
from core.governance import auth_manager, rate_limiter
from core.config import load_config, deep_merge, get_default_config
from core.feature_settings import persist_provider_feature_defaults, provider_feature_state

control_panel_bp = Blueprint('control_panel', __name__, url_prefix='/panel')

logger = logging.getLogger(__name__)

CONFIG_PATH = str(Path(__file__).parent / "config.yaml")


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
        for root in (Path("D:/Code/hooshka-web-gateway"), Path("D:/Code/mcp-web-bridge")):
            head_path = root / ".git" / "HEAD"
            if not head_path.exists():
                continue
            try:
                head = head_path.read_text(encoding="utf-8").strip()
                if head.startswith("ref:"):
                    ref = head.split(" ", 1)[1].strip()
                    branch = ref.rsplit("/", 1)[-1]
                    ref_path = root / ".git" / ref.replace("/", os.sep)
                    if ref_path.exists():
                        commit = ref_path.read_text(encoding="utf-8").strip()[:7]
                elif head:
                    branch = "detached"
                    commit = head[:7]
                break
            except Exception:
                pass
    return {
        "version": _read_version(),
        "commit": commit,
        "branch": branch,
        "evidence": "E2 Thinking/Search 4x4",
    }


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
    return {
        "id": provider.provider_id,
        "type": provider.provider_type.value,
        "enabled": provider.config.enabled,
        "priority": provider.config.priority,
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

def _run_service_manager(action):
    """Run a service action via the PowerShell script. Returns (success, output)."""
    script = f"""
    $ErrorActionPreference = 'Stop'
    . "{Path(__file__).parent / 'service_manager.ps1'}" {action}
    """
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hooshka Web Gateway - Control Panel</title>
    <link rel="icon" href="data:,">
    <style>
        .hwg-shell { max-width: 1680px !important; }
        .hwg-card { border: 1px solid #e2e8f0; box-shadow: 0 10px 24px rgba(15, 23, 42, .06); }
        .hwg-subtle { color: #cbd5e1; font-size: 12px; font-weight: 500; }
        .hwg-chip { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 700; }
        .hwg-ok { background: #dcfce7; color: #166534; }
        .hwg-bad { background: #fee2e2; color: #991b1b; }
        .hwg-neutral { background: #e2e8f0; color: #334155; }
        .hwg-runtime-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; background: #f8fafc; }
        :root{font-family:Segoe UI,Tahoma,Arial,sans-serif;color:#111827}*{box-sizing:border-box}body{margin:0}button,input,select,textarea{font:inherit}button{border:0;cursor:pointer}button:disabled{opacity:.6;cursor:not-allowed}table{width:100%;border-collapse:collapse}pre,textarea,.font-mono{font-family:Consolas,Cascadia Mono,Courier New,monospace}.max-w-7xl,.hwg-shell{max-width:1680px!important}.mx-auto{margin-left:auto;margin-right:auto}.min-h-screen{min-height:100vh}.min-w-full{min-width:100%}.w-full{width:100%}.bg-white{background:#fff}.bg-gray-50{background:#f9fafb}.bg-gray-100{background:#f3f4f6}.bg-gray-200{background:#e5e7eb}.bg-gray-600{background:#4b5563}.bg-gray-700{background:#374151}.bg-gray-900{background:#111827}.bg-blue-50{background:#eff6ff}.bg-blue-100{background:#dbeafe}.bg-blue-600{background:#2563eb}.bg-green-100{background:#dcfce7}.bg-green-600{background:#16a34a}.bg-red-100{background:#fee2e2}.bg-red-600{background:#dc2626}.bg-purple-100{background:#f3e8ff}.bg-orange-100{background:#ffedd5}.bg-emerald-100{background:#d1fae5}.bg-yellow-100{background:#fef3c7}.text-white{color:#fff}.text-gray-100{color:#f3f4f6}.text-gray-300{color:#d1d5db}.text-gray-500{color:#6b7280}.text-gray-600{color:#4b5563}.text-gray-700{color:#374151}.text-gray-800{color:#1f2937}.text-blue-600{color:#2563eb}.text-blue-700{color:#1d4ed8}.text-green-300{color:#86efac}.text-green-600{color:#16a34a}.text-green-800{color:#166534}.text-red-600{color:#dc2626}.text-red-800{color:#991b1b}.text-purple-600{color:#9333ea}.text-orange-600{color:#ea580c}.text-emerald-600{color:#059669}.text-yellow-800{color:#854d0e}.p-3{padding:.75rem}.p-4{padding:1rem}.p-6{padding:1.5rem}.px-1{padding-left:.25rem;padding-right:.25rem}.px-2{padding-left:.5rem;padding-right:.5rem}.py-1{padding-top:.25rem;padding-bottom:.25rem}.px-3{padding-left:.75rem;padding-right:.75rem}.py-2{padding-top:.5rem;padding-bottom:.5rem}.px-4{padding-left:1rem;padding-right:1rem}.py-3{padding-top:.75rem;padding-bottom:.75rem}.px-6{padding-left:1.5rem;padding-right:1.5rem}.py-4{padding-top:1rem;padding-bottom:1rem}.mt-1{margin-top:.25rem}.mt-6{margin-top:1.5rem}.mb-2{margin-bottom:.5rem}.mb-3{margin-bottom:.75rem}.mb-4{margin-bottom:1rem}.mb-6{margin-bottom:1.5rem}.mb-8{margin-bottom:2rem}.ml-4{margin-left:1rem}.mr-1{margin-right:.25rem}.mr-2{margin-right:.5rem}.flex{display:flex}.inline-flex{display:inline-flex}.grid{display:grid}.hidden{display:none!important}.items-center{align-items:center}.justify-between{justify-content:space-between}.gap-2{gap:.5rem}.gap-3{gap:.75rem}.gap-6{gap:1.5rem}.space-y-3>*+*{margin-top:.75rem}.space-x-4>*+*{margin-left:1rem}.grid-cols-1{grid-template-columns:repeat(1,minmax(0,1fr))}@media(min-width:768px){.md\:grid-cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(min-width:1024px){.lg\:grid-cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}.lg\:grid-cols-5{grid-template-columns:repeat(5,minmax(0,1fr))}}.rounded{border-radius:.375rem}.rounded-lg{border-radius:.5rem}.rounded-full{border-radius:999px}.border{border:1px solid #d1d5db}.border-b{border-bottom:1px solid #e5e7eb}.border-b-2{border-bottom:2px solid transparent}.border-blue-600{border-color:#2563eb}.border-transparent{border-color:transparent}.border-gray-200{border-color:#e5e7eb}.shadow,.shadow-lg{box-shadow:0 10px 24px rgba(15,23,42,.08)}.divide-y>*+*{border-top:1px solid #e5e7eb}.overflow-auto{overflow:auto}.overflow-x-auto{overflow-x:auto}.break-all{word-break:break-all}.text-left{text-align:left}.text-xs{font-size:.75rem;line-height:1rem}.text-sm{font-size:.875rem;line-height:1.25rem}.text-lg{font-size:1.125rem;line-height:1.75rem}.text-2xl{font-size:1.5rem;line-height:2rem}.font-medium{font-weight:500}.font-semibold{font-weight:600}.font-bold{font-weight:700}.uppercase{text-transform:uppercase}.h-32{height:8rem}.h-96{height:24rem}.hover\:bg-blue-700:hover,.hover\:bg-green-700:hover,.hover\:bg-red-700:hover,.hover\:bg-orange-700:hover{filter:brightness(.92)}.hover\:bg-gray-200:hover{background:#e5e7eb}.hover\:underline:hover{text-decoration:underline}.hover\:text-gray-700:hover{color:#374151}.tab-btn{background:transparent}.hwg-icon{display:inline-flex;align-items:center;justify-content:center;width:1.7rem;height:1.7rem;font-weight:800}.hwg-chart-wrap{position:relative;height:250px;width:100%;border:1px solid #e5e7eb;border-radius:10px;background:linear-gradient(#fff,#f8fafc)}#requests-chart{width:100%;height:100%;display:block}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-gray-900 text-white p-4 shadow-lg">
        <div class="hwg-shell max-w-7xl mx-auto flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold"><span class="hwg-icon mr-2">HWG</span>Hooshka Web Gateway Control Panel</h1>
                <div class="hwg-subtle mt-1">Version <b id="meta-version">-</b> | Commit <b id="meta-commit">-</b> | Branch <b id="meta-branch">-</b> | Evidence <b id="meta-evidence">-</b></div>
            </div>
            <div class="flex items-center space-x-4">
                <span id="service-status" class="px-3 py-1 rounded-full text-sm font-medium bg-gray-700">Checking...</span>
                <button onclick="location.reload()" class="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm">
                    <span class="mr-1">[R]</span> Refresh
                </button>
            </div>
        </div>
    </nav>

    <div class="hwg-shell max-w-7xl mx-auto p-6">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-blue-100 rounded-full"><span class="hwg-icon text-blue-600">H</span></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Service Status</p>
                        <p id="stat-service" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-green-100 rounded-full"><span class="hwg-icon text-green-600">P</span></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Providers</p>
                        <p id="stat-providers" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6 hwg-card">
                <div class="flex items-center">
                    <div class="p-3 bg-emerald-100 rounded-full"><span class="hwg-icon text-emerald-600">OK</span></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Ready Providers</p>
                        <p id="stat-ready" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-purple-100 rounded-full"><span class="hwg-icon text-purple-600">S</span></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Active Sessions</p>
                        <p id="stat-sessions" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-orange-100 rounded-full"><span class="hwg-icon text-orange-600">G</span></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Requests (1h)</p>
                        <p id="stat-requests" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="bg-white rounded-lg shadow">
            <div class="border-b border-gray-200">
                <nav class="flex -mb-px" aria-label="Tabs">
                    <button onclick="showTab('overview')" id="tab-overview" class="tab-btn px-6 py-3 border-b-2 border-blue-600 text-blue-600 font-medium">Overview</button>
                    <button onclick="showTab('providers')" id="tab-providers" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">Providers</button>
                    <button onclick="showTab('sessions')" id="tab-sessions" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">Sessions</button>
                    <button onclick="showTab('api_keys')" id="tab-api_keys" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">API Keys</button>
                    <button onclick="showTab('service')" id="tab-service" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">Service</button>
                    <button onclick="showTab('config')" id="tab-config" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">Config</button>
                    <button onclick="showTab('logs')" id="tab-logs" class="tab-btn px-6 py-3 border-b-2 border-transparent text-gray-500 hover:text-gray-700 font-medium">Logs</button>
                </nav>
            </div>

            <!-- Overview Tab -->
            <div id="panel-overview" class="tab-panel p-6">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                        <h3 class="text-lg font-semibold mb-4">System Health</h3>
                        <div id="health-info" class="space-y-3 text-sm">
                            <div class="flex justify-between"><span>API Endpoint</span><span id="health-api" class="font-medium">-</span></div>
                            <div class="flex justify-between"><span>Uptime</span><span id="health-uptime" class="font-medium">-</span></div>
                            <div class="flex justify-between"><span>Memory Usage</span><span id="health-memory" class="font-medium">-</span></div>
                            <div class="flex justify-between"><span>CPU Usage</span><span id="health-cpu" class="font-medium">-</span></div>
                            <div class="flex justify-between"><span>Global Chrome CDP</span><span id="health-cdp" class="font-medium">-</span></div>
                        </div>
                        <h3 class="text-lg font-semibold mt-6 mb-3">Provider Runtime Readiness</h3>
                        <div id="provider-runtime-summary" class="grid grid-cols-1 md:grid-cols-2 gap-3"></div>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold mb-4">Recent Requests</h3>
                        <div class="hwg-chart-wrap">
                            <canvas id="requests-chart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Providers Tab -->
            <div id="panel-providers" class="tab-panel p-6 hidden">
                <h3 class="text-lg font-semibold mb-4">Registered Providers</h3>
                <div id="providers-table" class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Runtime</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Capabilities</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Thinking</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Search</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Default Model</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="providers-body" class="bg-white divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Sessions Tab -->
            <div id="panel-sessions" class="tab-panel p-6 hidden">
                <h3 class="text-lg font-semibold mb-4">Active Conversations</h3>
                <div id="sessions-table" class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Conversation ID</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Provider</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Messages</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Updated</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="sessions-body" class="bg-white divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- API Keys Tab -->
            <div id="panel-api_keys" class="tab-panel p-6 hidden">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">API Key Management</h3>
                    <button onclick="toggleAuth()" id="btn-toggle-auth" class="px-3 py-1 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200">
                        Enable Auth
                    </button>
                </div>
                <div class="mb-4">
                    <span id="auth-status" class="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">Auth Disabled</span>
                </div>
                <div class="mb-4">
                    <button onclick="addApiKey()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                        <span class="mr-1">[+]</span> Generate New Key
                    </button>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">API Key</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Identity</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="api-keys-body" class="bg-white divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Service Tab -->
            <div id="panel-service" class="tab-panel p-6 hidden">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">Service Management</h3>
                    <span id="service-status-badge" class="px-3 py-1 rounded-full text-sm font-medium bg-gray-200">Checking...</span>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h4 class="font-medium mb-2">Action</h4>
                        <div class="flex gap-2">
                            <button onclick="serviceAction('start')" class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Start</button>
                            <button onclick="serviceAction('stop')" class="px-4 py-2 bg-red-600 text-white rounded hover:bg-orange-700">Stop</button>
                            <button onclick="serviceAction('restart')" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Restart</button>
                        </div>
                    </div>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h4 class="font-medium mb-2">Info</h4>
                        <pre id="service-info" class="bg-gray-900 text-green-300 p-3 rounded h-32 overflow-auto text-sm font-mono"></pre>
                    </div>
                </div>
            </div>

            <!-- Logs Tab -->
            <div id="panel-logs" class="tab-panel p-6 hidden">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">Application Logs</h3>
                    <select id="log-select" class="px-3 py-2 border rounded" onchange="loadLogs()">
                        <option value="bridge">bridge.log (Application)</option>
                        <option value="audit">audit.log (Audit JSON)</option>
                        <option value="service_stdout">service_stdout.log</option>
                        <option value="service_stderr">service_stderr.log</option>
                    </select>
                </div>
                <pre id="log-content" class="bg-gray-900 text-green-300 p-4 rounded h-96 overflow-auto text-sm font-mono"></pre>
            </div>

            <!-- Config Tab -->
            <div id="panel-config" class="tab-panel p-6 hidden">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">Configuration (config.yaml)</h3>
                    <div class="flex gap-2">
                        <button onclick="saveConfig()" class="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700">Save</button>
                        <button onclick="loadConfig()" class="px-3 py-1 bg-gray-600 text-white rounded text-sm hover:bg-gray-700">Refresh</button>
                    </div>
                </div>
                <textarea id="config-content" class="bg-gray-900 text-gray-100 p-4 rounded h-96 w-full overflow-auto text-sm font-mono" spellcheck="false"></textarea>
            </div>
        </div>
    </div>
</div>

<script>
// Initial data rendered server-side in dedicated JSON script tags
function readInitialData(id, defaultValue) {
    try {
        var el = document.getElementById(id);
        if (el && el.textContent) return JSON.parse(el.textContent);
    } catch (e) { console.error('Failed to parse initial data ' + id, e); }
    return defaultValue;
}

const INITIAL_HEALTH = readInitialData('data-health', {status: 'error'});
const INITIAL_PROVIDERS = readInitialData('data-providers', {providers: []});
const INITIAL_SESSIONS = readInitialData('data-sessions', {sessions: []});
const INITIAL_STATS = readInitialData('data-stats', {requests_1h: 0, requests_history: []});
const INITIAL_AUTH = readInitialData('data-auth', {auth_enabled: false, api_keys: []});
const INITIAL_SERVICE = readInitialData('data-service', {exists: false, status: 'Unknown', output: ''});
const INITIAL_META = readInitialData('data-meta', {version: '-', commit: '-', branch: '-', evidence: '-'});
const INITIAL_CONFIG = readInitialData('data-config', '');

// Tab management
function showTab(tabName) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('border-blue-600', 'text-blue-600');
        b.classList.add('border-transparent', 'text-gray-500');
    });
    document.getElementById('panel-' + tabName).classList.remove('hidden');
    document.getElementById('tab-' + tabName).classList.remove('border-transparent', 'text-gray-500');
    document.getElementById('tab-' + tabName).classList.add('border-blue-600', 'text-blue-600');
    
    if (tabName === 'providers') loadProviders();
    if (tabName === 'sessions') loadSessions();
    if (tabName === 'api_keys') { if (INITIAL_AUTH) updateApiKeys(INITIAL_AUTH); else loadApiKeys(); }
    if (tabName === 'service') { if (INITIAL_SERVICE) updateServiceStatus(INITIAL_SERVICE); else loadServiceStatus(); }
    if (tabName === 'logs') loadLogs();
    if (tabName === 'config') loadConfig();
}

// API calls
async function api(path) {
    const resp = await fetch('/panel/api' + path);
    return resp.json();
}

// Load all data
async function loadAll() {
    try {
        const results = await Promise.allSettled([
            api('/health'),
            api('/providers'),
            api('/sessions'),
            api('/stats'),
            api('/meta')
        ]);
        
        if (results[0].status === 'fulfilled') updateHealth(results[0].value);
        if (results[1].status === 'fulfilled') updateProviders(results[1].value);
        if (results[2].status === 'fulfilled') updateSessions(results[2].value);
        if (results[3].status === 'fulfilled') updateStats(results[3].value);
        if (results[3].status === 'fulfilled') initChart(results[3].value.requests_history || []);
        if (results[4].status === 'fulfilled') updateMeta(results[4].value);
    } catch (e) {
        console.error('loadAll error:', e);
    }
}

// Render initial server-side data immediately
function renderInitialData() {
    if (INITIAL_HEALTH) updateHealth(INITIAL_HEALTH);
    if (INITIAL_PROVIDERS) updateProviders(INITIAL_PROVIDERS);
    if (INITIAL_SESSIONS) updateSessions(INITIAL_SESSIONS);
    if (INITIAL_STATS) {
        updateStats(INITIAL_STATS);
        initChart(INITIAL_STATS.requests_history || []);
    }
    if (INITIAL_AUTH) updateApiKeys(INITIAL_AUTH);
    if (INITIAL_CONFIG) document.getElementById('config-content').value = INITIAL_CONFIG;
    if (INITIAL_SERVICE) updateServiceStatus(INITIAL_SERVICE);
    if (INITIAL_META) updateMeta(INITIAL_META);
}

function updateMeta(m) {
    document.getElementById('meta-version').textContent = m.version || '-';
    document.getElementById('meta-commit').textContent = m.commit || '-';
    document.getElementById('meta-branch').textContent = m.branch || '-';
    document.getElementById('meta-evidence').textContent = m.evidence || '-';
}

function updateHealth(h) {
    document.getElementById('service-status').textContent = h.status || 'Unknown';
    document.getElementById('service-status').className = 'px-3 py-1 rounded-full text-sm font-medium ' + 
        (h.status === 'running' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800');
    document.getElementById('stat-service').textContent = h.status || '-';
    document.getElementById('health-api').textContent = h.api_responding ? 'Responding' : 'Not Responding';
    document.getElementById('health-api').className = 'font-medium ' + (h.api_responding ? 'text-green-600' : 'text-red-600');
    document.getElementById('health-uptime').textContent = h.uptime || '-';
    document.getElementById('health-memory').textContent = h.memory || '-';
    document.getElementById('health-cpu').textContent = h.cpu || '-';
    document.getElementById('health-cdp').textContent = h.cdp_connected ? 'Connected' : 'Disconnected';
    document.getElementById('health-cdp').className = 'font-medium ' + (h.cdp_connected ? 'text-green-600' : 'text-red-600');
}

function updateProviders(data) {
    const providers = data.providers || [];
    document.getElementById('stat-providers').textContent = providers.length;
    const ready = providers.filter(p => p.runtime && p.runtime.ready === true).length;
    const statReady = document.getElementById('stat-ready');
    if (statReady) statReady.textContent = ready + '/' + providers.length;
    const runtimeSummary = document.getElementById('provider-runtime-summary');
    if (runtimeSummary) {
        runtimeSummary.innerHTML = providers.map(p => `
            <div class="hwg-runtime-card">
                <div class="flex justify-between gap-2 items-center">
                    <span class="font-mono text-sm">${p.id}</span>
                    <span class="hwg-chip ${p.runtime?.ready ? 'hwg-ok' : (p.runtime?.ready === null ? 'hwg-neutral' : 'hwg-bad')}">${p.runtime?.status || 'unknown'}</span>
                </div>
                <div class="text-xs text-gray-500 mt-1 font-mono">${p.runtime?.cdp_url || 'no dedicated CDP'}</div>
            </div>
        `).join('');
    }
    const tbody = document.getElementById('providers-body');
    tbody.innerHTML = providers.map(p => `
        <tr>
            <td class="px-6 py-4 font-mono text-sm">${p.id}</td>
            <td class="px-6 py-4"><span class="px-2 py-1 bg-gray-100 rounded text-sm">${p.type}</span></td>
            <td class="px-6 py-4">
                <span class="px-2 py-1 rounded text-sm ${p.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                    ${p.enabled ? 'Enabled' : 'Disabled'}
                </span>
            </td>
            <td class="px-6 py-4">
                <span class="hwg-chip ${p.runtime?.ready ? 'hwg-ok' : (p.runtime?.ready === null ? 'hwg-neutral' : 'hwg-bad')}">${p.runtime?.status || 'unknown'}</span>
                <div class="font-mono text-xs text-gray-500 mt-1">${p.runtime?.cdp_url || '-'}</div>
            </td>
            <td class="px-6 py-4">${p.priority}</td>
            <td class="px-6 py-4 text-sm">
                ${Object.entries(p.capabilities).filter(([k,v]) => v).map(([k]) => `<span class="mr-1 px-1 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">${k}</span>`).join('')}
            </td>
            <td class="px-6 py-4 text-sm">
                <label class="inline-flex items-center gap-2">
                    <input type="checkbox"
                        ${p.features?.defaults?.thinking ? 'checked' : ''}
                        ${p.features?.controls?.thinking ? '' : 'disabled'}
                        onchange="setProviderFeature('${p.id}', 'thinking', this.checked, this)">
                    <span>${p.features?.controls?.thinking ? (p.features?.defaults?.thinking ? 'On' : 'Off') : 'N/A'}</span>
                </label>
            </td>
            <td class="px-6 py-4 text-sm">
                <label class="inline-flex items-center gap-2">
                    <input type="checkbox"
                        ${p.features?.defaults?.search ? 'checked' : ''}
                        ${p.features?.controls?.search ? '' : 'disabled'}
                        onchange="setProviderFeature('${p.id}', 'search', this.checked, this)">
                    <span>${p.features?.controls?.search ? (p.features?.defaults?.search ? 'On' : 'Off') : 'N/A'}</span>
                </label>
            </td>
            <td class="px-6 py-4 text-sm">
                <div class="flex gap-2 items-center">
                    <input id="model-${p.id}" list="model-options-${p.id}" class="px-2 py-1 border rounded text-sm font-mono" value="${p.model?.default || p.id}">
                    <datalist id="model-options-${p.id}">
                        ${(p.model?.options || []).map(m => `<option value="${m}"></option>`).join('')}
                    </datalist>
                    <button onclick="setProviderModel('${p.id}')" class="px-2 py-1 bg-blue-600 text-white rounded text-xs">Save</button>
                </div>
                <div id="model-status-${p.id}" class="text-xs text-gray-500 mt-1"></div>
            </td>
            <td class="px-6 py-4">
                <button id="test-${p.id}" onclick="testProvider('${p.id}', this)" class="text-blue-600 hover:underline text-sm">Test</button>
                <div id="test-status-${p.id}" class="text-xs text-gray-500 mt-1"></div>
            </td>
        </tr>
    `).join('');
}

async function setProviderFeature(providerId, feature, value, checkbox) {
    const previous = !value;
    checkbox.disabled = true;
    try {
        const resp = await fetch('/panel/api/providers/' + encodeURIComponent(providerId) + '/features', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({[feature]: value})
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Update failed');
        await loadProviders();
    } catch (e) {
        checkbox.checked = previous;
        checkbox.disabled = false;
        alert('Feature update failed: ' + e.message);
    }
}

async function setProviderModel(providerId) {
    const input = document.getElementById('model-' + providerId);
    const status = document.getElementById('model-status-' + providerId);
    const model = (input.value || '').trim();
    if (!model) {
        status.textContent = 'model is required';
        status.className = 'text-xs text-red-600 mt-1';
        return;
    }
    status.textContent = 'Saving...';
    status.className = 'text-xs text-gray-500 mt-1';
    try {
        const resp = await fetch('/panel/api/providers/' + encodeURIComponent(providerId) + '/model', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({default_upstream_model: model})
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'model update failed');
        status.textContent = 'Saved';
        status.className = 'text-xs text-green-600 mt-1';
        await loadProviders();
    } catch (e) {
        status.textContent = 'Error: ' + e.message;
        status.className = 'text-xs text-red-600 mt-1';
    }
}

function updateSessions(data) {
    document.getElementById('stat-sessions').textContent = data.sessions?.length || 0;
    const tbody = document.getElementById('sessions-body');
    tbody.innerHTML = (data.sessions || []).map(s => `
        <tr>
            <td class="px-6 py-4 font-mono text-sm">${s.conversation_id}</td>
            <td class="px-6 py-4">${s.provider_id}</td>
            <td class="px-6 py-4">${s.message_count}</td>
            <td class="px-6 py-4 text-sm">${new Date(s.created_at * 1000).toLocaleString()}</td>
            <td class="px-6 py-4 text-sm">${new Date(s.updated_at * 1000).toLocaleString()}</td>
            <td class="px-6 py-4">
                <button onclick="deleteSession('${s.conversation_id}')" class="text-red-600 hover:underline text-sm">Delete</button>
            </td>
        </tr>
    `).join('');
}

function updateStats(data) {
    document.getElementById('stat-requests').textContent = data.requests_1h || 0;
}

function initChart(history) {
    const canvas = document.getElementById('requests-chart');
    const rect = canvas.parentElement.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(320, Math.floor(rect.width));
    const height = Math.max(180, Math.floor(rect.height));
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';

    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const padding = {left: 40, right: 18, top: 18, bottom: 28};
    const points = (history || []).map(h => ({value: Number(h.count || 0)}));
    const maxValue = Math.max(1, ...points.map(p => p.value));
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();

    ctx.fillStyle = '#64748b';
    ctx.font = '12px Segoe UI, Arial, sans-serif';
    ctx.fillText('Requests/min', padding.left, 14);
    ctx.fillText(String(maxValue), 8, padding.top + 4);
    ctx.fillText('0', 24, height - padding.bottom + 4);

    if (!points.length) {
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('No request samples in the current window', padding.left + 16, padding.top + 44);
        return;
    }

    const xFor = i => padding.left + (points.length === 1 ? plotW / 2 : i * plotW / (points.length - 1));
    const yFor = v => height - padding.bottom - (v / maxValue) * plotH;

    ctx.beginPath();
    points.forEach((p, i) => {
        const x = xFor(i), y = yFor(p.value);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#2563eb';
    points.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(xFor(i), yFor(p.value), 3, 0, Math.PI * 2);
        ctx.fill();
    });
}

async function loadProviders() {
    const data = await api('/providers');
    updateProviders(data);
}

async function loadSessions() {
    const data = await api('/sessions');
    updateSessions(data);
}

async function loadLogs() {
    const logType = document.getElementById('log-select').value;
    const data = await api('/logs/' + logType);
    document.getElementById('log-content').textContent = data.content || '(empty)';
}

async function loadConfig() {
    const data = await api('/config');
    document.getElementById('config-content').value = data.content || '';
}

async function saveConfig() {
    const content = document.getElementById('config-content').value;
    try {
        const resp = await fetch('/panel/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });
        const result = await resp.json();
        if (result.success) {
            alert('Config saved successfully');
        } else {
            alert('Error: ' + (result.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadApiKeys() {
    const data = await api('/auth/keys');
    updateApiKeys(data);
}

function updateApiKeys(data) {
    const badge = document.getElementById('auth-status');
    badge.textContent = data.auth_enabled ? 'Auth Enabled' : 'Auth Disabled';
    badge.className = 'px-2 py-1 rounded text-xs font-medium ' +
        (data.auth_enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800');

    const btn = document.getElementById('btn-toggle-auth');
    btn.textContent = data.auth_enabled ? 'Disable Auth' : 'Enable Auth';
    btn.className = 'px-3 py-1 rounded text-sm font-medium ' +
        (data.auth_enabled ? 'bg-red-100 hover:bg-red-200' : 'bg-green-100 hover:bg-green-200');

    const tbody = document.getElementById('api-keys-body');
    tbody.innerHTML = (data.api_keys || []).map(k => `
        <tr>
            <td class="px-6 py-4 font-mono text-sm break-all">${k.key}</td>
            <td class="px-6 py-4">${k.identity || '-'}</td>
            <td class="px-6 py-4 text-sm">${k.created_at || '-'}</td>
            <td class="px-6 py-4">
                <button onclick="deleteApiKey('${k.key}')" class="text-red-600 hover:underline text-sm">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function addApiKey() {
    try {
        const resp = await fetch('/panel/api/auth/keys', { method: 'POST' });
        const result = await resp.json();
        if (result.success) {
            alert(`Generated key:
${result.key}

Identity: ${result.identity}`);
            loadApiKeys();
        } else {
            alert('Error: ' + (result.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function deleteApiKey(key) {
    if (!confirm('Delete API key ' + key.substring(0, 20) + '...?')) return;
    try {
        const resp = await fetch('/panel/api/auth/keys/' + encodeURIComponent(key), { method: 'DELETE' });
        const result = await resp.json();
        alert(result.message || 'Key deleted');
        loadApiKeys();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function toggleAuth() {
    try {
        const resp = await fetch('/panel/api/auth/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: !document.getElementById('auth-status').textContent.includes('Enabled') })
        });
        const result = await resp.json();
        loadApiKeys();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadServiceStatus() {
    try {
        const data = await api('/service/status');
        updateServiceStatus(data);
    } catch (e) {
        document.getElementById('service-info').textContent = 'Error: ' + e.message;
    }
}

function updateServiceStatus(data) {
    const badge = document.getElementById('service-status-badge');
    if (data.exists) {
        badge.textContent = data.status;
        badge.className = 'px-3 py-1 rounded-full text-sm font-medium ' +
            (data.status === 'Running' ? 'bg-green-100 text-green-800' :
             data.status === 'Stopped' ? 'bg-red-100 text-red-800' :
             'bg-yellow-100 text-yellow-800');
    } else {
        badge.textContent = 'Not Installed';
        badge.className = 'px-3 py-1 rounded-full text-sm font-medium bg-gray-200 text-gray-800';
    }
    document.getElementById('service-info').textContent = JSON.stringify(data, null, 2) || '(no info)';
}

async function serviceAction(action) {
    const actionText = action.charAt(0).toUpperCase() + action.slice(1);
    if (!confirm(actionText + ' service?')) return;
    try {
        const resp = await fetch('/panel/api/service/' + action, { method: 'POST' });
        const result = await resp.json();
        document.getElementById('service-info').textContent = result.output || '';
        loadServiceStatus();
    } catch (e) {
        document.getElementById('service-info').textContent = 'Error: ' + e.message;
    }
}

async function testProvider(id, btn) {
    const status = document.getElementById('test-status-' + id);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    btn.disabled = true;
    btn.textContent = 'Testing...';
    if (status) {
        status.textContent = 'Testing runtime...';
        status.className = 'text-xs text-gray-500 mt-1';
    }
    try {
        const resp = await fetch('/panel/api/test_provider/' + encodeURIComponent(id), {
            method: 'POST',
            signal: controller.signal,
        });
        const result = await resp.json();
        const ok = resp.ok && result.success === true;
        if (status) {
            status.textContent = ok ? ('OK - ' + (result.runtime?.status || 'ready')) : ('FAILED - ' + (result.message || result.error || 'unavailable'));
            status.className = 'text-xs mt-1 ' + (ok ? 'text-green-600' : 'text-red-600');
        }
    } catch (e) {
        if (status) {
            status.textContent = e.name === 'AbortError' ? 'ERROR - timeout' : ('ERROR - ' + e.message);
            status.className = 'text-xs text-red-600 mt-1';
        }
    } finally {
        clearTimeout(timer);
        btn.disabled = false;
        btn.textContent = 'Test';
    }
}

async function deleteSession(id) {
    if (!confirm('Delete session ' + id + '?')) return;
    await fetch('/panel/api/sessions/' + id, { method: 'DELETE' });
    loadSessions();
}

// Auto-refresh
// Runtime API is the source of truth. Initial server-rendered values can become
// stale after service/provider state changes, so load live data first.
loadAll();
setInterval(loadAll, 10000);
</script>
</body>
</html>
"""

from flask import make_response


@control_panel_bp.after_request
def _set_panel_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@control_panel_bp.route('/')
def dashboard():
    health_data = _get_initial_health()
    providers_data = _get_initial_providers()
    sessions_data = _get_initial_sessions()
    stats_data = _get_initial_stats()
    auth_data = _get_initial_auth()
    config_content = _get_initial_config()
    service_data = _get_initial_service()
    
    html = DASHBOARD_HTML
    # Inject initial data as JSON script tags (safe escaping)
    data_scripts = (
        '<script type="application/json" id="data-health">' + json.dumps(health_data) + '</script>\n'
        '<script type="application/json" id="data-providers">' + json.dumps(providers_data) + '</script>\n'
        '<script type="application/json" id="data-sessions">' + json.dumps(sessions_data) + '</script>\n'
        '<script type="application/json" id="data-stats">' + json.dumps(stats_data) + '</script>\n'
        '<script type="application/json" id="data-auth">' + json.dumps(auth_data) + '</script>\n'
        '<script type="application/json" id="data-service">' + json.dumps(service_data) + '</script>\n'
        '<script type="application/json" id="data-meta">' + json.dumps(_get_panel_meta()) + '</script>\n'
        '<script type="application/json" id="data-config">' + json.dumps(config_content) + '</script>\n'
    )
    html = html.replace('</body>', data_scripts + '\n</body>')
    
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
    try:
        success, output = _run_service_manager("status")
        lines = output.strip().splitlines() if output else []
        status = "Unknown"
        exists = False
        for line in lines:
            if "Service:" in line and "NOT INSTALLED" in line:
                exists = False
                status = "NotInstalled"
            elif "Service:" in line:
                exists = True
            elif "Status:" in line:
                status = line.split("Status:")[1].strip()
        return {"exists": exists, "status": status, "output": output}
    except Exception:
        return {"exists": False, "status": "Unknown", "output": ""}

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


@control_panel_bp.route('/api/providers')
def api_providers():
    providers = provider_registry.list_providers(enabled_only=False)
    return jsonify({"providers": [_provider_payload(p) for p in providers]})

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

@control_panel_bp.route('/api/stats')
def api_stats():
    # Parse audit log for stats
    audit_log = "logs/audit.log"
    requests_1h = 0
    requests_history = []
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
                        # Aggregate by minute for chart
                        minute = int(ts // 60) * 60
                        requests_history.append({"timestamp": minute, "count": 1})
                except:
                    pass
    
    # Aggregate by minute
    from collections import defaultdict
    minute_counts = defaultdict(int)
    for h in requests_history:
        minute_counts[h["timestamp"]] += h["count"]
    
    history = [{"timestamp": k, "count": v} for k, v in sorted(minute_counts.items())]
    
    return jsonify({
        "requests_1h": requests_1h,
        "requests_history": history[-60:]  # Last 60 minutes
    })

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
        return jsonify({"success": True})

@control_panel_bp.route('/api/test_provider/<provider_id>', methods=['POST'])
def api_test_provider(provider_id):
    provider = provider_registry.get(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404

    started = time.time()
    runtime = _check_cdp(provider.config.config.get("cdp_url"))
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
                        key = entry.get("api_key", "")
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
    token = secrets.token_urlsafe(24)
    identity = f"user-{secrets.token_hex(3)}"
    config = _load_config_file()
    auth_section = config.setdefault("governance", {}).setdefault("auth", {})
    if not auth_section.get("api_keys"):
        auth_section["api_keys"] = {}
    auth_section["api_keys"][token] = identity
    auth_section["enabled"] = True
    _save_config_file(config)
    _sync_auth_keys()
    auth_manager.add_key(token, identity)
    from core.governance import audit_logger
    audit_logger.log({
        "event": "api_key_created",
        "api_key": token,
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
    lines = output.strip().splitlines() if output else []
    status = "Unknown"
    exists = False
    for line in lines:
        if "Service:" in line and "NOT INSTALLED" in line:
            exists = False
            status = "NotInstalled"
        elif "Service:" in line:
            exists = True
        elif "Status:" in line:
            status = line.split("Status:")[1].strip()
    return jsonify({
        "exists": exists,
        "status": status,
        "output": output,
    })


@control_panel_bp.route('/api/service/<action>', methods=['POST'])
def api_service_action(action):
    if action not in ("start", "stop", "restart"):
        return jsonify({"error": "Invalid action"}), 400
    success, output = _run_service_manager(action)
    return jsonify({
        "success": success,
        "action": action,
        "output": output,
    })
