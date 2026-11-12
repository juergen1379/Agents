/* Massivbau Erber · Bearbeitungsmodus:
   Texte direkt ändern, Bilder ersetzen, Listeneinträge hinzufügen, löschen und verschieben */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('adm-config').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var all = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var texts = {};    // Schlüssel -> neuer Text (Stellen außerhalb von Listen)
  var images = {};   // Schlüssel -> { src, alt } (Bilder außerhalb von Listen)
  var groups = {};   // Name der Liste -> true, wenn darin etwas geändert wurde
  var original = {};
  var newKey = 0;
  var MAX_ITEMS = 60;

  var statusEl = $('adm-status'), saveBtn = $('adm-save'), discardBtn = $('adm-discard'), toast = $('adm-toast');
  var plainOnly = (function () {
    var d = document.createElement('div');
    try { d.contentEditable = 'plaintext-only'; } catch (e) { return false; }
    return d.contentEditable === 'plaintext-only';
  })();

  function count() { return Object.keys(texts).length + Object.keys(images).length + Object.keys(groups).length; }
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
  function groupOf(el) { var g = el.closest('[data-repeat]'); return g ? g.getAttribute('data-repeat') : null; }
  function touchGroup(el) { var g = groupOf(el); if (g) groups[g] = true; return g; }

  /* ---------- Texte ---------- */
  function bindText(el) {
    var key = el.getAttribute('data-edit');
    if (!(key in original)) original[key] = clean(el.textContent);
    if (el.closest('[hidden]')) return; // z. B. Mega-Menü: wird über denselben Schlüssel mitgeändert
    el.setAttribute('contenteditable', plainOnly ? 'plaintext-only' : 'true');
    el.setAttribute('spellcheck', 'true');
    el.setAttribute('role', 'textbox');
    el.setAttribute('aria-label', 'Text bearbeiten');

    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); el.blur(); }
    });
    el.addEventListener('paste', function (e) {
      if (plainOnly) return;
      e.preventDefault();
      var t = (e.clipboardData || window.clipboardData).getData('text');
      document.execCommand('insertText', false, clean(t));
    });
    el.addEventListener('input', function () {
      var now = clean(el.textContent);
      if (touchGroup(el)) {
        el.classList.add('adm-changed');
      } else {
        if (now === original[key]) { delete texts[key]; } else { texts[key] = now; }
        all('[data-edit="' + key + '"]').forEach(function (other) {
          if (other !== el) other.textContent = now;
          other.classList.toggle('adm-changed', key in texts);
        });
      }
      refresh();
    });
    el.addEventListener('blur', function () {
      if (clean(el.textContent) !== '') return;
      el.textContent = original[key];
      if (!groupOf(el)) { delete texts[key]; el.classList.remove('adm-changed'); }
      refresh();
      say('Ein Text darf nicht leer sein. Der alte Text steht wieder da.', true);
    });
  }
  all('[data-edit]').forEach(bindText);

  /* ---------- Links im Bearbeitungsmodus nicht verfolgen ---------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (a && !a.hasAttribute('data-adm-link')) e.preventDefault();
  });
  document.addEventListener('submit', function (e) {
    if (!e.target.closest('.adm-bar, .adm-dialog')) e.preventDefault();
  });

  /* ---------- Dialoge ---------- */
  all('[data-adm-open]').forEach(function (b) {
    b.addEventListener('click', function () { $(b.getAttribute('data-adm-open')).showModal(); });
  });
  all('[data-adm-close]').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('dialog').close(); });
  });

  /* ---------- Bilder ---------- */
  var dlg = $('adm-image'), preview = $('adm-image-preview'), fileIn = $('adm-image-file'),
      altIn = $('adm-image-alt'), errEl = $('adm-image-error'), applyBtn = $('adm-image-apply');
  var current = null, pending = null;

  function imgError(msg) { errEl.textContent = msg || ''; errEl.hidden = !msg; }

  function bindImage(img) {
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
  }
  all('img[data-edit-img]').forEach(bindImage);

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
    var inGroup = !!groupOf(current);
    var change = images[key] || {};
    var touched = false;
    if (pending) {
      change.src = pending.src;
      current.setAttribute('data-new-src', pending.src);
      current.removeAttribute('srcset');
      current.src = pending.src;
      touched = true;
    }
    if (alt !== (current.getAttribute('alt') || '')) {
      change.alt = alt;
      current.setAttribute('alt', alt);
      touched = true;
    }
    if (touched) {
      if (inGroup) { touchGroup(current); } else { images[key] = change; }
      current.classList.add('adm-changed');
      refresh();
    }
    dlg.close();
  });

  /* ---------- Listen: Einträge hinzufügen, löschen, verschieben ---------- */
  function itemsOf(list) {
    return Array.prototype.filter.call(list.children, function (c) { return c.hasAttribute('data-item'); });
  }
  function updateTools(list) {
    var items = itemsOf(list);
    items.forEach(function (item, i) {
      var t = item.querySelector(':scope > .adm-tools');
      if (!t) return;
      t.querySelector('[data-act="up"]').disabled = i === 0;
      t.querySelector('[data-act="down"]').disabled = i === items.length - 1;
      t.querySelector('[data-act="remove"]').disabled = items.length <= 1;
      t.querySelector('[data-act="add"]').disabled = items.length >= MAX_ITEMS;
    });
  }
  function addTools(item) {
    var t = document.createElement('div');
    t.className = 'adm-tools';
    t.setAttribute('role', 'group');
    t.setAttribute('aria-label', 'Eintrag verwalten');
    [['up', '↑', 'Eintrag nach vorne schieben'], ['down', '↓', 'Eintrag nach hinten schieben'],
     ['add', '+', 'Neuen Eintrag danach einfügen'], ['remove', '×', 'Eintrag löschen']].forEach(function (d) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('data-act', d[0]);
      b.setAttribute('aria-label', d[2]);
      b.title = d[2];
      b.textContent = d[1];
      t.appendChild(b);
    });
    item.appendChild(t);
  }
  function cloneItem(item) {
    var copy = item.cloneNode(true);
    var t = copy.querySelector(':scope > .adm-tools');
    if (t) t.remove();
    // Neue Stellen bekommen vorläufige Schlüssel; die endgültigen vergibt der Server beim Speichern
    all('[data-edit]', copy).forEach(function (el) {
      el.setAttribute('data-edit', 'neu-' + (++newKey));
      el.classList.remove('adm-changed');
      ['contenteditable', 'role', 'aria-label', 'spellcheck'].forEach(function (a) { el.removeAttribute(a); });
      bindText(el);
    });
    all('img[data-edit-img]', copy).forEach(function (img) {
      img.setAttribute('data-edit-img', 'img-neu-' + (++newKey));
      img.classList.remove('adm-changed');
      bindImage(img);
    });
    copy.classList.add('adm-new');
    addTools(copy);
    return copy;
  }

  all('[data-repeat]').forEach(function (list) {
    itemsOf(list).forEach(function (item, i) {
      if (!item.hasAttribute('data-src')) item.setAttribute('data-src', String(i));
      addTools(item);
    });
    updateTools(list);
    list.addEventListener('click', function (e) {
      var b = e.target.closest('.adm-tools button');
      if (!b || b.disabled) return;
      var item = b.closest('[data-item]');
      if (!item || item.parentNode !== list) return;
      var act = b.getAttribute('data-act');
      var items = itemsOf(list), i = items.indexOf(item);
      if (act === 'up' && i > 0) { list.insertBefore(item, items[i - 1]); }
      if (act === 'down' && i < items.length - 1) { list.insertBefore(items[i + 1], item); }
      if (act === 'add') {
        var copy = cloneItem(item);
        list.insertBefore(copy, item.nextSibling);
        var first = copy.querySelector('[data-edit][contenteditable], img[data-edit-img]');
        if (first) first.focus();
        say('Neuer Eintrag eingefügt. Jetzt Text oder Bild anpassen.');
      }
      if (act === 'remove') {
        if (!window.confirm('Diesen Eintrag löschen?')) return;
        item.remove();
      }
      groups[list.getAttribute('data-repeat')] = true;
      updateTools(list);
      if (act === 'up' || act === 'down') b.focus();
      refresh();
    });
  });

  function groupPayload() {
    var out = {};
    Object.keys(groups).forEach(function (name) {
      var list = document.querySelector('[data-repeat="' + name + '"]');
      if (!list) return;
      out[name] = itemsOf(list).map(function (item) {
        return {
          src: parseInt(item.getAttribute('data-src'), 10),
          texts: all('[data-edit]', item).map(function (el) { return clean(el.textContent); }),
          images: all('img[data-edit-img]', item).map(function (img) {
            var o = { alt: img.getAttribute('alt') || '' };
            if (img.hasAttribute('data-new-src')) o.src = img.getAttribute('data-new-src');
            return o;
          })
        };
      });
    });
    return out;
  }

  /* ---------- Speichern, Verwerfen ---------- */
  saveBtn.addEventListener('click', function () {
    saveBtn.disabled = true;
    statusEl.textContent = 'Wird gespeichert …';
    var structural = Object.keys(groups).length > 0;
    fetch('admin/save.php', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csrf: cfg.csrf, texts: texts, images: images, groups: groupPayload() })
    })
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.error || 'Speichern hat nicht geklappt.');
        Object.keys(texts).forEach(function (k) { original[k] = texts[k]; });
        texts = {}; images = {}; groups = {};
        all('.adm-changed').forEach(function (el) { el.classList.remove('adm-changed'); });
        refresh();
        var skipped = (res.skipped || []).length;
        if (structural && !skipped) {
          // Nach Änderungen an Listen neu laden, damit alle Einträge ihre endgültigen Schlüssel haben
          try { sessionStorage.setItem('adm-saved', '1'); } catch (e) {}
          window.location.reload();
          return;
        }
        say(skipped ? 'Gespeichert. ' + skipped + ' Stelle(n) konnten nicht übernommen werden.' : 'Gespeichert. Die Änderungen sind jetzt auf der Website sichtbar.', !!skipped);
      })
      .catch(function (err) { refresh(); say(err.message || 'Speichern hat nicht geklappt.', true); });
  });

  discardBtn.addEventListener('click', function () {
    if (window.confirm('Alle nicht gespeicherten Änderungen verwerfen?')) {
      texts = {}; images = {}; groups = {};
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
  var justSaved = false;
  try { justSaved = sessionStorage.getItem('adm-saved') === '1'; sessionStorage.removeItem('adm-saved'); } catch (e) {}
  if (justSaved) say('Gespeichert. Die Änderungen sind jetzt auf der Website sichtbar.');
  else if (cfg.notice) say(cfg.notice, /nicht/.test(cfg.notice));
})();
