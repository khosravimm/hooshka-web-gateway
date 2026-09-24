(function () {
  'use strict';

  const PANEL_TITLES = {
    overview: 'وضعیت کلی',
    runtimes: 'Runtimeهای مرورگر',
    profiles: 'پروفایل‌های مرورگر',
    accounts: 'حساب‌ها و Session',
    providers: 'فراهم‌کننده‌ها',
    'provider-form': 'افزودن وب‌چت جدید',
    models: 'مدل‌ها و قابلیت‌ها',
    discovery: 'کاوش و گواهی',
    chat: 'چت تعاملی',
    sessions: 'گفتگوها',
    telemetry: 'آمار مصرف',
    apikeys: 'کلیدها و دسترسی',
    config: 'تنظیمات',
    service: 'سرویس و ری‌استارت',
    work: 'کارهای باقی‌مانده',
    logs: 'گزارش‌ها و شواهد',
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

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
    if (name === 'profiles') loadProfiles();
    if (name === 'accounts') loadAccounts();
    if (name === 'providers') loadProviders();
    if (name === 'models') loadModelsTab();
    if (name === 'discovery') loadDiscovery();
    if (name === 'chat') window.HwgChat && HwgChat.init();
    if (name === 'sessions') loadSessions();
    if (name === 'telemetry') loadTelemetry();
    if (name === 'apikeys') loadApiKeys();
    if (name === 'config') loadConfig();
    if (name === 'service') loadServiceStatus();
    if (name === 'work') loadWorkRegister();
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
      $('#meta-ui').textContent = (ui.version || '-') + (ui.build ? (' · ' + ui.build) : '');
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
      initChart('requests-chart', s.requests_history || []);
      const u = await api('/model_usage');
      renderOutboundKpis($('#outbound-kpis'), s, u);
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

  function renderOutboundKpis(box, stats, usage) {
    if (!box) return;
    const rows = (usage && usage.models) || [];
    const success = rows.reduce((a, r) => a + Number(r.success_count || 0), 0);
    const failure = rows.reduce((a, r) => a + Number(r.failure_count || 0), 0);
    const tokens = rows.reduce((a, r) => a + Number(r.total_tokens || 0), 0);
    const measured = rows.reduce((a, r) => a + Number(r.requests || 0), 0);
    const weightedLatency = rows.reduce((a, r) => a + Number(r.avg_latency_ms || 0) * Number(r.requests || 0), 0);
    const latency = measured ? Math.round(weightedLatency / measured) : null;
    box.innerHTML = [
      ['ارسال به Provider', compact((stats && stats.requests_1h) || 0), 'primary'],
      ['موفق', compact(success), 'ok'],
      ['ناموفق', compact(failure), failure ? 'bad' : 'neutral'],
      ['میانگین تأخیر', latency == null ? '—' : compact(latency) + ' ms', 'neutral'],
      ['توکن اندازه‌گیری‌شده', compact(tokens), 'info'],
    ].map(([label, value, kind]) => `<div class="metric-tile ${kind}"><span>${label}</span><b>${value}</b></div>`).join('');
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
    ctx.fillText('ارسال واقعی به Web Chat در هر دقیقه', pad.left, 18);
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
    const status = $('#runtime-action-global');
    setStatus(status, '', '');
    try {
      const [data, orchestration] = await Promise.all([
        api('/browser-runtimes'), api('/runtime/orchestration')
      ]);
      const agent = orchestration.desktop_agent || {};
      const banner = $('#runtime-agent-state');
      if (banner) {
        const ok = agent.reachable === true;
        banner.className = 'dependency-banner ' + (ok ? 'ok' : 'bad');
        banner.innerHTML = ok
          ? '<b>Desktop Runtime Agent آماده است.</b><span class="ltr">' + (agent.url || '') + '</span>'
          : '<b>عامل کنترل Runtime در دسترس نیست.</b><span>CDPهای موجود ممکن است زنده باشند، اما Start/Restart/Open تا بازگشت Agent غیرفعال است. ' + (agent.url || '-') + '</span>';
      }
      const cards = $('#runtime-cards');
      cards.innerHTML = (data.browser_runtimes || []).map(r => {
        const canOperate = agent.reachable === true;
        const browserState = r.ready ? 'Browser/CDP آماده' : 'Browser/CDP متوقف';
        const profileName = (r.profile || '').split(/[\/]/).filter(Boolean).pop() || '-';
        const children = (r.providers || []).map(p => `
          <div class="runtime-child-row">
            <div><b class="ltr">${p.id}</b><span class="hint">${p.label || ''}</span></div>
            <span class="hint ltr">${p.home_url || '-'}</span>
            <button class="btn ghost btn-xs" data-id="${p.id}" data-open="1" ${canOperate ? '' : 'disabled'}>باز کردن Tab / ورود</button>
          </div>`).join('');
        return `<div class="runtime-operation-card ${r.ready ? 'ready' : 'down'}">
          <div class="runtime-op-head"><div><b>${r.shared ? 'Browser Runtime مشترک' : 'Browser Runtime'}</b><div class="hint">${r.provider_count} Provider / Tab</div></div><span class="badge ${r.ready ? 'ok' : 'bad'}">${browserState}</span></div>
          <div class="runtime-meta"><span>Profile</span><b class="ltr">${profileName}</b><span>CDP</span><b class="ltr">${r.cdp_url || '-'}</b><span>Port</span><b>${r.port || '-'}</b></div>
          <div class="runtime-steps"><span class="step ${r.profile ? 'done' : ''}">Profile</span><span class="step ${r.ready ? 'done' : ''}">Browser</span><span class="step">Session/Auth در سطح Provider</span></div>
          <div class="runtime-children">${children}</div>
          <div class="btn-row mt"><button class="btn primary btn-sm" data-id="${r.representative_provider}" data-act="${r.ready ? 'restart' : 'start'}" ${canOperate ? '' : 'disabled'}>${r.ready ? 'ری‌استارت Browser Runtime' : 'شروع Browser Runtime'}</button></div>
          ${canOperate ? '' : '<div class="hint bad">Agent فقط برای عملیات کنترلی لازم است؛ سبز بودن Browser/CDP به معنی آماده‌بودن Agent یا Login نیست.</div>'}
        </div>`;
      }).join('');
      cards.querySelectorAll('button[data-act]').forEach(b => b.addEventListener('click', () => runtimeAction(b.dataset.id, b.dataset.act, b)));
      cards.querySelectorAll('button[data-open]').forEach(b => b.addEventListener('click', () => window.HwgOpenProvider(b.dataset.id)));
    } catch (e) {
      const cards = $('#runtime-cards');
      if (cards) cards.innerHTML = `<div class="card hint">خطا: ${e.message}</div>`;
    }
    $('#runtime-repair-all').onclick = () => runtimeAction('all', 'repair', null);
  }

  function normPath(v) { return String(v || '').replace(/\\/g, '/').toLowerCase(); }

  async function loadProfiles() {
    try {
      const [profileData, inventory] = await Promise.all([api('/runtime/profiles'), api('/ng/inventory')]);
      renderProfiles(profileData.profiles || [], inventory.account_instances || [], inventory.conflicts || []);
    } catch (e) {
      const box = $('#profiles-grid'); if (box) box.innerHTML = `<div class="hint">خطا: ${e.message}</div>`;
    }
  }

  function renderProfiles(profiles, accounts, conflicts) {
    const box = $('#profiles-grid'); if (!box) return;
    box.innerHTML = profiles.map(p => {
      const pnorm = normPath(p.profile_dir);
      const linked = accounts.filter(a => { const ap=normPath(a.browser_profile?.path); return ap && (pnorm.endsWith(ap) || ap.endsWith(pnorm)); });
      const modes = [...new Set(linked.map(a => a.browser_profile?.sharing_mode).filter(Boolean))];
      const hasConflict = linked.some(a => a.browser_profile?.sharing_mode === 'same_origin_conflict');
      const isolation = hasConflict ? 'Same-origin conflict' : (modes.includes('cross_origin_isolated') ? 'Cross-origin isolated' : (modes[0] || 'بدون Account'));
      const contentState = p.initialized ? 'دارای داده مرورگر' : 'تقریباً خالی';
      const whyLocked = (p.assigned_to || []).length ? 'برای حذف ابتدا اتصال‌های عملیاتی را منتقل کنید.' : '';
      const accountRows = linked.map(a => `<div class="hint"><b class="ltr">${a.account_id}</b> · <span class="ltr">${a.browser_profile?.origin || 'origin?'}</span></div>`).join('');
      return `<div class="profile-card semantic-profile ${p.kind || ''}">
        <div class="profile-card-head"><div><b class="ltr">${p.name}</b><span class="badge neutral">${p.kind || 'profile'}</span></div><span class="badge ${hasConflict ? 'bad' : (linked.length ? 'ok' : 'neutral')}">${isolation}</span></div>
        <div class="hint ltr">${p.profile_dir}</div><div class="profile-purpose">Chrome user-data: Session / Cookie / Local Storage / Browser settings</div>
        <div class="profile-assignment">${linked.length ? 'Accountهای متصل:' : 'Account متصلی ثبت نشده است.'}${accountRows}</div>
        <span class="badge ${p.initialized ? 'info' : 'neutral'}">${contentState}</span>
        ${whyLocked ? `<div class="dependency-note warn">${whyLocked}</div>` : ''}
        <button class="btn danger btn-xs" data-profile-dir="${p.profile_dir}" ${p.deletable ? '' : 'disabled'}>حذف Profile و داده‌های مرورگر</button></div>`;
    }).join('') || '<div class="hint">پروفایلی ثبت نشده است.</div>';
    box.querySelectorAll('[data-profile-dir]').forEach(btn => btn.addEventListener('click', () => deleteProfile(btn.dataset.profileDir)));
    const create=$('#profile-create'); if (create) create.onclick=createProfile;
  }

  async function createProfile() {
    const input = $('#profile-new-name');
    const name = (input.value || '').trim();
    if (!name) { toast('نام پروفایل الزامی است', 'err'); return; }
    try {
      await api('/runtime/profiles', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) });
      input.value = '';
      toast('Profile خالی ساخته شد؛ مرحله بعد اتصال آن به Runtime و سپس Login است.', 'ok');
      await loadProfiles();
      await loadProviders();
    } catch (e) { toast('ساخت پروفایل: ' + e.message, 'err'); }
  }

  async function deleteProfile(profileDir) {
    if (!confirm('این کار تمام Session/Cookie/Local Storage این Profile را حذف می‌کند. ادامه می‌دهید؟')) return;
    try {
      await api('/runtime/profiles', { method: 'DELETE', headers: {'Content-Type':'application/json'}, body: JSON.stringify({profile_dir: profileDir}) });
      toast('Profile و داده‌های مرورگر حذف شد', 'ok');
      await loadProfiles();
      await loadProviders();
    } catch (e) { toast('حذف Profile: ' + e.message, 'err'); }
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

  async function loadAccounts() {
    const box=$('#accounts-grid'), global=$('#accounts-global-status');
    if (global) setStatus(global,'','');
    try {
      const [data, readiness, runtimes] = await Promise.all([api('/accounts'), api('/readiness'), api('/browser-runtimes')]);
      const rmap = new Map((readiness.providers || []).map(r => [r.account_id, r]));
      const groups = runtimes.browser_runtimes || [];
      box.innerHTML = (data.accounts || []).map(a => {
        const b=a.browser_profile || {}, sess=a.session || {}, rr=rmap.get(a.account_id) || {};
        const pnorm=normPath(b.path); const rg=groups.find(g => {const gp=normPath(g.profile); return pnorm && (gp.endsWith(pnorm)||pnorm.endsWith(gp));});
        const access=sess.access_state || sess.state || 'UNKNOWN';
        const ready=rr.ready===true && rr.current===true;
        const readinessText=ready ? 'READY عملکردی' : (rr.state==='READY' ? 'STALE · Probe لازم' : (rr.state || 'UNKNOWN'));
        const failedStage=(rr.stages || []).find(x => x.ok === false); const checkedAt=rr.checked_at ? new Date(rr.checked_at).toLocaleString('fa-IR') : 'ثبت نشده';
        const readinessReason=ready ? 'Evidence معتبر و جاری است.' : (rr.state==='READY' ? 'Evidence منقضی شده؛ Probe را دوباره اجرا کنید.' : (failedStage ? ('توقف در '+failedStage.stage) : 'Evidence آمادگی ثبت نشده است.'));
        const providerId=(a.provider_profile_id || '').split(':')[0] || a.provider_id || '';
        const conflict=b.sharing_mode==='same_origin_conflict';
        return `<div class="profile-card account-card ${conflict?'conflict':''}">
          <div class="profile-card-head"><div><b class="ltr">${a.account_id}</b><span class="badge neutral ltr">${a.provider_profile_id || '-'}</span></div><span class="badge ${access==='AUTHENTICATED'?'ok':(access==='BLOCKED'?'bad':'warn')}">${access}</span></div>
          <div class="relationship-preview"><b>Provider Profile</b> <span class="ltr">${a.provider_profile_id || '-'}</span> → <b>Account</b> <span class="ltr">${a.account_id}</span> → <b>Profile/Origin</b> <span class="ltr">${b.path || '-'} · ${b.origin || '-'}</span> → <b>Runtime</b> <span class="ltr">${rg?.cdp_url || a.runtime?.cdp_url || 'provider runtime'}</span></div>
          <div class="kv"><span>Isolation</span><b>${b.sharing_mode || b.ownership || 'unknown'}</b><span>Session</span><b>${access}</b><span>Readiness</span><b>${readinessText}</b><span>Evidence</span><b>${checkedAt}</b><span>چرا/قدم بعد</span><b>${readinessReason}</b></div>
          ${conflict ? '<div class="dependency-note warn">Same-origin multi-account conflict: این Account باید Profile/Runtime مستقل داشته باشد.</div>' : ''}
          <div class="btn-row mt"><button class="btn ghost btn-xs" data-account="${a.account_id}" data-aa="validate">Validate Session</button><button class="btn primary btn-xs" data-account="${a.account_id}" data-aa="login">Open / Login</button><button class="btn ghost btn-xs" data-account="${a.account_id}" data-aa="reauth">Re-auth</button><button class="btn primary btn-xs" data-account="${a.account_id}" data-provider-ready="${providerId}" ${providerId ? '' : 'disabled'}>اجرای Readiness</button><button class="btn danger btn-xs" data-account="${a.account_id}" data-aa="logout">Logout</button></div>
          <div class="status-line" id="account-status-${a.account_id}"></div></div>`;
      }).join('') || '<div class="hint">Account Instance ثبت نشده است.</div>';
      box.querySelectorAll('[data-aa]').forEach(btn => btn.addEventListener('click', () => accountAction(btn.dataset.account, btn.dataset.aa, btn)));
      box.querySelectorAll('[data-provider-ready]').forEach(btn => btn.addEventListener('click', async () => { btn.disabled=true; const orig=btn.textContent; btn.textContent='در حال Probe...'; try { await api('/providers/'+encodeURIComponent(btn.dataset.providerReady)+'/readiness/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({execution_authority:'automated_validation',ttl_seconds:300})}); toast('Readiness Probe اجرا شد','ok'); await loadAccounts(); } catch(e){ toast('Readiness: '+e.message,'err'); } finally { btn.disabled=false; btn.textContent=orig; } }));
    } catch(e) { if(box) box.innerHTML=`<div class="hint">خطا: ${e.message}</div>`; }
  }

  async function accountAction(accountId, action, btn) {
    const status=document.getElementById('account-status-'+accountId), orig=btn.textContent;
    if(action==='logout' && !confirm('Logout فقط Origin همین Account را پاک می‌کند. ادامه می‌دهید؟')) return;
    btn.disabled=true; btn.textContent='در حال انجام...'; setStatus(status,'در حال اجرا و سپس راستی‌آزمایی...','working');
    try {
      if(action==='validate') await api('/accounts/'+encodeURIComponent(accountId)+'/session');
      else if(action==='login') await api('/accounts/'+encodeURIComponent(accountId)+'/login/open',{method:'POST'});
      else if(action==='reauth') await api('/accounts/'+encodeURIComponent(accountId)+'/reauth',{method:'POST'});
      else if(action==='logout') await api('/accounts/'+encodeURIComponent(accountId)+'/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true})});
      await new Promise(r=>setTimeout(r, action==='validate'?0:500));
      const verified=await api('/accounts/'+encodeURIComponent(accountId)+'/session');
      const state=verified.lifecycle?.access_state || verified.access?.state || 'UNKNOWN';
      setStatus(status,'راستی‌آزمایی پس از عملیات: '+state,'ok');
      toast('Account '+accountId+': '+state,'ok');
      await loadAccounts();
    } catch(e) { setStatus(status,'خطا: '+e.message,'err'); toast('Account: '+e.message,'err'); }
    finally { btn.disabled=false; btn.textContent=orig; }
  }

  /* ---------------- Providers ---------------- */
  async function loadProviders(opts) {
    let data;
    try { data = await api('/providers'); }
    catch (e) { return; }
    const providers = data.providers || [];
    $('#stat-providers').textContent = providers.length;
    const enabled = providers.filter(p => p.enabled === true);
    const ready = enabled.filter(p => p.readiness?.ready === true && p.readiness?.current === true).length;
    $('#stat-ready').textContent = ready + '/' + enabled.length;
    $('#stat-sessions').textContent = '؟';
    $('#health-api').textContent = 'پاسخگو';

    const summary = $('#provider-runtime-summary');
    if (summary) {
      summary.innerHTML = providers.map(p => {
        const functionalReady = p.readiness?.ready === true && p.readiness?.current === true;
        const stateClass = functionalReady ? 'ready' : (p.runtime?.ready ? 'unknown' : 'down');
        const rawReadiness = p.readiness?.state || 'UNKNOWN';
        const stateLabel = functionalReady ? 'READY عملکردی' : (rawReadiness === 'READY' ? 'STALE · Probe لازم' : (rawReadiness || (p.runtime?.ready ? 'نیازمند Probe' : 'Browser در دسترس نیست')));
        return `<div class="provider-status-card ${stateClass}">
          <div class="provider-status-head"><span class="status-dot"></span><b class="ltr">${p.id}</b></div>
          <div class="provider-status-state">${stateLabel}</div>
          <div class="provider-status-meta">${p.enabled ? 'فعال' : 'غیرفعال'} · Browser: ${p.runtime?.status || 'unknown'} · Readiness: ${stateLabel}</div>
        </div>`;
      }).join('');
    }

    if (opts && opts.quiet) return;

    const grid = $('#providers-grid');
    grid.innerHTML = providers.map(p => {
      const functionalReady = p.readiness?.ready === true && p.readiness?.current === true;
      const canEnable = p.enabled || functionalReady;
      const rawReadiness = p.readiness?.state || 'UNKNOWN';
      const readyLabel = functionalReady ? 'READY' : (rawReadiness === 'READY' ? 'STALE · Probe لازم' : rawReadiness);
      const featureBadges = Object.entries(p.capabilities || {}).filter(([k,v]) => v === true).map(([k]) => `<span class="cap-badge">${k}</span>`).join('');
      const modelOptions = (p.model?.options || [p.model?.default || p.id]).map(m => `<option value="${m.replace(/"/g,'&quot;')}">${m}</option>`).join('');
      return `<div class="card provider-relationship-card">
        <div class="card-head"><div><b class="ltr">${p.id}</b><div class="hint">${p.type} · اولویت ${p.priority}</div></div><div class="btn-row"><span class="badge ${p.runtime?.ready ? 'ok' : 'bad'}">Browser ${p.runtime?.ready ? 'ready' : 'down'}</span><span class="badge ${functionalReady ? 'ok' : 'neutral'}">${readyLabel}</span></div></div>
        <div class="relationship-preview"><b>Provider</b> <span class="ltr">${p.id}</span> → <b>Profile</b> <span class="ltr">${p.profile_dir || '-'}</span> → <b>Readiness</b> ${readyLabel}</div>
        <div class="grid-2 mt">
          <div><div class="hint">قابلیت‌های اعلام‌شده</div><div class="capability-badges">${featureBadges || '<span class="hint">ثبت نشده</span>'}</div></div>
          <div><div class="hint">وضعیت فعال‌سازی</div><label class="provider-switch"><input type="checkbox" ${p.enabled ? 'checked' : ''} ${canEnable ? '' : 'disabled'} onchange="window.HwgProviderEnabled && HwgProviderEnabled('${p.id}',this.checked)"><span>${p.enabled ? 'فعال' : (functionalReady ? 'آماده فعال‌سازی' : 'پس از READY قابل فعال‌سازی')}</span></label></div>
        </div>
        <div class="grid-2 mt">
          <div class="card compact-card"><div class="hint">مدل پیش‌فرض</div><div class="btn-row"><select class="ctrl" id="model-${p.id}">${modelOptions}</select><button class="btn primary btn-xs" onclick="window.HwgModelSave && HwgModelSave('${p.id}')">ذخیره مدل</button></div><div class="hint">فعلی: <span class="ltr">${p.model?.default || p.id}</span></div><div id="model-status-${p.id}" class="status-line"></div></div>
          <div class="card compact-card"><div class="hint">Feature defaults</div><div class="btn-row"><label class="check"><input type="checkbox" ${p.features?.defaults?.thinking ? 'checked' : ''} ${p.features?.controls?.thinking ? '' : 'disabled'} onchange="window.HwgProvidersToggle && HwgProvidersToggle('${p.id}','thinking',this.checked)"><span>Thinking ${p.features?.controls?.thinking ? '' : '(N/A)'}</span></label><label class="check"><input type="checkbox" ${p.features?.defaults?.search ? 'checked' : ''} ${p.features?.controls?.search ? '' : 'disabled'} onchange="window.HwgProvidersToggle && HwgProvidersToggle('${p.id}','search',this.checked)"><span>Search ${p.features?.controls?.search ? '' : '(N/A)'}</span></label></div></div>
        </div>
        <div class="btn-row mt"><button class="btn ghost btn-xs" onclick="window.HwgGoRuntime && HwgGoRuntime()">Browser Runtime</button><button class="btn ghost btn-xs" onclick="window.HwgGoAccounts && HwgGoAccounts()">Accounts</button><button class="btn primary btn-xs" id="ready-${p.id}" onclick="window.HwgReadinessProbe && HwgReadinessProbe('${p.id}')" ${p.runtime?.ready ? '' : 'disabled'}>اجرای Readiness</button><button class="btn ghost btn-xs" id="test-${p.id}" onclick="window.HwgTestProvider && HwgTestProvider('${p.id}')" ${p.runtime?.ready ? '' : 'disabled'}>تست Provider</button><button class="btn btn-danger btn-xs" onclick="window.HwgDeleteProvider && HwgDeleteProvider('${p.id}')">حذف</button></div>
        ${!p.runtime?.ready ? '<div class="dependency-note warn mt">ابتدا Browser Runtime را آماده کنید.</div>' : (!functionalReady ? '<div class="dependency-note mt">فعال‌سازی عملیاتی بعد از Readiness معتبر انجام می‌شود.</div>' : '')}
        <div id="ready-status-${p.id}" class="status-line"></div><div id="test-status-${p.id}" class="status-line"></div>
      </div>`;
    }).join('') || '<div class="hint">Provider ثبت نشده است.</div>';
  }

  window.HwgProviderEnabled = async function (providerId, enabled) {
    try {
      const r = await api('/providers/' + encodeURIComponent(providerId) + '/settings', {
        method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({enabled})
      });
      toast(providerId + (enabled ? ' فعال شد' : ' غیرفعال شد') + (r.restart?.scheduled ? '؛ ری‌استارت زمان‌بندی شد' : ''), 'ok');
      await loadProviders();
    } catch (e) { toast('تغییر وضعیت Provider: ' + e.message, 'err'); await loadProviders(); }
  };

  window.HwgGoRuntime = function () { showPanel('runtimes'); };
  window.HwgGoAccounts = function () { showPanel('accounts'); };

  window.HwgRuntimeProfile = async function (providerId) {
    const select = document.getElementById('runtime-profile-' + providerId);
    if (!select || !select.value) { toast('Profile انتخاب نشده است', 'err'); return; }
    try {
      const r = await api('/providers/' + encodeURIComponent(providerId) + '/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({profile_dir:select.value})});
      toast('Profile به Runtime متصل شد' + (r.restart?.scheduled ? '؛ بازخوانی زمان‌بندی شد' : ''), 'ok');
      await Promise.all([loadRuntimes(), loadProviders()]);
    } catch (e) { toast('اتصال Profile: ' + e.message, 'err'); }
  };

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

  window.HwgReadinessProbe = async function (providerId) {
    const status = document.getElementById('ready-status-' + providerId);
    const btn = document.getElementById('ready-' + providerId);
    setStatus(status, 'در حال اجرای زنجیره آمادگی...', 'working');
    if (btn) btn.disabled = true;
    try {
      const r = await api('/providers/' + encodeURIComponent(providerId) + '/readiness/probe', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({execution_authority:'automated_validation', ttl_seconds:300})
      });
      const stage = (r.stages || []).find(x => x.ok === false)?.stage;
      setStatus(status, r.ready ? 'READY - Probe واقعی پاس شد' : ('آماده نیست: ' + (r.state || stage || 'unknown')), r.ready ? 'ok' : 'warn');
      await loadProviders({quiet:false});
    } catch (e) {
      setStatus(status, 'خطا: ' + e.message, 'err');
    } finally {
      if (btn) btn.disabled = false;
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

  let providerWizard = { analysis:null, observation:null, candidate:null, runtimes:[] };

  function resetProviderWizard() {
    providerWizard = { analysis:null, observation:null, candidate:null, runtimes:[] };
    $('#pf-url').value='';
    $('#pf-proposal-card').classList.add('wizard-hidden');
    $('#pf-observation-card').classList.add('wizard-hidden');
    $('#pf-proposal').innerHTML=''; $('#pf-observation').innerHTML=''; $('#pf-next-action').innerHTML='';
    $('#pf-save').disabled=true; setStatus($('#provider-form-status'),'','');
  }

  async function loadProviderForm() {
    resetProviderWizard();
    try {
      const data=await api('/browser-runtimes'); providerWizard.runtimes=data.browser_runtimes||[];
    } catch(e) { setStatus($('#provider-form-status'),'بارگذاری Runtimeها شکست خورد: '+e.message,'err'); }
  }

  function fillWizardRuntimeSelect(recommendedKey) {
    const sel=$('#pf-runtime');
    sel.innerHTML=(providerWizard.runtimes||[]).map(r=>{
      const profile=(r.profile||'').split(/[\\/]/).filter(Boolean).pop()||'-';
      const ready=r.ready?'آماده':'متوقف';
      return `<option value="${esc(r.runtime_key)}" ${r.runtime_key===recommendedKey?'selected':''}>${esc(ready+' · '+profile+' · '+(r.port||'-'))}</option>`;
    }).join('') || '<option value="">Runtime آماده‌ای وجود ندارد</option>';
  }

  function renderWizardProposal(a) {
    fillWizardRuntimeSelect(a.recommended_runtime_key);
    const existing=(a.existing_origin_provider_ids||[]);
    const adapter=existing.length ? `این Origin قبلاً با Provider <b class="ltr">${esc(existing.join(', '))}</b> ثبت شده است؛ پیشنهاد HWG استفاده از همان Provider و افزودن Account در صورت نیاز است.` : (a.reuse_existing_adapter ? `Adapter موجود قابل استفاده است: <b class="ltr">${esc(a.known_adapter_type)}</b>` : 'Provider جدید است؛ ابتدا Candidate کاوش ساخته می‌شود و Adapter بعد از Evidence پیشنهاد خواهد شد.');
    $('#pf-proposal').innerHTML=`<div class="kv"><span>نام پیشنهادی</span><b>${esc(a.suggested_name)}</b><span>شناسه پیشنهادی</span><b class="ltr">${esc(a.suggested_provider_id)}</b><span>Origin</span><b class="ltr">${esc(a.origin)}</b><span>پیشنهاد</span><b>${adapter}</b></div>`;
    $('#pf-proposal-card').classList.remove('wizard-hidden');
    $('#pf-observe').textContent=existing.length?'مشاهده دوباره صفحه':'باز کردن و مشاهده از دید کاربر';
  }
  /* ---------------- Models & Capabilities ---------------- */
  async function loadModelsTab() {
    try {
      const caps = await fetch('/v1/capabilities', { cache: 'no-store' }).then(r => r.json());
      const models = await fetch('/v1/models', { cache: 'no-store' }).then(r => r.json());
      const prov = await api('/providers');
      const readiness = await api('/readiness');

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

      const certBox = $('#models-certification-scope');
      if (certBox) {
        certBox.innerHTML = (readiness.providers || []).map(r => {
          const current = r.ready === true && r.current === true;
          const failed = (r.stages || []).find(x => x.ok === false);
          const age = r.checked_at ? new Date(r.checked_at).toLocaleString('fa-IR') : 'ثبت نشده';
          const state = current ? 'READY جاری' : (r.state === 'READY' ? 'STALE' : (r.state || 'UNKNOWN'));
          const scope = [r.provider_id, r.account_id || 'account?', r.model || 'model?'].join(' / ');
          const why = current ? 'Evidence معتبر است.' : (failed ? ('توقف در '+failed.stage) : 'Evidence جاری وجود ندارد؛ Probe لازم است.');
          return `<div class="work-item"><div><b class="ltr">${scope}</b><span class="badge ${current?'ok':(r.state==='BLOCKED'?'bad':'warn')}">${state}</span></div><div class="hint">Evidence: ${age} · ${why}</div></div>`;
        }).join('') || '<div class="hint">Readiness Evidence ثبت نشده است.</div>';
      }

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
    $('#cfg-cdp-timeout').value = cdp.timeout || '';
    $('#cfg-auth-enabled').checked = auth.enabled === true;
    const box = $('#config-providers');
    box.innerHTML = (data.providers || []).map(p => `<div class="card">
      <div class="kv">
        <span class="ltr">${p.id}</span>
        <span class="badge ${p.enabled ? 'ok' : 'neutral'}">${p.enabled ? 'فعال' : 'غیرفعال'}</span>
        <span>اولویت</span><b>${p.priority ?? ''}</b>
      </div>
      <div class="btn-row mt">
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
        priority: Number(document.getElementById('cfg-provider-priority-' + id)?.value || card.querySelector('.kv b')?.textContent || 0),
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
      cdp: { timeout: Number($('#cfg-cdp-timeout').value || 0) },
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
      const [data, orchestration, health] = await Promise.all([api('/service/status'), api('/runtime/orchestration'), api('/health')]);
      const service=data.service||{}, legacy=data.legacy_service||{}, agent=orchestration.desktop_agent||{};
      const status=data.status||service.status||'Unknown', exists=data.exists===true||service.exists===true;
      const badge=$('#service-status-badge2'); badge.textContent=exists?status:(health.status?'Gateway زنده / Service نصب نیست':'نصب نشده'); badge.className='badge '+(health.status?'ok':(exists?'warn':'neutral'));
      $('#svc-start').disabled=!exists || status==='Running'; $('#svc-stop').disabled=!exists || status!=='Running'; $('#svc-restart').disabled=!exists;
      $('#svc-name').textContent=service.name||'HooshkaHWGNGDevGateway'; $('#svc-status-text').textContent=exists?status:'NotInstalled'; $('#svc-start-type').textContent=service.start_type||'-'; $('#svc-can-stop').textContent=exists?(service.can_stop?'بله':'خیر'):'-'; $('#svc-service-type').textContent=service.service_type||'-'; $('#svc-legacy').textContent=(legacy.name||'-')+': '+(legacy.status||'؟');
      $('#svc-gateway-runtime').textContent=exists?'Windows Service':'Direct Gateway Process'; $('#svc-gateway-health').textContent=health.status||'unknown'; $('#svc-agent-status').textContent=agent.reachable===true?'reachable':'down'; $('#svc-agent-task').textContent=(agent.task||'-')+(agent.task_exists===true?' · exists':' · missing');
      $('#service-message').textContent=!exists ? 'Windows Service canonical نصب نیست؛ Gateway توسعه به‌صورت process مستقیم اجراست. عملیات سرویس تا نصب مسیر canonical غیرفعال است.' : ''; $('#service-raw').textContent=data.output||'';
    } catch(e){ $('#service-message').textContent='خطا: '+e.message; }
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

  /* ---------------- Discovery / certification ---------------- */
  async function loadDiscovery() {
    const status = $('#discovery-create-status');
    try {
      const [inventory, runsData] = await Promise.all([api('/ng/inventory'), api('/discovery/runs')]);
      const select = $('#discovery-provider');
      const current = select.value;
      select.innerHTML = (inventory.provider_profiles || []).map(p => `<option value="${p.provider_id}">${p.provider_id}</option>`).join('');
      if (current && Array.from(select.options).some(o => o.value === current)) select.value = current;
      renderDiscoveryRuns(runsData.runs || [], runsData.self_use || {});
      $('#discovery-refresh').onclick = loadDiscovery;
      $('#discovery-new-run').onclick = async () => {
        const provider_id = select.value;
        const account_id = ($('#discovery-account').value || '').trim() || null;
        const recipe_version = ($('#discovery-recipe').value || '').trim() || 'webchat-standard-v1';
        if (!provider_id) { setStatus(status, 'Provider انتخاب نشده است', 'err'); return; }
        setStatus(status, 'در حال ایجاد Run...', 'working');
        try {
          const result = await api('/discovery/runs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({provider_id, account_id, recipe_version})});
          setStatus(status, 'Run ایجاد شد؛ مرحله بعد Research-first است.', 'ok');
          toast('Discovery Run: ' + result.run.run_id, 'ok');
          await loadDiscovery();
        } catch (e) { setStatus(status, e.message, 'err'); }
      };
    } catch (e) {
      setStatus(status, 'خطا: ' + e.message, 'err');
    }
  }

  function renderDiscoveryRuns(runs, selfUse) {
    const box = $('#discovery-runs');
    box.innerHTML = runs.map(r => {
      let action = '';
      const selfGate = selfUse[r.provider_id] || {allowed:false,reasons:['qualification_missing']};
      const selfGateText = selfGate.allowed ? 'QUALIFIED' : (selfGate.reasons || []).join(', ');
      if (r.state === 'RESEARCH_REQUIRED') action = `<div class="btn-row"><input class="ctrl ltr" id="research-${r.run_id}" placeholder="مرجع رسمی/داخلی/پروژه بالغ"><button class="btn primary btn-sm" data-disc-act="research" data-provider="${r.provider_id}" data-run="${r.run_id}">ثبت Research</button></div>`;
      if (r.state === 'BASELINE_REQUIRED') action = `<button class="btn primary btn-sm" data-disc-act="baseline" data-provider="${r.provider_id}" data-run="${r.run_id}">ثبت Baseline واقعی</button>`;
      if (['WAITING_FOR_LOGIN','WAITING_FOR_USER_INTERACTION','DIAGNOSTIC_REQUIRED','BLOCKED'].includes(r.state)) action = `<div class="work-gate"><div class="hint">${r.state === 'WAITING_FOR_LOGIN' ? 'ورود به حساب لازم است. پس از ورود Baseline دوباره بررسی می‌شود.' : r.state === 'WAITING_FOR_USER_INTERACTION' ? 'تعامل کاربر مانند CAPTCHA/Verification لازم است. پس از رفع آن Baseline دوباره بررسی می‌شود.' : r.state === 'BLOCKED' ? 'دسترسی Provider/Account مسدود است. Exploration متوقف می‌ماند و دورزدن مجاز نیست.' : 'وضعیت دسترسی نامشخص است و باید دوباره تشخیص داده شود.'}</div><button class="btn primary btn-sm mt" data-disc-act="baseline" data-provider="${r.provider_id}" data-run="${r.run_id}">بررسی مجدد وضعیت دسترسی</button></div>`;
      if (r.state === 'EXPLORATION_READY') action = `<div class="behavior-lab"><div class="grid-3"><input class="ctrl ltr" id="behavior-selector-${r.run_id}" placeholder="CSS selector"><select class="ctrl" id="behavior-kind-${r.run_id}"><option value="hover">Hover</option><option value="focus">Focus</option><option value="click">Click</option></select><input class="ctrl" id="behavior-purpose-${r.run_id}" placeholder="هدف مشاهده رفتار"></div><label class="check mt"><input type="checkbox" id="behavior-confirm-${r.run_id}"><span>برای Click این اقدام را صریحاً تأیید می‌کنم</span></label><div class="btn-row mt"><button class="btn ghost btn-sm" data-disc-act="behavior" data-provider="${r.provider_id}" data-run="${r.run_id}">اجرای Behavior Probe</button><button class="btn primary btn-sm" data-disc-act="explore" data-provider="${r.provider_id}" data-run="${r.run_id}">تکمیل Exploration فقط‌خواندنی</button></div><details class="mt"><summary class="hint">کمک گرفتن از AI برای ابهام‌های باقی‌مانده</summary><div class="grid-3 mt"><input class="ctrl" id="ai-question-${r.run_id}" placeholder="سؤال یا ابهام باقی‌مانده"><select class="ctrl" id="ai-route-${r.run_id}"><option value="least_loaded">کم‌بارترین مدل سالم</option><option value="weighted_load">وزن/بار</option><option value="ordered">ترتیب تنظیم‌شده</option></select><label class="check"><input type="checkbox" id="ai-confirm-${r.run_id}"><span>اجازه استفاده از مدل فعال HWG را می‌دهم</span></label></div><label class="check mt"><input type="checkbox" id="ai-target-${r.run_id}" ${selfGate.allowed ? '' : 'disabled'}><span>استفاده از خود Provider هدف — ${selfGate.allowed ? 'Transport Qualified' : 'مسدود: ' + selfGateText}</span></label>${selfGate.allowed ? '' : `<div class="hint mt">صلاحیت Self-use با آزمون خودکار nonce و بدون دخالت AI بررسی می‌شود.</div><button class="btn ghost btn-sm mt" data-disc-act="self-qualify" data-provider="${r.provider_id}" data-run="${r.run_id}">اجرای آزمون خودکار صلاحیت Self-use</button>`}<button class="btn ghost btn-sm mt" data-disc-act="ai-assist" data-provider="${r.provider_id}" data-run="${r.run_id}">تحلیل کمکی با AI</button></details></div>`;
      if (r.state === 'UPDATE_CANDIDATE') action = `<div><input class="ctrl" id="review-note-${r.run_id}" placeholder="یادداشت Review"><div class="btn-row mt"><button class="btn success btn-sm" data-disc-act="review-accept" data-provider="${r.provider_id}" data-run="${r.run_id}">ACCEPT</button><button class="btn ghost btn-sm" data-disc-act="review-hold" data-provider="${r.provider_id}" data-run="${r.run_id}">HOLD</button><button class="btn danger btn-sm" data-disc-act="review-reject" data-provider="${r.provider_id}" data-run="${r.run_id}">REJECT</button></div></div>`;
      if (r.state === 'CERTIFICATION_REQUIRED') action = `<div class="btn-row"><button class="btn success btn-sm" data-disc-act="cert-auto" data-provider="${r.provider_id}" data-run="${r.run_id}">اجرای Certification خودکار / E2</button><button class="btn ghost btn-sm" data-disc-act="cert-start" data-provider="${r.provider_id}" data-run="${r.run_id}">ثبت پذیرش/مشاهده انسانی</button></div><div class="hint mt">Certification فنی خودکار از round-trip واقعی و Evidence ماشینی استفاده می‌کند؛ کنترل انسانی مسیر جداگانه Acceptance است.</div>`;
      if (r.state === 'CERTIFYING') action = `<div><input class="ctrl ltr" id="cert-evidence-${r.run_id}" placeholder="Evidence record/path"><label class="check mt"><input type="checkbox" id="cert-confirm-${r.run_id}"><span>نتیجه را شخصاً مشاهده و تأیید کردم</span></label><div class="btn-row mt"><button class="btn success btn-sm" data-disc-act="cert-pass" data-provider="${r.provider_id}" data-run="${r.run_id}">ثبت PASS / E2</button><button class="btn ghost btn-sm" data-disc-act="cert-hold" data-provider="${r.provider_id}" data-run="${r.run_id}">HOLD</button></div></div>`;
      return `<div class="work-item"><div><b class="ltr">${r.provider_id}</b><span class="badge">${r.state}</span><span class="badge">${r.evidence_level}</span></div><div class="hint ltr">run=${r.run_id}</div><div class="hint">Account: <span class="ltr">${r.account_id || '-'}</span> · Recipe: <span class="ltr">${r.recipe_version}</span> · Decision: ${r.decision || 'PENDING'}</div>${action}</div>`;
    }).join('') || '<div class="work-item discovery-empty"><b>هنوز Run ثبت نشده است.</b><div class="hint">برای شروع، Provider و در صورت وجود Account Instance را انتخاب کنید. Run همیشه از RESEARCH_REQUIRED آغاز می‌شود؛ سپس Baseline وضعیت Runtime/Page/Login را می‌سنجد. Exploration فقط پس از عبور از Access Gate اجرا می‌شود و هیچ یافته‌ای مستقیماً Profile عملیاتی را تغییر نمی‌دهد.</div><div class="hint mt">مسیر بعدی: Research → Baseline → Exploration → Candidate → Certification. در ابهام‌های باقی‌مانده Behavior Lab و AI-assisted analysis قابل استفاده‌اند.</div></div>';
    box.querySelectorAll('[data-disc-act]').forEach(btn => btn.addEventListener('click', () => discoveryRunAction(btn)));
  }

  async function discoveryRunAction(btn) {
    const provider = btn.dataset.provider, run = btn.dataset.run, action = btn.dataset.discAct;
    btn.disabled = true;
    try {
      let body = null;
      let endpoint = action;
      if (action === 'research') {
        const ref = (document.getElementById('research-' + run)?.value || '').trim();
        if (!ref) throw new Error('مرجع Research الزامی است');
        body = {sources:[{kind:'reviewed_reference', ref}]};
      } else if (action === 'behavior') {
        endpoint = 'behavior';
        const selector = (document.getElementById('behavior-selector-' + run)?.value || '').trim();
        const kind = document.getElementById('behavior-kind-' + run)?.value || 'hover';
        const purpose = (document.getElementById('behavior-purpose-' + run)?.value || '').trim() || 'behavior observation';
        const confirmed_by_user = document.getElementById('behavior-confirm-' + run)?.checked === true;
        if (!selector) throw new Error('CSS selector برای Behavior Probe الزامی است');
        if (kind === 'click' && !confirmed_by_user) throw new Error('Click فقط با تأیید صریح کاربر مجاز است');
        body = {kind, selector, purpose, confirmed_by_user};
      } else if (action === 'self-qualify') {
        endpoint = 'self-use-qualify';
        body = {execution_authority:'automated_validation'};
      } else if (action === 'ai-assist') {
        endpoint = 'ai-assist';
        const question = (document.getElementById('ai-question-' + run)?.value || '').trim();
        const confirmed_by_user = document.getElementById('ai-confirm-' + run)?.checked === true;
        if (!question) throw new Error('سؤال unresolved برای AI الزامی است');
        if (!confirmed_by_user) throw new Error('استفاده از مدل فقط با مجوز صریح کاربر انجام می‌شود');
        body = {unresolved_questions:[question], confirmed_by_user, routing_policy:document.getElementById('ai-route-' + run)?.value || 'least_loaded', allow_target_provider:document.getElementById('ai-target-' + run)?.checked === true};
      } else if (action.startsWith('review-')) {
        endpoint = 'review';
        body = {decision: action.split('-')[1].toUpperCase(), note:(document.getElementById('review-note-' + run)?.value || '').trim()};
      } else if (action === 'cert-auto') {
        endpoint = 'certification/auto';
        body = {execution_authority:'automated_validation'};
      } else if (action === 'cert-start') {
        endpoint = 'certification/start';
      } else if (action === 'cert-pass' || action === 'cert-hold') {
        endpoint = 'certification/complete';
        const evidence_record = (document.getElementById('cert-evidence-' + run)?.value || '').trim();
        const confirmed_by_user = document.getElementById('cert-confirm-' + run)?.checked === true;
        const passed = action === 'cert-pass';
        if (passed && !evidence_record) throw new Error('Evidence record برای PASS الزامی است');
        if (passed && !confirmed_by_user) throw new Error('تأیید صریح کاربر برای E2 الزامی است');
        body = {passed, evidence_record, confirmed_by_user};
      }
      const result = await api('/discovery/runs/' + encodeURIComponent(provider) + '/' + encodeURIComponent(run) + '/' + endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})});
      toast('Discovery: ' + result.run.state, 'ok');
      await loadDiscovery();
    } catch (e) { toast('Discovery: ' + e.message, 'err'); }
    finally { btn.disabled = false; }
  }

  /* ---------------- Remaining work / governance ---------------- */
  async function loadWorkRegister() {
    try {
      const data = await api('/governance/work-register');
      const s = data.summary || {};
      $('#work-total').textContent = s.total ?? '-';
      $('#work-open').textContent = s.open ?? '-';
      $('#work-p0').textContent = s.p0_open ?? '-';
      $('#work-version').textContent = s.version || '-';
      const badge = $('#work-register-valid');
      badge.textContent = data.valid ? 'معتبر' : 'خطای Register';
      badge.className = 'badge ' + (data.valid ? 'hwg-ok' : 'hwg-bad');
      $('#work-next-actions').innerHTML = (s.next_actions || []).map(x =>
        `<div class="work-item"><b class="ltr">${x.id}</b><span>${x.title}</span><span class="badge">${x.priority}</span><span class="hint ltr">${x.target_version}</span></div>`
      ).join('') || '<div class="hint">اقدام آماده‌ای وجود ندارد.</div>';
      $('#work-register-list').innerHTML = (data.items || []).map(x =>
        `<div class="work-item"><div><b class="ltr">${x.id}</b><span class="badge">${x.status}</span><span class="badge">${x.priority}</span></div><div>${x.title}</div><div class="hint">هدف: <span class="ltr">${x.target_version}</span> · وابستگی: ${(x.depends_on || []).join('، ') || 'ندارد'}</div></div>`
      ).join('');
    } catch (e) {
      const badge = $('#work-register-valid');
      if (badge) { badge.textContent = 'خطا'; badge.className = 'badge hwg-bad'; }
      const list = $('#work-register-list');
      if (list) list.innerHTML = `<div class="hint">${e.message}</div>`;
    }
  }

  /* ---------------- Logs ---------------- */
  async function loadLogs() {
    const type=$('#log-select').value;
    try {
      const [data,evidence]=await Promise.all([api('/logs/'+encodeURIComponent(type)),api('/evidence/index')]);
      $('#log-content').textContent=data.content||'(خالی)'; const box=$('#log-content'); box.scrollTop=box.scrollHeight;
      const ebox=$('#evidence-index'); if (ebox) ebox.innerHTML=(evidence.records||[]).map(r=>`<div class="work-item"><div><span class="badge">${r.category}</span><b>${r.title||r.file}</b></div><div class="hint ltr">${r.file}</div><div class="hint">${r.modified_epoch?new Date(r.modified_epoch*1000).toLocaleString('fa-IR'):'-'}</div></div>`).join('')||'<div class="hint">Evidence ساختاریافته‌ای ثبت نشده است.</div>';
    } catch(e){ $('#log-content').textContent='خطا: '+e.message; const ebox=$('#evidence-index'); if(ebox) ebox.innerHTML='<div class="hint">'+e.message+'</div>'; }
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

    // URL-driven Provider onboarding wizard
    $('#btn-add-provider').addEventListener('click', async () => { showPanel('provider-form'); await loadProviderForm(); });
    $('#btn-close-provider-form').addEventListener('click', () => showPanel('providers'));
    $('#pf-cancel').addEventListener('click', () => showPanel('providers'));

    $('#pf-analyze').addEventListener('click', async () => {
      const url=($('#pf-url').value||'').trim(); const status=$('#provider-form-status');
      if (!url) { setStatus(status,'آدرس وب‌چت را وارد کنید.','err'); return; }
      setStatus(status,'در حال تحلیل URL و انتخاب پیشنهاد مناسب...','working');
      try {
        const a=await api('/provider-wizard/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
        providerWizard.analysis=a; renderWizardProposal(a); $('#pf-observation-card').classList.add('wizard-hidden');
        setStatus(status,'پیشنهاد اولیه آماده است. مرحله بعد مشاهده واقعی صفحه است.','ok');
      } catch(e) { setStatus(status,'تحلیل URL شکست خورد: '+e.message,'err'); }
    });

    async function observeWizardPage() {
      const status=$('#provider-form-status'); const a=providerWizard.analysis;
      if (!a) { setStatus(status,'ابتدا URL را بررسی کنید.','err'); return; }
      const runtimeKey=$('#pf-runtime').value || a.recommended_runtime_key;
      setStatus(status,'صفحه وب‌چت در مرورگر باز می‌شود. اگر Login، شرایط استفاده یا CAPTCHA دیدید همان را کامل کنید؛ سپس به این Wizard برگردید.','working');
      $('#pf-observe').disabled=true; $('#pf-reobserve').disabled=true;
      try {
        const r=await api('/provider-wizard/observe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:a.url,runtime_key:runtimeKey,preferred_target_id:(providerWizard.observation||{}).target_id||null})});
        providerWizard.observation=r.observation; providerWizard.candidate=r.candidate;
        const o=r.observation||{}, c=o.classification||{}, m=o.interaction_summary||{};
        $('#pf-observation').innerHTML=`<div class="kv"><span>وضعیت قابل مشاهده</span><b>${esc(c.state||'unknown')}</b><span>شاهد</span><b>${esc(c.evidence||'-')}</b><span>عنوان صفحه</span><b>${esc(o.title||'-')}</b><span>کنترل‌های قابل مشاهده</span><b>${m.controls??'-'}</b><span>ورودی فایل</span><b>${m.file_inputs??'-'}</b><span>ورودی پیام/متن</span><b>${m.editable_inputs??'-'}</b></div>`;
        const known=!!r.analysis?.reuse_existing_adapter && r.analysis?.register_new_provider!==false;
        const save=$('#pf-save'); save.disabled=!known;
        if (r.analysis?.register_new_provider===false) save.textContent='Provider موجود است';
        else if (known) save.textContent='ثبت Provider پیشنهادی';
        else save.textContent='Candidate ثبت شد';
        const state=c.state||'unknown';
        let nextAction='';
        if (state==='login_required') nextAction='اکنون به صفحه وب‌چتی که HWG باز کرده بروید، وارد حساب شوید یا شرایط استفاده را تأیید کنید. وقتی صفحه آماده چت شد، به این پنل برگردید و روی «انجام شد؛ ادامه بررسی» بزنید.';
        else if (state==='challenge') nextAction='صفحه وب‌چت نیازمند Verification/CAPTCHA است. آن را در همان صفحه بازشده کامل کنید، سپس به این پنل برگردید و «انجام شد؛ ادامه بررسی» را بزنید.';
        else if (state==='region_blocked') nextAction='دسترسی از این محیط به‌صورت منطقه‌ای مسدود است؛ Candidate ثبت می‌شود اما کاوش عملیاتی تا رفع این شرط ادامه پیدا نمی‌کند.';
        else if (r.analysis?.register_new_provider===false) nextAction='این Origin از قبل ثبت شده است. Provider جدید ساخته نمی‌شود؛ برای Session یا هویت دوم به Workspace حساب‌ها و Session بروید.';
        else if (known) nextAction='Adapter موجود با URL تطبیق دارد. HWG می‌تواند Provider را با تنظیمات پیشنهادی ثبت کند؛ سپس Login/Discovery/Readiness ادامه می‌یابد.';
        else if (o.needs_deeper_exploration) nextAction='کاوشگر هنوز نتوانسته وضعیت صفحه را با Evidence کافی تشخیص دهد. فعلاً اقدامی از شما لازم نیست؛ این Candidate باید وارد کاوش عمیق‌تر خودکار شود.'; else nextAction='این URL یک Provider جدید است. Candidate کاوش ذخیره شد؛ HWG آن را به‌عنوان Provider قابل اجرا ثبت نمی‌کند تا Adapter و Evidence لازم ساخته شوند.';
        $('#pf-next-action').innerHTML=nextAction; $('#pf-reobserve').textContent=(state==='login_required'||state==='challenge')?'انجام شد؛ ادامه بررسی':'بررسی مجدد';
        $('#pf-observation-card').classList.remove('wizard-hidden');
        setStatus(status, known?'مشاهده کامل شد؛ پیشنهاد قابل ثبت است.':'مشاهده کامل شد؛ Candidate کاوش ثبت شد.','ok');
      } catch(e) { setStatus(status,'مشاهده صفحه شکست خورد: '+e.message,'err'); }
      finally { $('#pf-observe').disabled=false; $('#pf-reobserve').disabled=false; }
    }
    $('#pf-observe').addEventListener('click', observeWizardPage);
    $('#pf-reobserve').addEventListener('click', observeWizardPage);

    $('#pf-save').addEventListener('click', async () => {
      const a=providerWizard.analysis; const status=$('#provider-form-status');
      if (!a || !a.known_adapter_type || a.register_new_provider===false) { setStatus(status,'برای Provider جدید ابتدا Adapter Candidate باید تکمیل شود.','err'); return; }
      const data={id:a.suggested_provider_id,type:a.known_adapter_type,runtime_key:$('#pf-runtime').value||a.recommended_runtime_key,home_url:a.url,priority:50};
      setStatus(status,'در حال ثبت Provider با پیشنهاد HWG...','working');
      try { const r=await api('/providers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}); if(!r.success) throw new Error(r.error||'ذخیره ناموفق'); toast('Provider ثبت شد؛ ادامه مسیر Login/Discovery/Readiness است.','ok'); showPanel('providers'); await loadProviders(); }
      catch(e){ setStatus(status,'ثبت Provider شکست خورد: '+e.message,'err'); }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    bindStaticActions();
    initNav();
  });
})();