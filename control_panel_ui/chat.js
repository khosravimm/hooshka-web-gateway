(function () {
  'use strict';

  const $ = function (sel) { return document.querySelector(sel); };
  const $$ = function (sel) { return Array.from(document.querySelectorAll(sel)); };

  let providerData = [];
  let currentConversationId = null;
  const history = [];
  let activeController = null;
  let sendInFlight = false;

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function toast(msg, kind) {
    const region = $('#toast-region');
    if (!region) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (kind || '');
    t.textContent = msg;
    region.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  async function api(path, options) {
    const resp = await fetch('/panel/api' + path, options);
    let data = {};
    try { data = await resp.json(); } catch (e) { /* ignore */ }
    if (!resp.ok) {
      throw new Error((data && (data.error || data.message)) || ('HTTP ' + resp.status));
    }
    return data;
  }

  function providerById(id) {
    return providerData.find(function (p) { return p.id === id; });
  }

  function modelOptionsFor(id) {
    const p = providerById(id);
    if (!p) return [];
    const opts = (p.model && Array.isArray(p.model.options)) ? p.model.options : [];
    const def = p.model && p.model.default;
    if (def && opts.indexOf(def) === -1) opts.unshift(def);
    if (!opts.length) opts.push(p.id);
    return opts;
  }

  async function populateProviders() {
    const sel = $('#chat-provider');
    const msel = $('#chat-model');
    try {
      const data = await api('/providers');
      providerData = data.providers || [];
      const enabled = providerData.filter(function (p) { return p.enabled === true; });
      const list = enabled.length ? enabled : providerData;
      sel.innerHTML = list.map(function (p) { return '<option value="' + esc(p.id) + '">' + esc(p.id) + '</option>'; }).join('');
      let target = null;
      let wantDefault = data.default_model || data.default;
      for (let i = 0; i < list.length; i++) {
        if (list[i].id === wantDefault || list[i].default === true) { target = list[i]; break; }
      }
      if (!target) target = list[0];
      if (target) sel.value = target.id;
      renderIndicators();
      refreshModelList();
      setStatus('آماده. انتخاب مدل: ' + (msel.options.length ? msel.options[msel.selectedIndex].text : '-'), 'ok');
    } catch (e) {
      setStatus('بارگیری پراوایدر ناموفق: ' + e.message, 'err');
    }
  }

  function refreshModelList() {
    const id = $('#chat-provider').value;
    const msel = $('#chat-model');
    const opts = modelOptionsFor(id);
    msel.innerHTML = opts.map(function (m) { return '<option value="' + esc(m) + '">' + esc(m) + '</option>'; }).join('');
  }

  function renderIndicators() {
    const box = $('#chat-cap-indicators');
    if (!box) return;
    box.innerHTML = providerData.filter(function (p) { return p.enabled !== false; }).map(function (p) {
      const c = (p.features && p.features.controls) || {};
      const thinking = c.thinking ? 'تفکر: بله' : 'تفکر: خیر';
      const search = c.search ? 'جستجو: بله' : 'جستجو: خیر';
      return '<span class="cap-chip" title="' + esc(p.id) + '">' + esc(p.id) + ' · ' + thinking + ' · ' + search + '</span>';
    }).join('');
  }

  function setStatus(msg, kind) {
    const el = $('#chat-status');
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'status-line' + (kind ? ' ' + kind : '');
  }

  function newId() {
    return 'conv-ui-' + Math.random().toString(36).slice(2, 10);
  }

  function appendUser(text) {
    const t = $('#chat-transcript');
    const msg = document.createElement('div');
    msg.className = 'msg msg-user';
    const body = document.createElement('div');
    body.className = 'msg-body';
    body.textContent = text;
    msg.appendChild(body);
    t.appendChild(msg);
    t.scrollTop = t.scrollHeight;
    return msg;
  }

  function appendAssistant() {
    const t = $('#chat-transcript');
    const msg = document.createElement('div');
    msg.className = 'msg msg-assistant';
    const body = document.createElement('div');
    body.className = 'msg-body msg-md';
    body.textContent = '';
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    msg.appendChild(body);
    msg.appendChild(meta);
    t.appendChild(msg);
    t.scrollTop = t.scrollHeight;
    return { msg: msg, body: body, meta: meta };
  }

  function appendSystem(text, kind) {
    const t = $('#chat-transcript');
    const msg = document.createElement('div');
    msg.className = 'msg msg-error';
    const body = document.createElement('div');
    body.className = 'msg-body';
    body.textContent = text;
    msg.appendChild(body);
    t.appendChild(msg);
    t.scrollTop = t.scrollHeight;
    return msg;
  }

  function parseSse(lines, onData, onDone, onError) {
    let done = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.length) continue;
      if (line.charAt(0) === ':') continue;
      if (line.indexOf('data:') !== 0) continue;
      const raw = line.slice(5).trim();
      if (!raw.length) continue;
      if (raw === '[DONE]') { done = true; break; }
      let payload;
      try { payload = JSON.parse(raw); } catch (e) { continue; }
      if (payload && payload.error) { onError(payload.error); done = true; break; }
      onData(payload);
    }
    return done;
  }

  async function sendMessage() {
    const input = $('#chat-input');
    const text = (input.value || '').trim();
    if (!text || sendInFlight) return;
    const model = $('#chat-model').value;
    if (!model) { toast('ابتدا مدل انتخاب کنید', 'warn'); return; }

    if (!currentConversationId) currentConversationId = newId();

    const userMsg = appendUser(text);
    history.push({ role: 'user', content: text });
    input.value = '';
    input.style.height = 'auto';

    const a = appendAssistant();
    const body = a.body;
    const meta = a.meta;
    let acc = '';
    let renderScheduled = false;

    function renderNow() {
      renderScheduled = false;
      if (!acc.trim()) { body.textContent = ''; return; }
      const html = window.Markdown ? window.Markdown.render(acc) : ('<pre>' + esc(acc) + '</pre>');
      body.innerHTML = '<div class="md-root">' + html + '</div>';
      const t = $('#chat-transcript');
      if (t) t.scrollTop = t.scrollHeight;
    }

    function scheduleRender() {
      if (renderScheduled) return;
      renderScheduled = true;
      requestAnimationFrame(renderNow);
    }

    $('#chat-send').disabled = true;
    $('#chat-stop').disabled = false;
    setStatus('در حال استریم از ' + ($('#chat-provider').value || '') + '/' + model + ' ...', 'working');
    sendInFlight = true;

    const thinking = $('#chat-thinking').checked === true;
    const search = $('#chat-search').checked === true;

    const controller = new AbortController();
    activeController = controller;

    try {
      const resp = await fetch('/v1/chat/conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model,
          messages: history,
          stream: true,
          thinking: thinking,
          search: search,
          conversation_id: currentConversationId,
        }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        let errData = {};
        try { errData = await resp.json(); } catch (e) { /* ignore */ }
        throw new Error((errData.error && (errData.error.message || JSON.stringify(errData.error))) || ('HTTP ' + resp.status));
      }
      if (!resp.body) throw new Error('بدون جریان پاسخ');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buf = '';
      let finished = false;
      let errored = false;
      let showedMeta = false;

      for (;;) {
        const r = await reader.read();
        if (r.done) break;
        buf += decoder.decode(r.value, { stream: true });
        let idx = buf.indexOf('\n');
        while (idx !== -1) {
          const line = buf.slice(0, idx);
          buf = buf.slice(idx + 1);
          const wasDone = parseSse([line],
            function (payload) {
              const choices = payload.choices || [];
              const delta = choices[0] && choices[0].delta ? choices[0].delta : {};
              if (delta.content) { acc += delta.content; scheduleRender(); }
              if (!showedMeta && payload.provider_meta) {
                const pm = payload.provider_meta;
                const parts = [];
                if (pm.provider_id) parts.push('پراوایدر: ' + pm.provider_id);
                if (pm.conversation_id) parts.push('conv: ' + pm.conversation_id);
                if (pm.thinking) parts.push('تفکر: فعال');
                parts.push('مدل: ' + payload.model);
                meta.textContent = parts.join(' · ');
                showedMeta = true;
              }
            },
            function () { finished = true; },
            function (err) { errored = true; body.textContent = esc(err.message || 'خطای runtime'); }
          );
          if (wasDone || finished || errored) break;
          idx = buf.indexOf('\n');
        }
        if (finished || errored) break;
      }
      if (buf.trim().length) {
        parseSse(buf.split('\n'),
          function (payload) {
            const choices = payload.choices || [];
            const delta = choices[0] && choices[0].delta ? choices[0].delta : {};
            if (delta.content) { acc += delta.content; renderNow(); }
          },
          function () { finished = true; },
          function (err) { errored = true; body.textContent = esc(err.message || 'خطای runtime'); }
        );
      }

      renderNow();
      if (errored) {
        history.pop();
        setStatus('پاسخ ناموفق بود.', 'err');
        toast('پاسخ ناموفق بود', 'err');
      } else if (acc.trim() || !finished) {
        history.push({ role: 'assistant', content: acc });
        setStatus('استریم کامل شد.', 'ok');
      } else {
        history.push({ role: 'assistant', content: acc || '' });
        setStatus('ناتمام (بدون محتوا).', 'warn');
      }
      if (!acc.trim() && !errored && finished) body.textContent = '(پاسخ خالی)';
    } catch (e) {
      if (e.name === 'AbortError') {
        body.textContent = acc || '';
        history.push({ role: 'assistant', content: acc });
        setStatus('توسط کاربر متوقف شد.', 'warn');
        toast('استریم متوقف شد', 'warn');
      } else {
        history.pop();
        appendSystem('خطا: ' + e.message, 'err');
        setStatus('خطا: ' + e.message, 'err');
      }
    } finally {
      activeController = null;
      sendInFlight = false;
      $('#chat-send').disabled = false;
      $('#chat-stop').disabled = true;
    }
  }

  function stopStream() {
    if (activeController) {
      activeController.abort();
    }
  }

  function newConversation() {
    history.length = 0;
    currentConversationId = null;
    const t = $('#chat-transcript');
    t.innerHTML = '';
    setStatus('گفتگوی جدید.', '');
  }

  function applyToolbarButton(btn) {
    const input = $('#chat-input');
    const insRaw = btn.dataset.ins;
    const selRaw = btn.dataset.sel;
    if (!insRaw) return;
    const selArr = String(selRaw || '0,0').split(',').map(Number);
    const sels = selArr[0] || 0;
    const selLen = selArr[1] || 0;
    input.focus();
    const start = input.selectionStart != null ? input.selectionStart : input.value.length;
    const end = input.selectionEnd != null ? input.selectionEnd : start;
    const selected = input.value.slice(start, end);
    const ins = insRaw.indexOf('$1') !== -1 ? insRaw.replace('$1', selected) : insRaw;
    const value = input.value;
    const newValue = value.slice(0, start) + ins + value.slice(end);
    input.value = newValue;
    let cursor = start + ins.length;
    if (sels) cursor = start + sels;
    input.focus();
    input.setSelectionRange(cursor, cursor + selLen);
    input.style.height = 'auto';
    input.style.height = Math.min(240, Math.max(60, input.scrollHeight)) + 'px';
  }

  function autoResize() {
    const input = $('#chat-input');
    input.style.height = 'auto';
    input.style.height = Math.min(240, Math.max(60, input.scrollHeight)) + 'px';
  }

  function init() {
    const input = $('#chat-input');
    $('#chat-provider').addEventListener('change', function () {
      refreshModelList();
      renderIndicators();
    });
    $('#chat-send').addEventListener('click', sendMessage);
    $('#chat-stop').addEventListener('click', stopStream);
    $('#chat-new').addEventListener('click', newConversation);
    $('#chat-attach').addEventListener('click', function () {
      toast('آپلود فایل هنوز در دسترس نیست (بدون endpoint آپلود در Runtime API)', 'warn');
    });
    const hint = $('#chat-attach-hint');
    if (hint) hint.textContent = 'غیرفعال — بدون endpoint آپلود';
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        if (!sendInFlight) sendMessage();
      }
    });
    input.addEventListener('input', autoResize);
    $$('.composer-toolbar button[data-ins]').forEach(function (b) {
      b.addEventListener('click', function () { applyToolbarButton(b); });
    });
    if (providerData.length === 0) populateProviders();
  }

  window.HwgChat = {
    init: init,
  };
})();