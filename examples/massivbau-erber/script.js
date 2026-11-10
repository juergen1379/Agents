/* Massivbau Erber · Verhalten: Menü, Mega-Menü, Hero-Slider, Scrollspy, Kontakt-Dock, Formular */
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var desktopNav = window.matchMedia('(min-width: 1080px)');

  var header = $('#site-header');
  var nav = $('#site-nav');
  var navToggle = $('.nav-toggle');
  var megaToggle = $('.mega-toggle');
  var mega = $('#mega-leistungen');
  var megaItem = megaToggle ? megaToggle.closest('.has-mega') : null;
  var main = $('main');
  var footer = $('.site-footer');
  var dock = $('#dock');
  var callbar = $('#callbar');

  var yearEl = $('#year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  /* ---------- Mega-Menü (Disclosure) ---------- */
  var megaTimer = null;

  function setMega(open) {
    if (!mega) return;
    clearTimeout(megaTimer);
    mega.hidden = !open;
    megaToggle.setAttribute('aria-expanded', String(open));
  }
  function megaIsOpen() { return mega && !mega.hidden; }

  if (megaToggle) {
    // Hat die Maus das Menü gerade geöffnet, soll der Klick es nicht wieder schließen
    var hoverOpened = false;
    megaToggle.addEventListener('click', function () {
      if (megaIsOpen() && hoverOpened) { hoverOpened = false; return; }
      setMega(!megaIsOpen());
    });

    // Hover nur mit Maus und nur in der Desktop-Leiste
    megaItem.addEventListener('pointerenter', function (e) {
      if (e.pointerType !== 'mouse' || !desktopNav.matches) return;
      clearTimeout(megaTimer);
      megaTimer = setTimeout(function () { if (!megaIsOpen()) { hoverOpened = true; setMega(true); } }, 90);
    });
    megaItem.addEventListener('pointerleave', function (e) {
      if (e.pointerType !== 'mouse' || !desktopNav.matches) return;
      clearTimeout(megaTimer);
      hoverOpened = false;
      megaTimer = setTimeout(function () { setMega(false); }, 220);
    });

    megaItem.addEventListener('focusout', function (e) {
      if (!desktopNav.matches) return;
      if (e.relatedTarget && !megaItem.contains(e.relatedTarget)) setMega(false);
    });
    document.addEventListener('click', function (e) {
      if (desktopNav.matches && megaIsOpen() && !megaItem.contains(e.target)) setMega(false);
    });
  }

  /* ---------- Mobiles Menü ---------- */
  function navIsOpen() { return nav.classList.contains('is-open'); }

  function sizeNav() {
    var space = window.innerHeight - header.getBoundingClientRect().bottom;
    nav.style.setProperty('--nav-h', Math.max(space, 240) + 'px');
  }
  window.addEventListener('resize', function () { if (navIsOpen()) sizeNav(); });

  function setNav(open, returnFocus) {
    nav.classList.toggle('is-open', open);
    navToggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('nav-open', open);
    [main, footer, dock, callbar].forEach(function (el) { if (el) el.inert = open; });
    if (open) {
      sizeNav();
    } else {
      setMega(false);
      if (returnFocus) navToggle.focus();
    }
  }

  if (navToggle) {
    navToggle.addEventListener('click', function () { setNav(!navIsOpen(), false); });
  }
  desktopNav.addEventListener('change', function () { setNav(false, false); setMega(false); });

  // Jeder Link im Menü schließt Menü und Mega-Menü
  $$('a', nav).forEach(function (a) {
    a.addEventListener('click', function () { setMega(false); if (navIsOpen()) setNav(false, false); });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (megaIsOpen() && desktopNav.matches) { setMega(false); megaToggle.focus(); return; }
    if (navIsOpen()) { setNav(false, true); return; }
    if (dockIsOpen()) { setDock(false); dockBtn.focus(); }
  });

  /* ---------- Scrollspy ---------- */
  var spyLinks = $$('[data-spy]');
  if ('IntersectionObserver' in window && spyLinks.length) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        spyLinks.forEach(function (l) {
          if (l.getAttribute('data-spy') === entry.target.id) l.setAttribute('aria-current', 'true');
          else l.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    spyLinks.forEach(function (l) {
      var s = document.getElementById(l.getAttribute('data-spy'));
      if (s) spy.observe(s);
    });
    // Oberhalb der ersten Sektion ist nichts aktiv
    var heroEl = $('#start');
    if (heroEl) new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) spyLinks.forEach(function (l) { l.removeAttribute('aria-current'); });
    }, { rootMargin: '-40% 0px -55% 0px' }).observe(heroEl);
  }

  /* ---------- Einblenden ---------- */
  var groups = $$('.reveal-group');
  if ('IntersectionObserver' in window) {
    var rev = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('is-in'); rev.unobserve(entry.target); }
      });
    }, { rootMargin: '0px 0px -10% 0px' });
    groups.forEach(function (g) { rev.observe(g); });
  } else {
    groups.forEach(function (g) { g.classList.add('is-in'); });
  }

  /* ---------- Hero-Slider ---------- */
  (function () {
    var hero = $('.hero');
    var slides = $$('.slide', hero);
    if (!hero || slides.length < 2) return;
    var dots = $$('.slider-dot', hero);
    var toggle = $('[data-slider="toggle"]', hero);
    var current = $('[data-slider="current"]', hero);
    var slidesWrap = $('#hero-slides');
    var index = 0;
    var timer = null;
    var playing = !reduceMotion.matches; // Wunsch des Nutzers
    var hovering = false;
    var focusInside = false;
    var onScreen = true;
    var INTERVAL = 7000;

    function show(i, announce) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) { s.classList.toggle('is-active', n === index); });
      dots.forEach(function (d, n) {
        if (n === index) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current');
      });
      if (current) current.textContent = '0' + (index + 1);
      slidesWrap.setAttribute('aria-live', announce ? 'polite' : 'off');
    }
    function schedule() {
      clearTimeout(timer);
      if (!playing || hovering || focusInside || !onScreen || document.hidden) return;
      timer = setTimeout(function () { show(index + 1, false); schedule(); }, INTERVAL);
    }
    function setPlaying(p) {
      playing = p;
      toggle.setAttribute('aria-label', p ? 'Automatischen Wechsel anhalten' : 'Automatischen Wechsel starten');
      $('use', toggle).setAttribute('href', p ? '#i-pause' : '#i-play');
      schedule();
    }
    function manual(i) { setPlaying(false); show(i, true); }

    $('[data-slider="prev"]', hero).addEventListener('click', function () { manual(index - 1); });
    $('[data-slider="next"]', hero).addEventListener('click', function () { manual(index + 1); });
    dots.forEach(function (d, n) { d.addEventListener('click', function () { manual(n); }); });
    toggle.addEventListener('click', function () {
      if (!playing) focusInside = false; // ausdrücklicher Start schlägt die Fokus-Pause
      setPlaying(!playing);
    });

    hero.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') { hovering = true; schedule(); } });
    hero.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') { hovering = false; schedule(); } });
    hero.addEventListener('focusin', function () { focusInside = true; schedule(); });
    hero.addEventListener('focusout', function (e) {
      if (!hero.contains(e.relatedTarget)) { focusInside = false; schedule(); }
    });
    document.addEventListener('visibilitychange', schedule);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) { onScreen = entries[0].isIntersecting; schedule(); }, { threshold: .3 }).observe(hero);
    }

    // Wischen auf Touch-Geräten
    var startX = null, startY = null;
    slidesWrap.addEventListener('touchstart', function (e) {
      startX = e.touches[0].clientX; startY = e.touches[0].clientY;
    }, { passive: true });
    slidesWrap.addEventListener('touchend', function (e) {
      if (startX === null) return;
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      startX = null;
      if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.5) manual(index + (dx < 0 ? 1 : -1));
    }, { passive: true });

    setPlaying(playing);
  })();

  /* ---------- Sticky-Kontakt ---------- */
  var dockBtn = $('#dock-btn');
  var dockPanel = $('#dock-panel');
  function dockIsOpen() { return dockPanel && !dockPanel.hidden; }
  function setDock(open) {
    if (!dockPanel) return;
    dockPanel.hidden = !open;
    dockBtn.setAttribute('aria-expanded', String(open));
  }
  if (dockBtn) {
    dockBtn.addEventListener('click', function () { setDock(!dockIsOpen()); });
    $$('a', dockPanel).forEach(function (a) { a.addEventListener('click', function () { setDock(false); }); });
    document.addEventListener('click', function (e) {
      if (dockIsOpen() && !dock.contains(e.target)) setDock(false);
    });
    dock.addEventListener('focusout', function (e) {
      if (e.relatedTarget && !dock.contains(e.relatedTarget)) setDock(false);
    });
  }

  // Im Kontaktbereich und im Footer ausblenden, damit nichts verdeckt wird
  var contact = $('#kontakt');
  if ('IntersectionObserver' in window && contact) {
    var seen = { kontakt: false, footer: false };
    var typing = false;
    var applySticky = function () {
      var hide = seen.kontakt || seen.footer || typing;
      if (hide) setDock(false);
      [dock, callbar].forEach(function (el) { if (el) el.classList.toggle('is-hidden', hide); });
    };
    var hideObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        seen[entry.target === contact ? 'kontakt' : 'footer'] = entry.isIntersecting;
      });
      applySticky();
    }, { rootMargin: '0px 0px -80px 0px' });
    hideObs.observe(contact);
    if (footer) hideObs.observe(footer);
    document.addEventListener('focusin', function (e) {
      typing = !!(e.target.closest && e.target.closest('.form') && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName));
      applySticky();
    });
  }

  /* ---------- Formular: Prüfung und Übergabe ans E-Mail-Programm ---------- */
  (function () {
    var form = $('#anfrage');
    if (!form) return;
    var summary = $('#form-summary');
    var done = $('#form-done');
    var copyBtn = $('#form-copy');
    var copied = $('#form-copied');
    var lastText = '';
    var MAIL = 'sandro@massivbau-erber.de';
    var submitBtn = $('[type="submit"]', form);
    var submitting = false;
    form.noValidate = true; // eigene Prüfung unten; ohne JS prüft der Browser
    // Fehlermeldungen beim Verlassen eines Felds dürfen den Klick auf den Button nicht verschieben
    submitBtn.addEventListener('pointerdown', function () { submitting = true; });
    document.addEventListener('pointerup', function () { setTimeout(function () { submitting = false; }, 0); });

    var rules = [
      { id: 'f-name', err: 'e-name', test: function (v) { return v.length > 1; }, msg: 'Bitte geben Sie Ihren Namen ein.' },
      { id: 'f-tel', err: 'e-tel', test: function (v) { return /^[\d\s+()\/-]+$/.test(v) && v.replace(/\D/g, '').length >= 6; }, msg: 'Bitte geben Sie eine Telefonnummer ein, unter der wir Sie erreichen.' },
      { id: 'f-mail', err: 'e-mail', test: function (v) { return v === '' || /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v); }, msg: 'Diese E-Mail-Adresse scheint unvollständig zu sein (Beispiel: name@beispiel.de).' },
      { id: 'f-text', err: 'e-text', test: function (v) { return v.length > 4; }, msg: 'Bitte beschreiben Sie kurz Ihr Vorhaben.' }
    ];

    function check(rule) {
      var input = document.getElementById(rule.id);
      var err = document.getElementById(rule.err);
      var ok = rule.test(input.value.trim());
      if (ok) {
        input.removeAttribute('aria-invalid');
        input.removeAttribute('aria-describedby');
        err.hidden = true;
        err.textContent = '';
      } else {
        input.setAttribute('aria-invalid', 'true');
        input.setAttribute('aria-describedby', rule.err);
        err.textContent = rule.msg;
        err.hidden = false;
      }
      return ok;
    }

    rules.forEach(function (rule) {
      var input = document.getElementById(rule.id);
      input.addEventListener('blur', function () {
        if (submitting) return;
        if (input.value.trim() !== '' || input.hasAttribute('aria-invalid')) check(rule);
      });
      input.addEventListener('input', function () {
        if (input.hasAttribute('aria-invalid')) check(rule);
      });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var failed = rules.filter(function (r) { return !check(r); });
      if (failed.length) {
        summary.textContent = failed.length === 1
          ? 'Ein Feld ist noch nicht richtig ausgefüllt.'
          : failed.length + ' Felder sind noch nicht richtig ausgefüllt.';
        summary.hidden = false;
        done.hidden = true;
        document.getElementById(failed[0].id).focus();
        return;
      }
      summary.hidden = true;

      var val = function (id) { return document.getElementById(id).value.trim(); };
      var art = val('f-art');
      var lines = [
        'Name: ' + val('f-name'),
        'Telefon: ' + val('f-tel')
      ];
      if (val('f-mail')) lines.push('E-Mail: ' + val('f-mail'));
      if (val('f-ort')) lines.push('Ort des Bauvorhabens: ' + val('f-ort'));
      if (art) lines.push('Vorhaben: ' + art);
      lines.push('', val('f-text'));
      lastText = lines.join('\n');

      var subject = 'Anfrage' + (art ? ' ' + art : '') + ' – ' + val('f-name');
      window.location.href = 'mailto:' + MAIL +
        '?subject=' + encodeURIComponent(subject) +
        '&body=' + encodeURIComponent(lastText);

      copied.textContent = '';
      done.hidden = false;
      done.focus();
    });

    copyBtn.addEventListener('click', function () {
      var ok = function () { copied.textContent = 'Text kopiert.'; };
      var fail = function () { copied.textContent = 'Kopieren hat nicht geklappt. Bitte rufen Sie an.'; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(lastText).then(ok, fail);
      } else { fail(); }
    });
  })();
})();
