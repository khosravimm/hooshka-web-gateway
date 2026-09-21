(function (global) {
  'use strict';

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function inline(s) {
    s = String(s);
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+(?:\s+"[^"]*")?)\)/g, function (_, alt, href) {
      var parts = href.split(/\s+"/);
      var src = parts[0];
      return '<img data-src-guard="1" src="' + escapeHtml(src) + '" alt="' + escapeHtml(alt) + '" loading="lazy">';
    });
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, txt, href) {
      return '<a href="' + escapeHtml(href) + '" target="_blank" rel="noopener noreferrer">' + inline(escapeHtml(txt)) + '</a>';
    });
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    s = s.replace(/_([^_]+)_/g, '<em>$1</em>');
    s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    return s;
  }

  function renderTable(lines, i) {
    var header = lines[i].split('|').map(function (x) { return x.trim(); }).filter(function (x, idx, arr) { return !(x === '' && (idx === 0 || idx === arr.length - 1)); });
    var html = '<table><thead><tr>';
    header.forEach(function (c) { html += '<th>' + inline(escapeHtml(c)) + '</th>'; });
    html += '</tr></thead><tbody>';
    i += 1;
    if (lines[i] && lines[i].includes('---')) { i += 1; }
    while (i < lines.length && lines[i].trim() !== '' && lines[i].includes('|')) {
      var cells = lines[i].split('|').map(function (x) { return x.trim(); }).filter(function (x, idx, arr) { return !(x === '' && (idx === 0 || idx === arr.length - 1)); });
      html += '<tr>';
      cells.forEach(function (c) { html += '<td>' + inline(escapeHtml(c)) + '</td>'; });
      html += '</tr>';
      i += 1;
    }
    html += '</tbody></table>';
    return { html: html, next: i };
  }

  function renderList(lines, i, ordered) {
    var tag = ordered ? 'ol' : 'ul';
    var html = '<' + tag + '>';
    while (i < lines.length && lines[i].trim() !== '') {
      var line = lines[i].trim();
      var m = ordered ? line.match(/^\d+[.)]\s+(.*)$/) : line.match(/^[-*+]\s+(.*)$/);
      if (!m) { break; }
      html += '<li>' + inline(escapeHtml(m[1])) + '</li>';
      i += 1;
    }
    html += '</' + tag + '>';
    return { html: html, next: i };
  }

  function render(src) {
    var text = String(src == null ? '' : src).replace(/\r\n/g, '\n').split('\n');
    var out = [];
    var inFence = null;
    var fenceBuf = [];
    var fenceLang = '';

    var i = 0;
    while (i < text.length) {
      var line = text[i];

      if (inFence) {
        if (line.trim().startsWith('```')) {
          out.push('<pre><code>' + escapeHtml(fenceBuf.join('\n')) + '</code></pre>');
          fenceBuf = [];
          inFence = null;
        } else {
          fenceBuf.push(line);
        }
        i += 1;
        continue;
      }

      var fence = line.match(/^\s*```(\w*)\s*$/);
      if (fence) {
        inFence = true;
        fenceLang = fence[1] || '';
        i += 1;
        continue;
      }

      var t = line.trim();

      if (t === '') { i += 1; continue; }

      if (t === '---' && i === 0) { out.push('<hr>'); i += 1; continue; }

      var h = t.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        var level = Math.min(6, h[1].length);
        out.push('<h' + level + '>' + inline(escapeHtml(h[2])) + '</h' + level + '>');
        i += 1; continue;
      }

      if (t.startsWith('> ')) {
        var quote = [];
        while (i < text.length && text[i].trim().startsWith('>')) {
          quote.push(text[i].trim().replace(/^>\s?/, ''));
          i += 1;
        }
        out.push('<blockquote><p>' + inline(escapeHtml(quote.join(' '))) + '</p></blockquote>');
        continue;
      }

      if (/^\s*\|.+\|/.test(t) && i + 1 < text.length && text[i + 1].includes('---')) {
        var tbl = renderTable(text, i);
        out.push(tbl.html);
        i = tbl.next;
        continue;
      }

      if (/^[-*+]\s+/.test(t)) {
        var ul = renderList(text, i, false);
        out.push(ul.html);
        i = ul.next;
        continue;
      }

      if (/^\d+[.)]\s/.test(t)) {
        var ol = renderList(text, i, true);
        out.push(ol.html);
        i = ol.next;
        continue;
      }

      out.push('<p>' + inline(escapeHtml(t)) + '</p>');
      i += 1;
    }

    if (inFence) {
      out.push('<pre><code>' + escapeHtml(fenceBuf.join('\n')) + '</code></pre>');
    }

    return out.join('\n');
  }

  function hasPersian(s) {
    return /[\u0600-\u06FF]/.test(String(s || ''));
  }

  global.Markdown = { render: render, hasPersian: hasPersian };
})(window || globalThis);