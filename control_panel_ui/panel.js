(function () {
  'use strict';

  const PANEL_TITLES = {
    overview: 'وضعیت کلی',
    runtimes: 'محیط‌های اجرا',
    providers: 'فراهم‌کننده‌ها',
    models: 'مدل‌ها و قابلیت‌ها',
    chat: 'چت تعاملی',
    sessions: 'گفتگوها',
    telemetry: 'آمار مصرف',
    apikeys: 'کلیدها و دسترسی',
    config: 'تنظیمات',
    service: 'سرویس و ری‌استارت',
    logs: 'گزارش‌ها و شواهد',
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function setStatus(el, msg, kind) {
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'status-line' + (kind ? ' ' + kind : '');
  }

  function toast(msg, kind) {
    const region = $('#toast-region');
    if (!region) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (kind || '');
    t.textContent = msg;
    region.appendChild(t);
    setTimeout(() => t.remove(), 4200);
  }

  function compact(n) {
    const v = Number(n || 0);
    const a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(a >= 1e10 ? 0 : 1).replace(/\.0$/, '') + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M';
    if (a >= 1e3) return (v / 1e3).toFixed(a >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'k';
    return String(v);
  }

  async function api(path, options) {
    const resp = await fetch('/panel/api' + path, options);
    let data = null;
    try { data = await resp.json(); } catch (e) { data = {}; }
    if (!resp.ok) {
      const err = new Error((data && (data.error || data.message)) || ('HTTP ' + resp.status));
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  /* ---------------- Theme ---------------- */
  function initTheme() {
    const saved = localStorage.getItem('hwg-ui-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    $('#theme-toggle').textContent = 'تم: ' + (saved === 'dark' ? 'تاریک' : 'روشن');
    $('#theme-toggle').onclick = () => {
      const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', cur);
      localStorage.setItem('hwg-ui-theme', cur);
      $('#theme-toggle').textContent = 'تم: ' + (cur === 'dark' ? 'تاریک' : 'روشن');
    };
  }

  /* ---------------- Navigation ---------------- */
  function showPanel(name) {
    $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.panel === name));
    $$('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + name));
    $('#panel-title').textContent = PANEL_TITLES[name] || name;
    if (name === 'overview') loadOverview();
    if (name === 'runtimes') loadRuntimes();
    if (name === 'providers') loadProviders();
    if (name === 'models') loadModelsTab();
    if (name === 'chat') window.HwgChat && HwgChat.init();
    if (name === 'sessions') loadSessions();
    if (name === 'telemetry') loadTelemetry();
    if (name === 'apikeys') loadApiKeys();
    if (name === 'config') loadConfig();
    if (name === 'service') loadServiceStatus();
    if (name === 'logs') loadLogs();
  }

function initNav() {
    $$('.nav-item').forEach(b => b.addEventListener('click', () => showPanel(b.dataset.panel)));
    $('#refresh-btn').addEventListener('click', () => { loadMeta(); loadServiceBadge(); showPanel(currentPanel()); refreshAll(); });
    showPanel('overview');
    startStatsPolling();
  }

  function startStatsPolling() {
    if (window._statsPolling) return;
    window._statsPolling = setInterval(async () => {
      if (document.querySelector('.nav-item.active')?.dataset.panel === 'overview') {
        await Promise.allSettled([loadStatsAll(), loadOverviewExtra(), loadProviders({ quiet: true })]);
      }
    }, 5000);
  }

  function currentPanel() {
    const active = $('.nav-item.active');
    return active ? active.dataset.panel : 'overview';
  }

  async function refreshAll() {
    await Promise.allSettled([loadProviders(), loadSessions(), loadStatsAll(), loadApiKeys()]);
  }

  /* ---------------- Meta ---------------- */
  async function loadMeta() {
    try {
      const m = await api('/meta');
      $('#meta-version').textContent = m.version || '-';
      $('#meta-commit').textContent = m.commit || '-';
      $('#meta-branch').textContent = m.branch || '-';
      $('#meta-evidence').textContent = m.evidence || '-';
    } catch (e) { /* keep placeholders */ }
    try {
      const ui = await fetch('/panel/assets/UI_VERSION.json', { cache: 'no-store' }).then(r => r.json());
      $('#meta-ui').textContent = ui.version || '-';
    } catch (e) {
      $('#meta-ui').textContent = '-';
    }
  }

  async function loadServiceBadge() {
    try {
      const data = await api('/service/status');
      const service = data.service || {};
      const status = data.status || service.status || 'Unknown';
      const exists = data.exists === true || service.exists === true;
      const badge = $('#service-status-badge');
      badge.textContent = exists ? status : 'نصب نشده';
      badge.className = 'badge ' + (exists
        ? (status === 'Running' ? 'ok' : status === 'Stopped' ? 'bad' : 'warn')
        : 'neutral');
    } catch (e) {
      $('#service-status-badge').textContent = 'نامشخص';
    }
  }

  /* ---------------- Overview ---------------- */
  async function loadOverview() {
    await Promise.allSettled([loadMeta(), loadServiceBadge(), loadStatsAll(), loadProviders({ quiet: true })]);
    await loadOverviewExtra();
  }

  async function loadOverviewExtra() {
    try {
      const h = await api('/health');
      const cdp = $('#health-cdp');
      if (cdp) {
        cdp.textContent = h.cdp_connected ? 'فعال' : 'غیرفعال';
        cdp.className = h.cdp_connected ? 'ok' : 'bad';
      }
      const mem = $('#health-memory');
      if (mem) mem.textContent = h.memory || '-';
      const cpu = $('#health-cpu');
      if (cpu) cpu.textContent = h.cpu || '-';
      const up = $('#health-uptime');
      if (up) up.textContent = h.uptime || '-';
      const svc = $('#stat-service');
      if (svc) svc.textContent = h.status === 'running' ? 'در حال اجرا' : (h.status || '-');
    } catch (e) { /* ignore */ }
    try {
      const sess = await api('/sessions');
      const stat = $('#stat-sessions');
      if (stat) stat.textContent = (sess.sessions || []).length;
    } catch (e) { /* ignore */ }
    try {
      const models = await fetch('/v1/models', { cache: 'no-store' }).then(r => r.json());
      const pr = models.provider_runtime || {};
      const concurrency = $('#health-concurrency');
      if (concurrency) {
        concurrency.textContent = (pr.inflight || 0) + '/' + (pr.max_concurrency || '-') +
          (pr.rejected ? ' (ردشده ' + pr.rejected + ')' : '');
        concurrency.className = (pr.inflight || 0) > 0 ? 'ok' : '';
      }
    } catch (e) { /* ignore */ }
  }

  async function loadStatsAll() {
    try {
      const s = await api('/stats');
      $('#stat-requests').textContent = s.requests_1h || 0;
      renderBreakdown($('#request-breakdown-summary'), s.breakdown);
      initChart('requests-chart', s.requests_history || []);
      const u = await api('/model_usage');
      renderModelUsage($('#model-usage-summary'), u);
    } catch (e) { /* ignore */ }
  }

  function startStatsPolling() {
    if (window.__hwg_stats_polling) return;
    window.__hwg_stats_polling = setInterval(() => {
      if (document.querySelector('.nav-item.active')?.dataset.panel === 'overview') {
        loadStatsAll();
        loadOverviewExtra();
        loadProviders({ quiet: true });
      }
    }, 5000);
  }

  function renderBreakdown(box, b) {
    if (!box) return;
    b = b || {};
    box.innerHTML = [
      ['درخواست مدل', b.model || 0],
      ['پنل', b.panel || 0],
      ['سلامت/فراداده', b.health_metadata || 0],
      ['سایر', b.other || 0],
    ].map(([label, value]) => `<div class="hwg-chip hwg-neutral">${label}: <b>${compact(value)}</b></div>`).join(' ');
  }

  function renderModelUsage(box, data) {
    if (!box) return;
    const rows = data.models || [];
    if (!rows.length) {
      const monitored = (data.monitored || []).map(m => m.provider + '/' + m.model).join('، ');
      box.innerHTML = `<div class="hwg-chip hwg-neutral">ترافیک مدل تکمیل‌شده در ۱ ساعت گذشته ثبت نشده است.</div>
        <div class="hint">اهداف: ${monitored || '—'}</div>`;
      return;
    }
    box.innerHTML = rows.map(r => {
      const tv = (v, avail) => avail ? compact(v) + (r.tokens_estimated ? ' (تخمین)' : '') : 'در دسترس نیست';
      const avail = (f) => f === true;
      return `<div class="card">
        <div class="kv">
          <span class="ltr">${r.provider}/${r.model}</span>
          <span class="hwg-chip hwg-neutral">${compact(r.requests)} درخواست</span>
          <span>موفق / ناموفق</span><b>${compact(r.success_count || 0)} / ${compact(r.failure_count || 0)}</b>
          <span>میانگین تأخیر</span><b>${r.avg_latency_ms == null ? 'ثبت نشده' : compact(r.avg_latency_ms) + ' ms'}</b>
          <span>آخرین فعالیت</span><b>${r.last_activity ? new Date(r.last_activity * 1000).toLocaleString('fa-IR') : 'ثبت نشده'}</b>
          <span>توکن ورودی</span><b>${tv(r.prompt_tokens, avail(r.prompt_tokens_available))}</b>
          <span>توکن خروجی</span><b>${tv(r.completion_tokens, avail(r.completion_tokens_available))}</b>
          <span>کل توکن</span><b>${tv(r.total_tokens, avail(r.total_tokens_available) || avail(r.tokens_available))}</b>
        </div>
      </div>`;
    }).join('');
  }

  function niceCeil(v) {
    if (v <= 5) return 5;
    if (v <= 10) return 10;
    if (v <= 20) return 20;
    if (v <= 50) return 50;
    if (v <= 100) return 100;
    const m = Math.pow(10, Math.floor(Math.log10(v)));
    return Math.ceil(v / m) * m;
  }

  function initChart(canvasId, history) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !canvas.parentElement) return;
    const rect = canvas.parentElement.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(360, Math.floor(rect.width));
    const height = Math.max(230, Math.floor(rect.height));
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const pad = { left: 52, right: 18, top: 30, bottom: 38 };
    const points = (history || []).map(h => ({ ts: Number(h.timestamp || 0), v: Math.max(0, Number(h.count || 0)) }));
    const values = points.map(p => p.v);
    const maxObs = values.length ? Math.max(...values) : 0;
    const yMax = niceCeil(Math.max(5, maxObs * 1.15));
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--panel').trim() || '#fff';
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = '#64748b';
    ctx.font = '12px Segoe UI, Arial, sans-serif';
    ctx.fillText('درخواست‌های گیت‌وی در هر دقیقه', pad.left, 18);
    ctx.strokeStyle = '#e5e7eb';
    const labels = ['#64748b', '#cbd5e1', '#2563eb', '#334155'];
    ctx.strokeStyle = labels[2];
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const y = pad.top + (plotH * i / 5);
      const tick = Math.round(yMax - (yMax * i / 5));
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
      ctx.fillStyle = labels[0];
      ctx.fillText(String(tick), pad.left - 8, y + 4);
    }
    if (!points.length || maxObs === 0) {
      ctx.fillStyle = labels[0];
      ctx.fillText('داده‌ای موجود نیست', pad.left + 14, pad.top + 44);
      return;
    }
    const denom = Math.max(1, points.length - 1);
    const xFor = i => pad.left + (i * plotW / denom);
    const yFor = v => pad.top + plotH - (v / yMax) * plotH;
    const labelStep = Math.max(1, Math.ceil(points.length / 6));
    ctx.font = '11px Segoe UI, Arial, sans-serif';
    points.forEach((p, i) => {
      if (i % labelStep !== 0 && i !== points.length - 1) return;
      const label = new Date(p.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      ctx.fillStyle = labels[0];
      ctx.fillText(label, Math.min(width - pad.right - 32, Math.max(pad.left, xFor(i) - 16)), height - 12);
    });
    ctx.strokeStyle = labels[2];
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((p, i) => { const x = xFor(i), y = yFor(p.v); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.stroke();
    ctx.fillStyle = labels[2];
    points.forEach((p, i) => { ctx.beginPath(); ctx.arc(xFor(i), yFor(p.v), 2.5, 0, Math.PI * 2); ctx.fill(); });
  }

  /* ---------------- Runtimes ---------------- */
  async function loadRuntimes() {
    const tbody = $('#runtimes-body');
    const status = $('#runtime-action-global');
    setStatus(status, '', '');
    try {
      const data = await api('/runtimes');
      tbody.innerHTML = (data.runtimes || []).map(r => `
        <tr>
          <td class="ltr">${r.id}</td>
          <td class="ltr">${r.port || '-'}</td>
          <td><span class="hwg-chip ${r.ready ? 'hwg-ok' : (r.ready === null ? 'hwg-neutral' : 'hwg-bad')}">${r.status || 'unknown'}</span></td>
          <td class="ltr">${r.profile || '-'}</td>
          <td class="ltr"><a href="${r.home_url}" target="_blank" rel="noopener noreferrer">${r.home_url}</a></td>
          <td>${r.label || '-'}</td>
          <td>
            <div class="btn-row">
              <button class="btn ghost btn-xs" data-id="${r.id}" data-act="open">باز کردن</button>
              <button class="btn ${r.ready ? 'ghost' : 'primary'} btn-xs" data-id="${r.id}" data-act="${r.ready ? 'restart' : 'start'}">${r.ready ? 'ری‌استارت' : 'شروع'}</button>
            </div>
          </td>
        </tr>`).join('');
      tbody.querySelectorAll('button[data-act]').forEach(b => b.addEventListener('click', () => runtimeAction(b.dataset.id, b.dataset.act, b)));
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-muted">خطا: ${e.message}</td></tr>`;
    }
    $('#runtime-repair-all').onclick = () => runtimeAction('all', 'repair', null);
  }

  async function runtimeAction(providerId, action, btn) {
    const status = $('#runtime-action-global');
    let fallback = null;
    if (btn) { btn.disabled = true; const orig = btn.textContent; fallback = orig; btn.textContent = 'در حال انجام...'; }
    setStatus(status, 'در حال انجام عملیات runtime...', 'working');
    try {
      const data = await api('/providers/runtime/' + encodeURIComponent(providerId) + '/' + encodeURIComponent(action), { method: 'POST' });
      setStatus(status, data.message || 'تکمیل شد', 'ok');
      toast('Runtime: ' + (data.message || action), 'ok');
      if (btn) { btn.textContent = fallback; btn.disabled = false; }
      await loadRuntimes();
      await loadProviders({ quiet: true });
    } catch (e) {
      setStatus(status, 'شکست: ' + e.message, 'err');
      toast('Runtime: ' + e.message, 'err');
      if (btn) { btn.textContent = fallback; btn.disabled = false; }
    }
  }

  /* ---------------- Providers ---------------- */
  async function loadProviders(opts) {
    let data;
    try { data = await api('/providers'); }
    catch (e) { return; }
    const providers = data.providers || [];
    $('#stat-providers').textContent = providers.length;
    const enabled = providers.filter(p => p.enabled === true);
    const ready = enabled.filter(p => p.runtime && p.runtime.ready === true).length;
    $('#stat-ready').textContent = ready + '/' + enabled.length;
    $('#stat-sessions').textContent = '؟';
    $('#health-api').textContent = 'پاسخگو';

    const summary = $('#provider-runtime-summary');
    if (summary) {
      summary.innerHTML = providers.map(p => `
        <div class="hwg-chip ${p.runtime?.ready ? 'hwg-ok' : (p.runtime?.ready === null ? 'hwg-neutral' : 'hwg-bad')}">${p.id}: ${p.runtime?.status || 'unknown'}</div>`).join('');
    }

    if (opts && opts.quiet) return;

    const tbody = $('#providers-body');
    tbody.innerHTML = providers.map(p => `
      <tr>
        <td class="ltr">${p.id}</td>
        <td><span class="hwg-chip hwg-neutral">${p.type}</span></td>
        <td><span class="hwg-chip ${p.enabled ? 'hwg-ok' : 'hwg-bad'}">${p.enabled ? 'فعال' : 'غیرفعال'}</span></td>
        <td>
          <span class="hwg-chip ${p.runtime?.ready ? 'hwg-ok' : (p.runtime?.ready === null ? 'hwg-neutral' : 'hwg-bad')}">${p.runtime?.status || 'unknown'}</span>
          <div class="hint ltr">${p.runtime?.cdp_url || '-'}</div>
        </td>
        <td>${p.priority}</td>
        <td><div class="capability-badges">${Object.entries(p.capabilities || {}).filter(([k, v]) => v === true).map(([k]) => `<span class="cap-badge">${k}</span>`).join('')}</div></td>
        <td>
          <label class="check"><input type="checkbox" ${p.features?.defaults?.thinking ? 'checked' : ''} ${p.features?.controls?.thinking ? '' : 'disabled'}
            onchange="window.HwgProvidersToggle && HwgProvidersToggle('${p.id}','thinking',this.checked)"><span>${p.features?.controls?.thinking ? (p.features?.defaults?.thinking ? 'روشن' : 'خاموش') : 'N/A'}</span></label>
        </td>
        <td>
          <label class="check"><input type="checkbox" ${p.features?.defaults?.search ? 'checked' : ''} ${p.features?.controls?.search ? '' : 'disabled'}
            onchange="window.HwgProvidersToggle && HwgProvidersToggle('${p.id}','search',this.checked)"><span>${p.features?.controls?.search ? (p.features?.defaults?.search ? 'روشن' : 'خاموش') : 'N/A'}</span></label>
        </td>
        <td>
          <div class="btn-row">
            <select class="ctrl" id="model-${p.id}" style="max-width:180px" data-original="${(p.model?.default || p.id)?.replace(/"/g, '&quot;')}">
              ${(p.model?.options || [p.model?.default || p.id]).map(m => `<option value="${m.replace(/"/g, '&quot;')}">${m}</option>`).join('')}
            </select>
            <button class="btn primary btn-xs" onclick="window.HwgModelSave && HwgModelSave('${p.id}')">ذخیره</button>
          </div>
          <div class="hint">فعلی: <span class="ltr">${p.model?.default || p.id}</span></div>
          <div id="model-status-${p.id}" class="status-line"></div>
        </td>
        <td>
          <div class="btn-row">
            <button class="btn ghost btn-xs" onclick="window.HwgOpenProvider && HwgOpenProvider('${p.id}')">باز کردن</button>
            <button class="btn ghost btn-xs" id="rt-${p.id}" onclick="window.HwgProviderRuntime && HwgProviderRuntime('${p.id}')">${p.runtime?.ready ? 'ری‌استارت' : 'شروع'}</button>
            <button class="btn ghost btn-xs" id="test-${p.id}" onclick="window.HwgTestProvider && HwgTestProvider('${p.id}')">تست</button>
            <button class="btn btn-danger btn-xs" onclick="window.HwgDeleteProvider && HwgDeleteProvider('${p.id}')">حذف</button>
          </div>
          <div id="test-status-${p.id}" class="status-line"></div>
        </td>
      </tr>`).join('');
    $('#repair-all-runtimes').onclick = () => runtimeAction('all', 'repair', null);
  }

  window.HwgProvidersToggle = async function (providerId, feature, value) {
    try {
      await api('/providers/' + encodeURIComponent(providerId) + '/features', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [feature]: value }),
      });
      await loadProviders();
      toast('ویژگی ' + feature + ' ذخیره شد', 'ok');
    } catch (e) {
      toast('ذخیره ویژگی شکست خورد: ' + e.message, 'err');
      loadProviders();
    }
  };

  window.HwgModelSave = async function (providerId) {
    const input = document.getElementById('model-' + providerId);
    const status = document.getElementById('model-status-' + providerId);
    const model = (input.value || '').trim();
    if (!model) { setStatus(status, 'مدل الزامی است', 'err'); return; }
    setStatus(status, 'در حال ذخیره...', 'working');
    try {
      await api('/providers/' + encodeURIComponent(providerId) + '/model', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ default_upstream_model: model }),
      });
      setStatus(status, 'ذخیره شد', 'ok');
      loadProviders();
    } catch (e) {
      setStatus(status, 'خطا: ' + e.message, 'err');
    }
  };

  window.HwgOpenProvider = async function (providerId) {
    try {
      const r = await api('/providers/' + encodeURIComponent(providerId) + '/open', { method: 'POST' });
      toast(r.success ? 'مرورگر باز شد' : (r.message || 'باز نشد'), r.success ? 'ok' : 'warn');
    } catch (e) { toast('باز کردن شکست خورد: ' + e.message, 'err'); }
  };

  window.HwgProviderRuntime = async function (providerId) {
    const btn = document.getElementById('rt-' + providerId);
    const id = encodeURIComponent(providerId);
    const action = btn && btn.closest('tr').textContent.includes('ری‌استارت') ? 'restart' : 'start';
    if (btn) btn.disabled = true;
    try {
      const r = await api('/providers/runtime/' + encodeURIComponent(providerId) + '/' + action, { method: 'POST' });
      if (!r.success) throw new Error(r.message || 'runtime action failed');
      toast('Runtime ' + providerId + ': ' + (r.message || 'ok'), 'ok');
    } catch (e) {
      toast('Runtime: ' + e.message, 'err');
    } finally {
      if (btn) btn.disabled = false;
      await Promise.all([loadProviders(), loadRuntimes()]);
    }
  };

  window.HwgTestProvider = async function (providerId) {
    const status = document.getElementById('test-status-' + providerId);
    const btn = document.getElementById('test-' + providerId);
    setStatus(status, 'در حال تست...', 'working');
    if (btn) btn.disabled = true;
    try {
      const r = await api('/test_provider/' + encodeURIComponent(providerId), { method: 'POST' });
      setStatus(status, (r.success ? 'OK - ' : 'ناموفق - ') + (r.runtime?.status || r.message || 'unavailable'), r.success ? 'ok' : 'err');
    } catch (e) {
      setStatus(status, 'خطا: ' + e.message, 'err');
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  window.HwgDeleteProvider = async function (providerId) {
    if (!confirm('پراوایدر ' + providerId + ' حذف شود؟ این عملیات قابل بازگشت نیست.')) return;
    try {
      const r = await api('/providers/' + encodeURIComponent(providerId), { method: 'DELETE' });
      if (r.success) {
        toast('پراوایدر حذف شد (نیاز به ری‌استارت)', 'ok');
        loadProviders();
      } else {
        toast('خطا: ' + (r.error || 'نامشخص'), 'err');
      }
    } catch (e) {
      toast('خطا: ' + e.message, 'err');
    }
  };

  /* ---------------- Models & Capabilities ---------------- */
  async function loadModelsTab() {
    try {
      const caps = await fetch('/v1/capabilities', { cache: 'no-store' }).then(r => r.json());
      const models = await fetch('/v1/models', { cache: 'no-store' }).then(r => r.json());
      const prov = await api('/providers');

      const mbox = $('#models-summary');
      mbox.innerHTML = `
        <div class="card"><div class="kv">
          <span>Manifest</span><b class="ltr">${caps.manifest_version || '-'}</b>
          <span>Spec</span><b class="ltr">${caps.spec_version || '-'}</b>
          <span>Baseline سازگاری</span><b class="ltr">${caps.compatibility_baseline || '-'}</b>
        </div></div>
        <div class="card"><div class="kv">
          <span>لوکال بدون کلید</span><b>${caps.access?.loopback_without_key ? 'مجاز' : 'ممنوع'}</b>
          <span>سیاست لوکال</span><b class="ltr">${caps.access?.loopback_policy || '-'}</b>
          <span>غیرلوکال</span><b>${caps.access?.non_loopback || '-'}</b>
          <span>احراز هویت</span><b>${caps.access?.auth_enabled ? 'فعال' : 'غیرفعال'}</b>
        </div></div>
        <div class="card"><div class="kv">
          <span>تعداد مدل</span><b>${(models.data || []).length}</b>
          <span>تعداد پراوایدر</span><b>${(caps.providers || []).length}</b>
          <span>پیش‌فرض</span><b class="ltr">${prov.default || '-'}</b>
          <span>هم‌روندی</span><b>${models.provider_runtime?.inflight || 0}/${models.provider_runtime?.max_concurrency || '-'}</b>
        </div></div>`;

      const capKeys = ['chat_completion', 'streaming', 'tools', 'vision', 'embeddings', 'search', 'reasoning', 'files', 'max_context_tokens'];
      const plist = (caps.providers || []).filter(p => p.enabled !== false);
      const matrix = $('#capability-matrix');
      matrix.innerHTML = '<table class="data-table"><thead><tr><th>قابلیت</th>' +
        plist.map(p => `<th class="ltr">${p.id}</th>`).join('') + '</tr></thead><tbody>' +
        capKeys.map(k => `<tr><td><span class="cap-badge">${k}</span></td>` +
          plist.map(p => {
            const v = p.capabilities && p.capabilities[k];
            if (k === 'max_context_tokens') return `<td>${Number(v) || '-'}</td>`;
            if (v === true) return `<td><span class="hwg-chip hwg-ok">بله</span></td>`;
            if (v) return `<td class="ltr">${String(v)}</td>`;
            return `<td><span class="hwg-chip hwg-neutral">-</span></td>`;
          }).join('') + '</tr>').join('') + '</tbody></table>';

      const modelBox = document.createElement('div');
      matrix.appendChild(modelBox);
    } catch (e) {
      const mbox = $('#models-summary');
      if (mbox) mbox.innerHTML = '<div class="card hint">خطا: ' + e.message + '</div>';
    }
  }

  /* ---------------- Sessions ---------------- */
  async function loadSessions() {
    const tbody = $('#sessions-body');
    try {
      const data = await api('/sessions');
      $('#stat-sessions').textContent = (data.sessions || []).length;
      tbody.innerHTML = (data.sessions || []).map(s => `
        <tr>
          <td class="ltr">${s.conversation_id}</td>
          <td>${s.provider_id}</td>
          <td>${s.message_count}</td>
          <td>${new Date((s.created_at || 0) * 1000).toLocaleString()}</td>
          <td>${new Date((s.updated_at || 0) * 1000).toLocaleString()}</td>
          <td><button class="btn danger btn-xs" data-id="${s.conversation_id}">حذف</button></td>
        </tr>`).join('');
      tbody.querySelectorAll('button[data-id]').forEach(b => {
        b.addEventListener('click', async () => {
          if (!confirm('گفتگوی ' + b.dataset.id + ' حذف شود؟')) return;
          try { await api('/sessions/' + encodeURIComponent(b.dataset.id), { method: 'DELETE' }); toast('گفتگو حذف شد', 'ok'); } catch (e) { toast('خطا: ' + e.message, 'err'); }
          loadSessions();
        });
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6">خطا: ${e.message}</td></tr>`;
    }
  }

  /* ---------------- Telemetry ---------------- */
  async function loadTelemetry() {
    try {
      const s = await api('/stats');
      renderBreakdown($('#tl-breakdown'), s.breakdown);
      initChart('requests-chart-tl', s.requests_history || []);
      const u = await api('/model_usage');
      renderModelUsage($('#tl-model'), u);
    } catch (e) { /* ignore */ }
  }

  /* ---------------- API Keys ---------------- */
  async function loadApiKeys() {
    const tbody = $('#api-keys-body');
    const status = $('#auth-status');
    try {
      const data = await api('/auth/keys');
      $('#top-auth-badge').textContent = data.auth_enabled ? 'کلید اجباری' : 'بی‌کلید لوکال';
      $('#top-auth-badge').className = 'badge ' + (data.auth_enabled ? 'info' : 'neutral');
      setStatus(status, data.auth_enabled ? 'احراز هویت فعال است؛ دسترسی غیرلوکال فقط با کلید.' : 'احراز هویت غیرفعال؛ اتصالات لوکال بدون کلید مجازند.', data.auth_enabled ? 'ok' : '');
      const btn = $('#btn-toggle-auth');
      btn.textContent = data.auth_enabled ? 'غیرفعال‌کردن احراز هویت' : 'فعال‌کردن احراز هویت';
      btn.className = 'btn ' + (data.auth_enabled ? 'danger' : 'success');
      btn.onclick = () => toggleAuth(data.auth_enabled ? false : true);
      tbody.innerHTML = (data.api_keys || []).map(k => `
        <tr>
          <td class="ltr">${k.key}</td>
          <td>${k.identity || '-'}</td>
          <td>${k.created_at || '-'}</td>
          <td><button class="btn danger btn-xs" data-key="${k.key}">حذف</button></td>
        </tr>`).join('');
      tbody.querySelectorAll('button[data-key]').forEach(b => {
        b.addEventListener('click', async () => {
          if (!confirm('کلید ' + b.dataset.key.substring(0, 20) + '... حذف شود؟')) return;
          try {
            const r = await api('/auth/keys/' + encodeURIComponent(b.dataset.key), { method: 'DELETE' });
            toast(r.message || 'کلید حذف شد', 'ok');
          } catch (e) { toast('خطا: ' + e.message, 'err'); }
          loadApiKeys();
        });
      });
    } catch (e) {
      setStatus(status, 'خطا: ' + e.message, 'err');
    }
  }

  window.HwgGenKey = async function () {
    if (!confirm('کلید API جدید تولید شود؟' + '\n\nکلید فقط همین یکبار نمایش داده می‌شود.')) return;
    try {
      const r = await api('/auth/keys', { method: 'POST' });
      const modal = document.createElement('div');
      modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:10000;';
      const box = document.createElement('div');
      box.style.cssText = 'background:#fff; color:#111; padding:1.5rem; border-radius:8px; max-width:440px; width:90%;';
      const pre = document.createElement('pre');
      pre.textContent = r.key;
      pre.style.cssText = 'background:#f3f3f3; padding:1rem; border-radius:4px; overflow:auto; max-height:200px; white-space:pre-wrap; word-break:break-all;';
      const copy = document.createElement('button');
      copy.textContent = 'کلید را کپی کن';
      copy.style.cssText = 'margin-top:1rem; padding:0.5rem 1rem; background:#4caf50; color:#fff; border:none; border-radius:4px; cursor:pointer;';
      copy.onclick = async () => {
        try { await navigator.clipboard.writeText(r.key); toast('کلید کپی شد', 'ok'); } catch (e) { toast('کپی نشد: ' + e.message, 'err'); }
      };
      const identity = document.createElement('div');
      identity.textContent = r.identity ? 'هویت: ' + r.identity : '';
      identity.style.marginTop = '1rem';
      const close = document.createElement('button');
      close.textContent = 'بستن';
      close.style.cssText = 'margin-left:0.5rem; padding:0.5rem 1rem; background:#666; color:#fff; border:none; border-radius:4px; cursor:pointer;';
      close.onclick = () => modal.remove();
      const h = document.createElement('h3');
      h.textContent = 'کلید API تولید شده';
      box.appendChild(h); box.appendChild(pre); box.appendChild(copy); box.appendChild(identity); box.appendChild(close);
      modal.appendChild(box);
      document.body.appendChild(modal);
      loadApiKeys();
    } catch (e) { toast('خطا: ' + e.message, 'err'); }
  };

  async function toggleAuth(enabled) {
    try {
      await api('/auth/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      toast('احراز هویت: ' + (enabled ? 'فعال' : 'غیرفعال'), 'ok');
      loadApiKeys();
    } catch (e) { toast('خطا: ' + e.message, 'err'); }
  }

  /* ---------------- Config ---------------- */
  async function loadConfig() {
    try {
      const [raw, summary] = await Promise.all([api('/config'), api('/config/summary')]);
      $('#config-content').value = raw.content || '';
      renderHumanConfig(summary);
      setStatus($('#config-status'), '', '');
    } catch (e) {
      setStatus($('#config-status'), 'خطا: ' + e.message, 'err');
    }
  }

  function renderHumanConfig(data) {
    const server = data.server || {}, cdp = data.cdp || {}, auth = data.auth || {};
    $('#cfg-server-host').value = server.host || '';
    $('#cfg-server-port').value = server.port || '';
    $('#cfg-server-threads').value = server.threads || '';
    $('#cfg-provider-concurrency').value = server.provider_concurrency || '';
    $('#cfg-server-debug').checked = server.debug === true;
    $('#cfg-cdp-url').value = cdp.url || '';
    $('#cfg-cdp-timeout').value = cdp.timeout || '';
    $('#cfg-auth-enabled').checked = auth.enabled === true;
    const box = $('#config-providers');
    box.innerHTML = (data.providers || []).map(p => `<div class="card">
      <div class="kv">
        <span class="ltr">${p.id}</span>
        <label class="check"><input id="cfg-provider-enabled-${p.id}" type="checkbox" ${p.enabled ? 'checked' : ''}>فعال</label>
        <span>اولویت</span><b>${p.priority ?? ''}</b>
      </div>
      <div class="btn-row mt">
        <label class="field">CDP<input id="cfg-provider-cdp-${p.id}" class="ctrl ltr" value="${(p.cdp_url || '').replace(/"/g, '&quot;')}"></label>
        <label class="field">مدل پیش‌فرض<input id="cfg-provider-model-${p.id}" class="ctrl" value="${(p.default_upstream_model || '').replace(/"/g, '&quot;')}"></label>
        <label class="check"><input id="cfg-provider-thinking-${p.id}" type="checkbox" ${p.thinking ? 'checked' : ''}>تفکر</label>
        <label class="check"><input id="cfg-provider-search-${p.id}" type="checkbox" ${p.search ? 'checked' : ''}>جستجو</label>
      </div>
    </div>`).join('');
  }

  function collectHumanConfig() {
    const providers = [];
    $$('#config-providers .card').forEach(card => {
      const id = card.querySelector('.ltr')?.textContent?.trim();
      if (!id) return;
      providers.push({
        id,
        enabled: document.getElementById('cfg-provider-enabled-' + id)?.checked === true,
        priority: Number(document.getElementById('cfg-provider-priority-' + id)?.value || card.querySelector('.kv b')?.textContent || 0),
        cdp_url: document.getElementById('cfg-provider-cdp-' + id)?.value || '',
        default_upstream_model: document.getElementById('cfg-provider-model-' + id)?.value || '',
        thinking: document.getElementById('cfg-provider-thinking-' + id)?.checked === true,
        search: document.getElementById('cfg-provider-search-' + id)?.checked === true,
      });
    });
    return {
      server: {
        host: $('#cfg-server-host').value,
        port: Number($('#cfg-server-port').value || 0),
        debug: $('#cfg-server-debug').checked,
        threads: Number($('#cfg-server-threads').value || 0),
        provider_concurrency: Number($('#cfg-provider-concurrency').value || 0),
      },
      cdp: { url: $('#cfg-cdp-url').value, timeout: Number($('#cfg-cdp-timeout').value || 0) },
      auth: { enabled: $('#cfg-auth-enabled').checked },
      providers,
    };
  }

  async function waitForGatewayRecovery(requestId) {
    await new Promise(r => setTimeout(r, 800));
    for (let i = 0; i < 100; i++) {
      try {
        const st = await api('/restart/status?probe=' + Date.now());
        if (st.request_id === requestId) {
          if (st.state === 'completed' && st.success === true) return st;
          if (st.state === 'failed') throw new Error((st.errors || []).join('; ') || 'ری‌استارت ناموفق');
          setStatus($('#config-status'), 'ری‌استارت در حال انجام: ' + (st.state || '') + ' (' + (i + 1) + '/100)', 'working');
        }
      } catch (e) {
        if (String(e.message || '').includes('ری‌استارت ناموفق')) throw e;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
    throw new Error('ری‌استارت در بازه زمانی مورد انتظار تکمیل نشد');
  }

  async function saveHumanConfig() {
    setStatus($('#config-status'), 'در حال ذخیره تنظیمات...', 'working');
    try {
      const r = await api('/config/summary', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collectHumanConfig()),
      });
      if (r.success !== true) throw new Error(r.error || 'ذخیره ناموفق');
      setStatus($('#config-status'), 'تنظیمات ذخیره شد؛ در انتظار ری‌استارت سرویس‌ها...', 'working');
      await waitForGatewayRecovery(r.restart?.request_id);
      setStatus($('#config-status'), 'تنظیمات ذخیره شد و سرویس‌ها بازیابی شدند.', 'ok');
      await loadConfig();
      refreshAll();
    } catch (e) {
      setStatus($('#config-status'), 'خطا: ' + e.message, 'err');
    }
  }

  async function saveRawConfig() {
    setStatus($('#config-status'), 'در حال ذخیره YAML خام...', 'working');
    try {
      const r = await api('/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: $('#config-content').value }),
      });
      if (r.success !== true) throw new Error(r.error || 'ذخیره ناموفق');
      setStatus($('#config-status'), 'YAML ذخیره شد؛ در انتظار ری‌استارت...', 'working');
      await waitForGatewayRecovery(r.restart?.request_id);
      setStatus($('#config-status'), 'YAML ذخیره شد و سرویس‌ها بازیابی شدند.', 'ok');
      await loadConfig();
      refreshAll();
    } catch (e) {
      setStatus($('#config-status'), 'خطا: ' + e.message, 'err');
    }
  }

  /* ---------------- Service ---------------- */
  async function loadServiceStatus() {
    try {
      const data = await api('/service/status');
      const service = data.service || {}, legacy = data.legacy_service || {};
      const status = data.status || service.status || 'Unknown';
      const exists = data.exists === true || service.exists === true;
      const badge = $('#service-status-badge2');
      badge.textContent = exists ? status : 'نصب نشده';
      badge.className = 'badge ' + (exists ? (status === 'Running' ? 'ok' : status === 'Stopped' ? 'bad' : 'warn') : 'neutral');
      $('#svc-start').disabled = exists && status === 'Running';
      $('#svc-stop').disabled = !exists || status !== 'Running';
      $('#svc-restart').disabled = !exists;
      $('#svc-name').textContent = service.name || 'HooshkaWebGateway';
      $('#svc-status-text').textContent = exists ? status : 'نصب نشده';
      $('#svc-start-type').textContent = service.start_type || '-';
      $('#svc-can-stop').textContent = exists ? (service.can_stop ? 'بله' : 'خیر') : '-';
      $('#svc-service-type').textContent = service.service_type || '-';
      $('#svc-legacy').textContent = (legacy.name || '-') + ': ' + (legacy.status || '؟');
      $('#service-message').textContent = !exists ? 'سرویس ویندوز cannonical نصب نشده است.' : '';
      $('#service-raw').textContent = data.output || '';
    } catch (e) {
      $('#service-message').textContent = 'خطا: ' + e.message;
    }
  }

  async function waitForServiceRecovery(requestId) {
    await new Promise(r => setTimeout(r, 900));
    for (let i = 0; i < 60; i++) {
      try {
        const st = await api('/service/restart/status?probe=' + Date.now());
        if (st.request_id === requestId) {
          if (st.state === 'completed' && st.success === true) return st;
          if (st.state === 'failed') throw new Error((st.errors || []).join('; ') || 'ری‌استارت ناموفق');
          const m = $('#service-message'); if (m) m.textContent = 'در حال ری‌استارت: ' + (st.state || '');
        }
      } catch (e) {
        if (String(e.message || '').includes('ری‌استارت ناموفق')) throw e;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
    throw new Error('گیت‌وی در بازه مورد انتظار بازیابی نشد');
  }

  async function serviceAction(action) {
    const label = { start: 'شروع', stop: 'توقف', restart: 'ری‌استارت' }[action] || action;
    if (!confirm(label + ' سرویس؟')) return;
    const btn = $('#svc-' + action);
    const msg = $('#service-message');
    if (btn) btn.disabled = true;
    if (msg) msg.textContent = label + ' در حال انجام...';
    try {
      const r = await api('/service/' + action, { method: 'POST' });
      if (r.success !== true) throw new Error(r.error || 'عملیات ناموفق');
      if (action === 'restart' && r.restart?.request_id) {
        if (msg) msg.textContent = 'ری‌استارت زمان‌بندی شد؛ در انتظار بازیابی گیت‌وی...';
        await waitForServiceRecovery(r.restart.request_id);
        if (msg) msg.textContent = 'گیت‌وی ری‌استارت و بررسی سلامت انجام شد.';
      } else {
        loadServiceStatus();
      }
    } catch (e) {
      if (msg) msg.textContent = 'خطا: ' + e.message;
      toast('سرویس: ' + e.message, 'err');
    } finally {
      await loadServiceStatus();
      if (btn) btn.disabled = false;
    }
  }

  /* ---------------- Logs ---------------- */
  async function loadLogs() {
    const type = $('#log-select').value;
    try {
      const data = await api('/logs/' + encodeURIComponent(type));
      $('#log-content').textContent = data.content || '(خالی)';
      const box = $('#log-content');
      box.scrollTop = box.scrollHeight;
    } catch (e) {
      $('#log-content').textContent = 'خطا: ' + e.message;
    }
  }

  /* ---------------- Init ---------------- */
  function bindStaticActions() {
    $('#reload-models').addEventListener('click', loadModelsTab);
    $('#reload-sessions').addEventListener('click', loadSessions);
    $('#reload-telemetry').addEventListener('click', loadTelemetry);
    $('#log-select').addEventListener('change', loadLogs);
    $('#save-human-config').addEventListener('click', saveHumanConfig);
    $('#reload-config').addEventListener('click', loadConfig);
    $('#save-raw-config').addEventListener('click', saveRawConfig);
    $('#reload-raw-config').addEventListener('click', loadConfig);
    $('#gen-key').addEventListener('click', () => window.HwgGenKey());
    $('#svc-start').addEventListener('click', () => serviceAction('start'));
    $('#svc-stop').addEventListener('click', () => serviceAction('stop'));
    $('#svc-restart').addEventListener('click', () => serviceAction('restart'));

    // Provider form handlers
    $('#btn-add-provider').addEventListener('click', () => showPanel('provider-form'));
    $('#btn-close-provider-form').addEventListener('click', () => showPanel('providers'));
    $('#pf-cancel').addEventListener('click', () => showPanel('providers'));

    $('#pf-save').addEventListener('click', async () => {
      const status = $('#provider-form-status');
      setStatus(status, 'در حال ذخیره...', 'working');
      const data = {
        id: $('#pf-id').value.trim(),
        type: $('#pf-type').value.trim(),
        priority: parseInt($('#pf-priority').value, 10) || 50,
        enabled: $('#pf-enabled').checked,
        config: {
          runtime: {
            cdp_url: $('#pf-cdp').value.trim(),
            profile_dir: $('#pf-profile').value.trim(),
            home_url: $('#pf-homeurl').value.trim(),
          }
        }
      };
      if (!data.id || !data.type) {
        setStatus(status, 'شناسه و نوع پراوایدر الزامی است', 'err');
        return;
      }
      try {
        const r = await api('/providers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        if (r.success) {
          toast('پراوایدر اضافه شد (نیاز به ری‌استارت)', 'ok');
          showPanel('providers');
          loadProviders();
        } else {
          setStatus(status, r.error || 'خطا در ذخیره', 'err');
        }
      } catch (e) {
        setStatus(status, 'خطا: ' + e.message, 'err');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    bindStaticActions();
    initNav();
  });
})();