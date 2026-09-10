import os
import json
import time
import logging
import subprocess
import secrets
import yaml
import psutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template_string, jsonify, request
from core.provider_registry import provider_registry
from core.mcp import mcp_session_manager
from core.governance import auth_manager, rate_limiter
from core.config import load_config, deep_merge, get_default_config

control_panel_bp = Blueprint('control_panel', __name__, url_prefix='/panel')

logger = logging.getLogger(__name__)

CONFIG_PATH = str(Path(__file__).parent / "config.yaml")


def _load_config_file():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config_file(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _sync_auth_keys():
    """Sync API keys from config.yaml into the runtime AuthManager singleton."""
    config = _load_config_file()
    raw_keys = config.get("governance", {}).get("auth", {}).get("api_keys", {}) or {}
    auth_manager._api_keys.clear()
    for key, identity in raw_keys.items():
        auth_manager._api_keys[key] = {"identity": identity, "metadata": {}}


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

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hooshka Web Gateway - Control Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-gray-900 text-white p-4 shadow-lg">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <h1 class="text-2xl font-bold"><i class="fas fa-server mr-2"></i>Hooshka Web Gateway Control Panel</h1>
            <div class="flex items-center space-x-4">
                <span id="service-status" class="px-3 py-1 rounded-full text-sm font-medium bg-gray-700">Checking...</span>
                <button onclick="location.reload()" class="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm">
                    <i class="fas fa-sync-alt mr-1"></i> Refresh
                </button>
            </div>
        </div>
    </nav>

    <div class="max-w-7xl mx-auto p-6">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-blue-100 rounded-full"><i class="fas fa-heartbeat text-blue-600 text-2xl"></i></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Service Status</p>
                        <p id="stat-service" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-green-100 rounded-full"><i class="fas fa-plug text-green-600 text-2xl"></i></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Providers</p>
                        <p id="stat-providers" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-purple-100 rounded-full"><i class="fas fa-comments text-purple-600 text-2xl"></i></div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-600">Active Sessions</p>
                        <p id="stat-sessions" class="text-2xl font-bold">-</p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-orange-100 rounded-full"><i class="fas fa-chart-line text-orange-600 text-2xl"></i></div>
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
                            <div class="flex justify-between"><span>Chrome CDP</span><span id="health-cdp" class="font-medium">-</span></div>
                        </div>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold mb-4">Recent Requests</h3>
                        <div style="position: relative; height: 250px; width: 100%;">
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
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Capabilities</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Models</th>
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
                        <i class="fas fa-plus mr-1"></i> Generate New Key
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
            api('/stats')
        ]);
        
        if (results[0].status === 'fulfilled') updateHealth(results[0].value);
        if (results[1].status === 'fulfilled') updateProviders(results[1].value);
        if (results[2].status === 'fulfilled') updateSessions(results[2].value);
        if (results[3].status === 'fulfilled') updateStats(results[3].value);
        if (results[3].status === 'fulfilled') initChart(results[3].value.requests_history || []);
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
    document.getElementById('stat-providers').textContent = data.providers?.length || 0;
    const tbody = document.getElementById('providers-body');
    tbody.innerHTML = (data.providers || []).map(p => `
        <tr>
            <td class="px-6 py-4 font-mono text-sm">${p.id}</td>
            <td class="px-6 py-4"><span class="px-2 py-1 bg-gray-100 rounded text-sm">${p.type}</span></td>
            <td class="px-6 py-4">
                <span class="px-2 py-1 rounded text-sm ${p.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                    ${p.enabled ? 'Enabled' : 'Disabled'}
                </span>
            </td>
            <td class="px-6 py-4">${p.priority}</td>
            <td class="px-6 py-4 text-sm">
                ${Object.entries(p.capabilities).filter(([k,v]) => v).map(([k]) => `<span class="mr-1 px-1 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">${k}</span>`).join('')}
            </td>
            <td class="px-6 py-4 text-sm">${(p.capabilities.supported_models || []).join(', ')}</td>
            <td class="px-6 py-4">
                <button onclick="testProvider('${p.id}')" class="text-blue-600 hover:underline text-sm">Test</button>
            </td>
        </tr>
    `).join('');
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

let requestsChart = null;
function initChart(history) {
    const ctx = document.getElementById('requests-chart').getContext('2d');
    if (requestsChart) requestsChart.destroy();
    
    const labels = history.map(h => new Date(h.timestamp * 1000).toLocaleTimeString());
    const data = history.map(h => h.count);
    
    requestsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Requests/min',
                data: data,
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
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

async function testProvider(id) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Testing...';
    try {
        const resp = await fetch('/panel/api/test_provider/' + id, { method: 'POST' });
        const result = await resp.json();
        alert(result.message || JSON.stringify(result));
    } catch (e) {
        alert('Error: ' + e.message);
    }
    btn.disabled = false;
    btn.textContent = 'Test';
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
            cdp_url = config.get("cdp", {}).get("url", "http://127.0.0.1:9222")
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
        return {
            "providers": [
                {
                    "id": p.provider_id,
                    "type": p.provider_type.value,
                    "enabled": p.config.enabled,
                    "priority": p.config.priority,
                    "capabilities": {
                        "chat_completion": p.capabilities.chat_completion,
                        "streaming": p.capabilities.streaming,
                        "tools": p.capabilities.tools,
                        "vision": p.capabilities.vision,
                        "embeddings": p.capabilities.embeddings,
                        "max_context_tokens": p.capabilities.max_context_tokens,
                        "supported_models": p.capabilities.supported_models,
                    }
                }
                for p in providers
            ]
        }
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
    cdp_url = config.get("cdp", {}).get("url", "http://127.0.0.1:9222")
    
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

@control_panel_bp.route('/api/providers')
def api_providers():
    providers = provider_registry.list_providers(enabled_only=False)
    return jsonify({
        "providers": [
            {
                "id": p.provider_id,
                "type": p.provider_type.value,
                "enabled": p.config.enabled,
                "priority": p.config.priority,
                "capabilities": {
                    "chat_completion": p.capabilities.chat_completion,
                    "streaming": p.capabilities.streaming,
                    "tools": p.capabilities.tools,
                    "vision": p.capabilities.vision,
                    "embeddings": p.capabilities.embeddings,
                    "max_context_tokens": p.capabilities.max_context_tokens,
                    "supported_models": p.capabilities.supported_models,
                }
            }
            for p in providers
        ]
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
    
    try:
        import asyncio
        health = asyncio.run(provider.health_check())
        return jsonify({"success": health, "message": f"Health check: {'OK' if health else 'FAILED'}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

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