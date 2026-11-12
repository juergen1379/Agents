/* Massivbau Erber · Bearbeitungsmodus: Texte direkt ändern, Bilder ersetzen, speichern */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('adm-config').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var texts = {};   // Schlüssel -> neuer Text
  var images = {};  // Schlüssel -> { src, alt }
  var original = {};
  var statusEl = $('adm-status'), saveBtn = $('adm-save'), discardBtn = $('adm-discard'), toast = $('adm-toast');
  var plainOnly = (function () {
    var d = document.createElement('div');
    try { d.contentEditable = 'plaintext-only'; } catch (e) { return false; }
    return d.contentEditable === 'plaintext-only';
  })();

  function count() { return Object.keys(texts).length + Object.keys(images).length; }
  function refresh() {
    var n = count();
    statusEl.textContent = n === 0 ? 'Keine Änderungen' : (n === 1 ? '1 Änderung nicht gespeichert' : n + ' Änderungen nicht gespeichert');
    saveBtn.disabled = discardBtn.disabled = n === 0;
    document.body.classList.toggle('adm-dirty', n > 0);
  }
  function say(msg, bad) {
    toast.textContent = msg;
    toast.className = 'adm-toast is-on' + (bad ? ' is-bad' : '');
    clearTimeout(say.t);
    say.t = setTimeout(function () { toast.className = 'adm-toast'; }, bad ? 8000 : 4000);
  }
  function clean(s) { return s.replace(/\s+/g, ' ').trim(); }

  /* ---------- Texte ---------- */
  var fields = Array.prototype.slice.call(document.querySelectorAll('[data-edit]'));
  fields.forEach(function (el) {
    var key = el.getAttribute('data-edit');
    if (!(key in original)) original[key] = clean(el.textContent);
    if (el.closest('[hidden]')) return; // z. B. Mega-Menü: wird über denselben Schlüssel mitgeändert
    el.setAttribute('contenteditable', plainOnly ? 'plaintext-only' : 'true');
    el.setAttribute('spellcheck', 'true');
    el.setAttribute('role', 'textbox');
    el.setAttribute('aria-label', 'Text bearbeiten');

    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); el.blur(); }
      if (e.key === 'Escape') { el.textContent = (key in texts) ? texts[key] : original[key]; el.blur(); }
    });
    el.addEventListener('paste', function (e) {
      if (plainOnly) return;
      e.preventDefault();
      var t = (e.clipboardData || window.clipboardData).getData('text');
      document.execCommand('insertText', false, clean(t));
    });
    el.addEventListener('input', function () {
      var now = clean(el.textContent);
      if (now === original[key]) { delete texts[key]; } else { texts[key] = now; }
      fields.forEach(function (other) {
        if (other !== el && other.getAttribute('data-edit') === key) other.textContent = now;
        if (other.getAttribute('data-edit') === key) other.classList.toggle('adm-changed', key in texts);
      });
      refresh();
    });
    el.addEventListener('blur', function () {
      if (clean(el.textContent) === '') {
        el.textContent = original[key];
        delete texts[key];
        el.classList.remove('adm-changed');
        refresh();
        say('Ein Text darf nicht leer sein. Der alte Text steht wieder da.', true);
      }
    });
  });

  /* ---------- Links im Bearbeitungsmodus nicht verfolgen ---------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (a && !a.hasAttribute('data-adm-link')) e.preventDefault();
  });
  document.addEventListener('submit', function (e) {
    if (!e.target.closest('.adm-bar, .adm-dialog')) e.preventDefault();
  });

  /* ---------- Dialoge ---------- */
  document.querySelectorAll('[data-adm-open]').forEach(function (b) {
    b.addEventListener('click', function () { $(b.getAttribute('data-adm-open')).showModal(); });
  });
  document.querySelectorAll('[data-adm-close]').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('dialog').close(); });
  });

  /* ---------- Bilder ---------- */
  var dlg = $('adm-image'), preview = $('adm-image-preview'), fileIn = $('adm-image-file'),
      altIn = $('adm-image-alt'), errEl = $('adm-image-error'), applyBtn = $('adm-image-apply');
  var current = null, pending = null;

  function imgError(msg) { errEl.textContent = msg || ''; errEl.hidden = !msg; }

  document.querySelectorAll('img[data-edit-img]').forEach(function (img) {
    img.setAttribute('tabindex', '0');
    img.setAttribute('role', 'button');
    img.setAttribute('aria-label', 'Bild ersetzen: ' + (img.getAttribute('alt') || 'ohne Beschreibung'));
    var open = function () {
      current = img; pending = null;
      preview.src = img.currentSrc || img.src;
      altIn.value = img.getAttribute('alt') || '';
      fileIn.value = '';
      imgError('');
      dlg.showModal();
    };
    img.addEventListener('click', open);
    img.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  });

  fileIn.addEventListener('change', function () {
    var file = fileIn.files[0];
    if (!file) return;
    imgError('');
    if (file.size > 12 * 1024 * 1024) { imgError('Das Bild ist größer als 12 MB.'); fileIn.value = ''; return; }
    var data = new FormData();
    data.append('csrf', cfg.csrf);
    data.append('image', file);
    applyBtn.disabled = true;
    applyBtn.textContent = 'Bild wird hochgeladen …';
    fetch('admin/upload.php', { method: 'POST', body: data, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.error || 'Der Upload hat nicht geklappt.');
        pending = res;
        preview.src = res.src;
      })
      .catch(function (err) { imgError(err.message || 'Der Upload hat nicht geklappt.'); fileIn.value = ''; })
      .then(function () { applyBtn.disabled = false; applyBtn.textContent = 'Übernehmen'; });
  });

  applyBtn.addEventListener('click', function () {
    if (!current) return;
    var key = current.getAttribute('data-edit-img');
    var alt = clean(altIn.value);
    var change = images[key] || {};
    var touched = false;
    if (pending) {
      change.src = pending.src;
      current.removeAttribute('srcset');
      current.src = pending.src;
      touched = true;
    }
    if (alt !== (current.getAttribute('alt') || '')) {
      change.alt = alt;
      current.setAttribute('alt', alt);
      touched = true;
    }
    if (touched) { images[key] = change; current.classList.add('adm-changed'); refresh(); }
    dlg.close();
  });

  /* ---------- Speichern, Verwerfen ---------- */
  saveBtn.addEventListener('click', function () {
    saveBtn.disabled = true;
    statusEl.textContent = 'Wird gespeichert …';
    fetch('admin/save.php', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csrf: cfg.csrf, texts: texts, images: images })
    })
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.error || 'Speichern hat nicht geklappt.');
        Object.keys(texts).forEach(function (k) { original[k] = texts[k]; });
        texts = {}; images = {};
        document.querySelectorAll('.adm-changed').forEach(function (el) { el.classList.remove('adm-changed'); });
        refresh();
        var skipped = (res.skipped || []).length;
        say(skipped ? 'Gespeichert. ' + skipped + ' Stelle(n) konnten nicht übernommen werden.' : 'Gespeichert. Die Änderungen sind jetzt auf der Website sichtbar.', !!skipped);
      })
      .catch(function (err) { refresh(); say(err.message || 'Speichern hat nicht geklappt.', true); });
  });

  discardBtn.addEventListener('click', function () {
    if (window.confirm('Alle nicht gespeicherten Änderungen verwerfen?')) {
      texts = {}; images = {};
      window.location.reload();
    }
  });

  window.addEventListener('beforeunload', function (e) {
    if (count() > 0) { e.preventDefault(); e.returnValue = ''; }
  });

  /* ---------- Hinweis nach oben setzen, Platz für die Leiste freihalten ---------- */
  var bar = $('adm-bar');
  document.body.insertBefore($('adm-hint'), document.body.firstChild);
  var fit = function () { document.documentElement.style.setProperty('--adm-h', bar.offsetHeight + 'px'); };
  fit();
  window.addEventListener('resize', fit);
  if ('ResizeObserver' in window) new ResizeObserver(fit).observe(bar);

  refresh();
  if (cfg.notice) say(cfg.notice, /nicht/.test(cfg.notice));
})();
