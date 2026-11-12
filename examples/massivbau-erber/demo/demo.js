/* Demo des Kundenzugangs in einer einzigen HTML-Datei, ohne Server.
   Anmeldung, Upload und Speichern werden im Browser nachgestellt:
   Änderungen liegen nur im Speicher dieses Browsers (localStorage). */
(function () {
  'use strict';
  var KEY = 'erber-demo-inhalt', AUTH = 'erber-demo', PASSWORD = 'erber-demo';
  var memory = null;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || { texts: {}, images: {}, groups: {} }; }
    catch (e) { return memory || { texts: {}, images: {}, groups: {} }; }
  }
  function store(data) {
    memory = data;
    try { localStorage.setItem(KEY, JSON.stringify(data)); return true; } catch (e) { return false; }
  }
  function session(name, value) {
    try {
      if (value === undefined) return sessionStorage.getItem(name);
      if (value === null) sessionStorage.removeItem(name); else sessionStorage.setItem(name, value);
    } catch (e) { return null; }
  }
  function go(edit) {
    if (edit) { session(AUTH, '1'); location.hash = '#bearbeiten'; }
    else { history.replaceState(null, '', location.pathname + location.search); }
    location.reload();
  }

  /* Gespeicherte Änderungen anwenden (in Ansicht und Bearbeitung) */
  var saved = load();
  Object.keys(saved.texts).forEach(function (k) {
    document.querySelectorAll('[data-edit="' + k + '"]').forEach(function (el) { el.textContent = saved.texts[k]; });
  });
  Object.keys(saved.images).forEach(function (k) {
    var img = document.querySelector('img[data-edit-img="' + k + '"]'), c = saved.images[k];
    if (!img) return;
    if (c.src) img.src = c.src;
    if (typeof c.alt === 'string') img.alt = c.alt;
  });

  /* Gespeicherte Listen wieder aufbauen: Einträge sind Kopien der Einträge aus der Datei */
  var tempKey = 0;
  Object.keys(saved.groups || {}).forEach(function (name) {
    var list = document.querySelector('[data-repeat="' + name + '"]');
    if (!list) return;
    var base = Array.prototype.filter.call(list.children, function (c) { return c.hasAttribute('data-item'); });
    var used = {};
    var fresh = saved.groups[name].map(function (d) {
      if (!base[d.src]) return null;
      var node = base[d.src].cloneNode(true);
      node.setAttribute('data-src', String(d.src));
      var copy = !!used[d.src]; used[d.src] = true;
      node.querySelectorAll('[data-edit]').forEach(function (el, i) {
        if (copy) el.setAttribute('data-edit', 'neu-d' + (++tempKey));
        if (typeof d.texts[i] === 'string') el.textContent = d.texts[i];
      });
      node.querySelectorAll('img[data-edit-img]').forEach(function (img, i) {
        if (copy) img.setAttribute('data-edit-img', 'img-neu-d' + (++tempKey));
        var c = (d.images || [])[i] || {};
        if (c.src) { img.src = c.src; img.setAttribute('data-new-src', c.src); }
        if (typeof c.alt === 'string') img.alt = c.alt;
      });
      return node;
    }).filter(Boolean);
    if (!fresh.length) return;
    base.forEach(function (n) { n.remove(); });
    fresh.forEach(function (n) { list.appendChild(n); });
  });

  /* ---------- Ansicht: Einstieg und Anmeldung ---------- */
  if (!window.DEMO_EDIT) {
    var login = document.getElementById('demo-login');
    var open = function () { login.showModal(); document.getElementById('demo-pw').focus(); };
    document.querySelectorAll('[data-demo-login]').forEach(function (b) { b.addEventListener('click', open); });
    document.getElementById('demo-login-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var err = document.getElementById('demo-login-error');
      if (document.getElementById('demo-pw').value === PASSWORD) { go(true); }
      else { err.textContent = 'Das Passwort stimmt nicht.'; err.hidden = false; }
    });
    document.getElementById('demo-login-cancel').addEventListener('click', function () { login.close(); });
    if (location.hash === '#bearbeiten') open();
    return;
  }

  /* ---------- Bearbeitung: Oberfläche einsetzen, Server nachstellen ---------- */
  document.body.appendChild(document.getElementById('adm-ui').content.cloneNode(true));
  document.querySelectorAll('[data-demo-login]').forEach(function (b) { b.remove(); });

  function shrink(file) {
    return new Promise(function (resolve, reject) {
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) { reject(new Error('Bitte ein JPG, PNG oder WebP wählen.')); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        var scale = Math.min(1, 1200 / img.naturalWidth);
        var c = document.createElement('canvas');
        c.width = Math.round(img.naturalWidth * scale); c.height = Math.round(img.naturalHeight * scale);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        resolve({ ok: true, src: c.toDataURL('image/jpeg', 0.8), width: c.width, height: c.height });
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('Das Bild konnte nicht gelesen werden.')); };
      img.src = url;
    });
  }
  function answer(obj) { return { ok: true, status: 200, json: function () { return Promise.resolve(obj); } }; }

  window.fetch = function (url, opts) {
    if (/upload\.php$/.test(url)) {
      return shrink(opts.body.get('image')).then(answer, function (e) { return answer({ ok: false, error: e.message }); });
    }
    if (/save\.php$/.test(url)) {
      var body = JSON.parse(opts.body), data = load();
      Object.keys(body.texts || {}).forEach(function (k) { data.texts[k] = body.texts[k]; });
      Object.keys(body.images || {}).forEach(function (k) {
        data.images[k] = Object.assign(data.images[k] || {}, body.images[k]);
      });
      data.groups = data.groups || {};
      Object.keys(body.groups || {}).forEach(function (g) { data.groups[g] = body.groups[g]; });
      return Promise.resolve(answer(store(data)
        ? { ok: true, saved: 1, skipped: [] }
        : { ok: false, error: 'Der Demo-Speicher des Browsers ist voll. Bitte „Sicherungen“ öffnen und die Demo zurücksetzen.' }));
    }
    return Promise.reject(new Error('In der Demo nicht verfügbar.'));
  };

  /* Formulare und Links der Leiste: in der Demo ohne Server */
  document.addEventListener('submit', function (e) {
    var action = (e.target.querySelector('[name="action"]') || {}).value;
    if (!action) return;
    e.preventDefault();
    if (action === 'logout') { session(AUTH, null); go(false); }
    if (action === 'restore') { try { localStorage.removeItem(KEY); } catch (x) {} memory = null; window.onbeforeunload = null; location.reload(); }
    if (action === 'password') {
      e.target.closest('dialog').close();
      var t = document.getElementById('adm-toast');
      t.textContent = 'In der Demo lässt sich das Passwort nicht ändern.'; t.className = 'adm-toast is-on';
      setTimeout(function () { t.className = 'adm-toast'; }, 4000);
    }
  }, true);
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-adm-link]');
    if (a) { e.preventDefault(); go(false); }
  }, true);

  window.__erberEditor();
})();
