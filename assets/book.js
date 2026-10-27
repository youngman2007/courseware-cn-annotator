(function () {
  'use strict';

  var CFG = window.BOOK_CFG || {};
  var T = {
    notesOn: '隐藏注释', notesOff: '显示注释',
    imgsOn: '隐藏原图', imgsOff: '显示原图',
    themeDark: '深色', themeLight: '浅色',
    slideBtn: '原课件图', slideBtnOpen: '收起原图',
    reading: '正在阅读：{label} · {title}', noMatch: '没有匹配的页面'
  };
  Object.keys(CFG.i18n || {}).forEach(function (k) { T[k] = CFG.i18n[k]; });
  var PREFIX = CFG.storageKey || 'book';
  var DEFAULT_THEME = CFG.defaultTheme || 'light';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) {
    return Array.prototype.slice.call((r || document).querySelectorAll(s));
  };
  var body = document.body;
  var pages = $$('.page');
  var tocItems = $$('.toc-item');

  /* ---------- 分组展开 / 收起 ---------- */
  function setGroup(g, open) {
    var b = $('.group-b', g), ar = $('.arrow', g);
    if (b) b.style.display = open ? 'block' : 'none';
    if (ar) ar.textContent = open ? '▾' : '▸';
  }
  function restoreGroups() {
    $$('.group').forEach(function (g) {
      if (g.dataset.open !== undefined) setGroup(g, g.dataset.open === '1');
      else setGroup(g, true);
      g.classList.remove('hidden');
    });
  }
  $$('.group-h').forEach(function (h) {
    h.addEventListener('click', function () {
      var g = h.closest('.group'), b = h.nextElementSibling;
      if (!b) return;
      setGroup(g, b.style.display === 'none');
    });
  });

  /* ---------- 记忆设置（主题 / 注释 / 原图） ---------- */
  var LS = {
    get: function (k, d) {
      try { var v = localStorage.getItem(PREFIX + '.' + k); return v === null ? d : v; }
      catch (e) { return d; }
    },
    set: function (k, v) {
      try { localStorage.setItem(PREFIX + '.' + k, v); } catch (e) {}
    }
  };

  var btnNotes = $('#btnNotes'), btnImgs = $('#btnImgs'),
      btnTheme = $('#btnTheme'), btnPrint = $('#btnPrint');
  var noteCards = $$('.card.notes'), figs = $$('.slidefig');

  function setNotes(on) {
    body.classList.toggle('no-notes', !on);
    noteCards.forEach(function (c) { c.style.display = on ? '' : 'none'; });
    if (btnNotes) {
      btnNotes.classList.toggle('on', on);
      btnNotes.textContent = on ? T.notesOn : T.notesOff;
    }
    LS.set('notes', on ? '1' : '0');
  }
  function setImgs(on) {
    figs.forEach(function (f) { f.classList.toggle('hidden', !on); });
    if (btnImgs) {
      btnImgs.classList.toggle('on', on);
      btnImgs.textContent = on ? T.imgsOn : T.imgsOff;
    }
    LS.set('imgs', on ? '1' : '0');
  }
  function setTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    if (btnTheme) {
      btnTheme.classList.toggle('on', dark);
      btnTheme.textContent = dark ? T.themeLight : T.themeDark;
    }
    LS.set('theme', dark ? 'dark' : 'light');
  }

  if (btnNotes) btnNotes.addEventListener('click', function () {
    setNotes(body.classList.contains('no-notes'));
  });
  if (btnImgs) {
    if (!figs.length) { btnImgs.hidden = true; }
    else btnImgs.addEventListener('click', function () {
      // 只要还有没显示的图，就整体打开；全部显示了才收起
      setImgs(figs.some(function (f) { return f.classList.contains('hidden'); }));
    });
  }
  if (btnTheme) btnTheme.addEventListener('click', function () {
    setTheme(document.documentElement.getAttribute('data-theme') !== 'dark');
  });
  if (btnPrint) btnPrint.addEventListener('click', function () { window.print(); });

  // 网址参数可临时覆盖设置，如 index.html?imgs=1&theme=dark&notes=0
  var QP = new URLSearchParams(location.search);
  var pick = function (key, lsKey, dflt) {
    return QP.has(key) ? QP.get(key) !== '0' : LS.get(lsKey, dflt) === '1';
  };
  if (btnNotes) setNotes(pick('notes', 'notes', '1'));
  if (figs.length) setImgs(pick('imgs', 'imgs', '0'));
  setTheme(QP.has('theme') ? QP.get('theme') === 'dark' : LS.get('theme', DEFAULT_THEME) === 'dark');
  restoreGroups();

  /* ---------- 每页的“原课件图”按钮 ---------- */
  pages.forEach(function (sec) {
    var b = $('.slidetoggle', sec), f = $('.slidefig', sec);
    if (!b || !f) return;
    b.addEventListener('click', function () {
      var hidden = f.classList.toggle('hidden');
      b.textContent = hidden ? T.slideBtn : T.slideBtnOpen;
      b.classList.toggle('on', !hidden);
    });
  });

  /* ---------- 图片灯箱 ---------- */
  var lb = $('#lightbox'), lbImg = $('#lightboxImg');
  if (lb && lbImg) {
    document.addEventListener('click', function (e) {
      var img = e.target.closest ? e.target.closest('.slidefig img') : null;
      if (img) { lbImg.src = img.src; lb.classList.remove('hidden'); return; }
      if (e.target.closest && e.target.closest('#lightbox')) lb.classList.add('hidden');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { lb.classList.add('hidden'); body.classList.remove('nav'); }
    });
  }

  /* ---------- 搜索：按标题 + 正文全文过滤 ---------- */
  var q = $('#q');
  // 索引时去掉所有空白，这样“5 变量卡诺图”与“5变量卡诺图”都能搜到
  pages.forEach(function (p) {
    p.dataset.text = (p.textContent || '').toLowerCase().replace(/\s+/g, '');
  });

  function search(kw) {
    var k = kw.trim().toLowerCase();
    if (!k) {
      pages.forEach(function (p) { p.classList.remove('hidden'); });
      tocItems.forEach(function (a) { a.classList.remove('hide'); });
      restoreGroups();
      return;
    }
    // 空格分隔的多个关键词为“与”关系：全部命中才算命中
    var terms = k.split(/\s+/).filter(Boolean);
    pages.forEach(function (p) {
      var txt = p.dataset.text || '';
      var hit = terms.every(function (t) { return txt.indexOf(t) >= 0; });
      p.classList.toggle('hidden', !hit);
    });
    tocItems.forEach(function (a) {
      var n = a.dataset.num, sec = document.getElementById('p' + n);
      a.classList.toggle('hide', !(sec && !sec.classList.contains('hidden')));
    });
    $$('.group').forEach(function (g) {
      var any = $$('.toc-item', g).some(function (a) { return !a.classList.contains('hide'); });
      g.classList.toggle('hidden', !any);
      if (any) setGroup(g, true);
    });
  }
  if (q) {
    q.addEventListener('input', function () { search(q.value); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var first = tocItems.filter(function (a) { return !a.classList.contains('hide'); })[0];
        if (first) { location.hash = '#p' + first.dataset.num; first.click(); }
      }
    });
  }

  /* ---------- 滚动联动：当前页 / 进度 / 侧栏高亮 ---------- */
  var barFill = $('#barFill'), nowTitle = $('#nowTitle');
  var visible = function () {
    return pages.filter(function (p) { return !p.classList.contains('hidden'); });
  };

  function update() {
    var list = visible();
    if (!barFill || !nowTitle) return;
    if (!list.length) { barFill.style.width = '0'; nowTitle.textContent = T.noMatch; return; }
    var probe = window.innerHeight * 0.28;
    var cur = list[0];
    for (var i = 0; i < list.length; i++) {
      if (list[i].getBoundingClientRect().top <= probe) cur = list[i]; else break;
    }
    var num = cur.dataset.num;
    if (nowTitle.dataset.num !== num) {
      nowTitle.dataset.num = num;
      var label = cur.dataset.label || ('第 ' + num + ' 页');
      var title = cur.dataset.title || '';
      nowTitle.textContent = T.reading
        .replace('{label}', label)
        .replace('{title}', title)
        .replace(/ · $/, '');
      tocItems.forEach(function (a) { a.classList.toggle('active', a.dataset.num === num); });
      var act = $('.toc-item.active');
      if (act && act.getBoundingClientRect) {
        var r = act.getBoundingClientRect();
        if (r.top < 60 || r.bottom > window.innerHeight - 60) act.scrollIntoView({ block: 'center' });
      }
    }
    var total = document.documentElement.scrollHeight - window.innerHeight;
    barFill.style.width = (total > 0 ? Math.min(100, (window.scrollY / total) * 100) : 0) + '%';
  }
  var tick = false;
  window.addEventListener('scroll', function () {
    if (tick) return; tick = true;
    window.requestAnimationFrame(function () { update(); tick = false; });
  }, { passive: true });
  window.addEventListener('resize', update);

  /* ---------- 键盘翻页 ---------- */
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return;
    var list = visible();
    if (!list.length) return;
    var cur = 0;
    list.forEach(function (p, i) { if (p.dataset.num === nowTitle.dataset.num) cur = i; });
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === 'j') {
      var nx = list[Math.min(cur + 1, list.length - 1)];
      nx.scrollIntoView(); location.hash = '#p' + nx.dataset.num; e.preventDefault();
    } else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || e.key === 'k') {
      var pv = list[Math.max(cur - 1, 0)];
      pv.scrollIntoView(); location.hash = '#p' + pv.dataset.num; e.preventDefault();
    } else if (e.key === '/' && q) {
      q.focus(); q.select(); e.preventDefault();
    }
  });

  /* ---------- 移动端目录 ---------- */
  var menu = $('#menu');
  if (menu) menu.addEventListener('click', function () { body.classList.toggle('nav'); });
  // 窄屏时把目录按钮移进顶栏，避免悬浮按钮压住页脚文字
  function placeMenu() {
    var bar = $('#bar');
    if (menu && bar && window.innerWidth <= 1000 && menu.parentNode !== bar) {
      bar.insertBefore(menu, bar.firstChild);
    }
  }
  placeMenu();
  window.addEventListener('resize', placeMenu);
  tocItems.forEach(function (a) {
    a.addEventListener('click', function () { body.classList.remove('nav'); });
  });

  update();

  /* ---------- 深链接：图片加载完后再校正一次滚动位置 ---------- */
  function jumpToHash() {
    var h = location.hash;
    if (!h || h.length < 2) return;
    var el = document.getElementById(h.slice(1));
    if (el) el.scrollIntoView({ block: 'start', behavior: 'instant' });
  }
  window.addEventListener('load', function () {
    jumpToHash();
    setTimeout(jumpToHash, 300);
    setTimeout(jumpToHash, 1200);
  });
  window.addEventListener('hashchange', function () { setTimeout(update, 60); });
})();
