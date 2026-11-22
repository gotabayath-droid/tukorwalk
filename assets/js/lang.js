/* Tuk Or Walk — language switcher (21 languages)
   English is the default and is what search engines index (the HTML is always English).
   Choosing another language translates the page in the browser with Google Website Translator.
   The choice is kept in sessionStorage + a session cookie, so it follows the visitor to every page
   until the browser/tab session ends. Nothing is loaded for English. */
(function () {
  'use strict';
  var LANGS = [
    ['en','English','EN'],['zh-CN','中文','ZH'],['hi','हिन्दी','HI'],['es','Español','ES'],['fr','Français','FR'],
    ['ar','العربية','AR'],['pt','Português','PT'],['ru','Русский','RU'],['de','Deutsch','DE'],['ja','日本語','JA'],
    ['tr','Türkçe','TR'],['ko','한국어','KO'],['ta','தமிழ்','TA'],['it','Italiano','IT'],['pl','Polski','PL'],
    ['nl','Nederlands','NL'],['si','සිංහල','SI'],['sv','Svenska','SV'],['cs','Čeština','CS'],['da','Dansk','DA'],['et','Eesti','ET']
  ];
  var KEY = 'tw_lang';
  var codes = LANGS.map(function (l) { return l[0]; });

  function store(get, v) {
    try { if (get) return sessionStorage.getItem(KEY); sessionStorage.setItem(KEY, v); } catch (e) {}
    return null;
  }
  function readCookie() {
    var m = document.cookie.match(/(?:^|;\s*)googtrans=\/en\/([^;]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  function setCookie(code) {
    var host = location.hostname, v;
    var bases = ['', '; domain=' + host];
    var parts = host.split('.');
    if (parts.length > 2) bases.push('; domain=.' + parts.slice(-2).join('.'));
    else if (parts.length === 2) bases.push('; domain=.' + host);
    bases.forEach(function (d) {
      if (code === 'en') v = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/' + d;
      else v = 'googtrans=/en/' + code + '; path=/' + d;           // no expiry = session cookie
      document.cookie = v;
    });
  }
  function current() {
    var s = store(true);
    if (s && codes.indexOf(s) > -1) return s;
    var c = readCookie();
    if (c && codes.indexOf(c) > -1) return c;
    return 'en';
  }

  function loadTranslate(code) {
    setCookie(code);
    var holder = document.getElementById('google_translate_element');
    if (!holder) {
      holder = document.createElement('div');
      holder.id = 'google_translate_element';
      holder.className = 'notranslate';
      holder.setAttribute('aria-hidden', 'true');
      document.body.appendChild(holder);
    }
    window.twTranslateInit = function () {
      try {
        new google.translate.TranslateElement({
          pageLanguage: 'en',
          includedLanguages: codes.filter(function (c) { return c !== 'en'; }).join(','),
          autoDisplay: false
        }, 'google_translate_element');
      } catch (e) {}
    };
    var s = document.createElement('script');
    s.src = 'https://translate.google.com/translate_a/element.js?cb=twTranslateInit';
    s.async = true;
    document.head.appendChild(s);
  }

  function choose(code) {
    if (code === current() && code === (readCookie() || 'en')) return;
    store(false, code);
    setCookie(code);
    location.reload();             // reload applies (or removes) the translation cleanly
  }

  function bindUI(active) {
    var label = '';
    LANGS.forEach(function (l) { if (l[0] === active) label = l[2]; });

    // top button + dropdown (clone the button to drop any older inline listener, then own the toggle)
    var btn = document.getElementById('langBtn'), dd = document.getElementById('langDropdown');
    if (btn && dd) {
      var nb = btn.cloneNode(true);
      btn.parentNode.replaceChild(nb, btn);
      btn = nb;
      var sp = btn.querySelector('span'); if (sp) sp.textContent = label;
      btn.setAttribute('aria-haspopup', 'true');
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-controls', 'langDropdown');
      btn.addEventListener('click', function (e) {
        e.stopImmediatePropagation();
        e.stopPropagation();
        var open = dd.classList.toggle('open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      document.addEventListener('click', function (e) {
        if (!dd.contains(e.target) && !btn.contains(e.target)) { dd.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { dd.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
      });
    }

    [].forEach.call(document.querySelectorAll('.lang-dropdown, .bottom-languages'), function (box) {
      box.classList.add('notranslate');
      box.setAttribute('translate', 'no');
      [].forEach.call(box.querySelectorAll('a'), function (a, i) {
        var l = LANGS[i]; if (!l) return;
        a.setAttribute('lang', l[0]);
        a.setAttribute('hreflang', l[0]);
        a.setAttribute('href', '#lang-' + l[0]);
        a.setAttribute('data-lang', l[0]);
        a.setAttribute('role', 'button');
        var on = l[0] === active;
        a.classList.toggle('active', on);
        if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
        a.addEventListener('click', function (ev) { ev.preventDefault(); choose(l[0]); });
      });
    });
  }

  function init() {
    var active = current();
    // keep storage + cookie in step on every page of the session
    store(false, active);
    if (active !== 'en') {
      loadTranslate(active);
      document.documentElement.setAttribute('data-translated', active);
    } else if (readCookie()) { setCookie('en'); }
    bindUI(active);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
