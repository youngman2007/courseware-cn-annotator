# -*- coding: utf-8 -*-
"""电子书成品自检：结构计数、无头 DOM 功能测试、布局几何、截图、PDF 校验。

用法：
  python verify_book.py --config courseware.json --all
  python verify_book.py --config courseware.json --check-html --dom
  python verify_book.py --config courseware.json --layout --shots --pdf
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

PROBE_JS = r"""
<script>
(function () {
  window.__errs = [];
  window.addEventListener('error', function (e) { window.__errs.push(String(e.message || e)); });
  window.addEventListener('load', function () {
    setTimeout(function () {
      var R = { errors: window.__errs.slice() };
      var $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };
      var pages = $$('.page'), notes = $$('.card.notes'), figs = $$('.slidefig');
      R.innerWidth = window.innerWidth;
      R.pages = pages.length; R.notes = notes.length; R.figs = figs.length;
      R.toc = $$('.toc-item').length; R.groups = $$('.group').length;
      R.appendix = $$('.page[data-kind="app"]').length;
      R.title = document.title;
      R.overflow = document.documentElement.scrollWidth > window.innerWidth + 1;

      // 布局几何
      var bad = [];
      $$('.card,.slidefig,.page-head,.pager').forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.right > window.innerWidth + 1 || r.left < -1) bad.push(el.className || el.tagName);
      });
      R.outOfViewport = bad.slice(0, 5);
      R.overlap = false;
      var side = document.getElementById('side'), main = document.getElementById('main');
      if (side && main && getComputedStyle(side).position !== 'fixed') {
        var a = side.getBoundingClientRect(), b = main.getBoundingClientRect();
        R.overlap = a.right > b.left + 1;
      }
      var menu = document.getElementById('menu');
      R.menuVisible = !!(menu && getComputedStyle(menu).display !== 'none');
      R.scrollTables = $$('.tw').filter(function (t) { return t.scrollWidth > t.clientWidth + 2; }).length;

      // 搜索
      var q = document.getElementById('q');
      function vis(sel) {
        return $$(sel).filter(function (x) { return !x.classList.contains('hidden') && !x.classList.contains('hide'); }).length;
      }
      if (q) {
        var kw = __PROBE_KW__;
        q.value = kw; q.dispatchEvent(new Event('input'));
        R.searchHits = vis('.page');
        R.searchNo = (function () { q.value = 'zzzqqqxx'; q.dispatchEvent(new Event('input')); return vis('.page'); })();
        q.value = ''; q.dispatchEvent(new Event('input'));
        R.clearedPages = vis('.page');
        R.restoredGroups = $$('.group[data-open]').every(function (g) {
          var b = g.querySelector('.group-b');
          return (g.dataset.open === '1') === (!!b && b.style.display !== 'none');
        });
        if (R.appendix) {
          q.value = '附录'; q.dispatchEvent(new Event('input'));
          R.appendixHits = vis('.page[data-kind="app"]');
          q.value = ''; q.dispatchEvent(new Event('input'));
        }
        R.search = true;
      } else { R.search = false; }

      // 注释 / 原图开关
      var bn = document.getElementById('btnNotes');
      R.notesTested = !!bn;
      if (bn) {
        bn.click(); R.notesHidden = notes.filter(function (c) { return getComputedStyle(c).display !== 'none'; }).length;
        bn.click(); R.notesRestored = notes.filter(function (c) { return getComputedStyle(c).display !== 'none'; }).length;
      }
      var bi = document.getElementById('btnImgs');
      R.imgsTested = !!(bi && figs.length);
      if (R.imgsTested) {
        bi.click(); R.imgsShown = figs.filter(function (f) { return !f.classList.contains('hidden'); }).length;
        bi.click(); R.imgsRestored = figs.filter(function (f) { return !f.classList.contains('hidden'); }).length;
      }

      // 单页原图按钮
      var st = document.querySelector('.slidetoggle');
      if (st) {
        st.click();
        var f = st.closest('.page').querySelector('.slidefig');
        R.slideBtnVisible = !!f && !f.classList.contains('hidden');
      }

      // 分组展开
      var gs = $$('.group'), g2 = gs[1];
      if (g2) {
        var h = g2.querySelector('.group-h'), b = g2.querySelector('.group-b');
        h.click(); R.groupAfter = b.style.display;
        h.click(); R.groupBack = b.style.display;
      }

      // 键盘翻页 + / 聚焦
      if (pages.length > 1) {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        R.keyboardHash = location.hash;
        R.keyboardExpected = '#p' + pages[1].dataset.num;
      }
      document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
      R.slashFocus = !!(document.activeElement && document.activeElement.id === 'q');

      document.title = 'PROBE::' + encodeURIComponent(JSON.stringify(R));
    }, 600);
  });
})();
</script>
"""


# ---------------------------------------------------------------- chrome
def run_chrome(chrome: str, args: list[str], timeout: int = 90) -> str:
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--allow-file-access-from-files"] + args
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", "replace")


def _iframe_wrapper(out_dir: Path, page_name: str, w: int, h: int, *, keep_meta: bool) -> Path:
    """Chrome 无头模式的窗口宽度有下限（约 512px），窄屏用 iframe 强制出真实视口。"""
    if keep_meta:
        script = """<script>
var f=document.getElementById('f');
var t=setInterval(function(){
  try{var x=f.contentDocument.title;
    if(x.indexOf('PROBE::')===0){document.title=x;clearInterval(t);}
  }catch(e){document.title='PROBE::ERR';clearInterval(t);}
},150);
</script>"""
    else:
        script = ""
    wrap = f"""<!doctype html><meta charset="utf-8">
<body style="margin:0;background:#f4f6f9">
<iframe id="f" src="{page_name}" style="width:{w}px;height:{h}px;border:0;display:block"></iframe>
{script}
</body>"""
    p = out_dir / f"_wrap_{w}.html"
    C.write_text(p, wrap)
    return p


def probe(chrome: str, out_dir: Path, src: str, kw: str, w: int, h: int) -> dict:
    js = PROBE_JS.replace("__PROBE_KW__", json.dumps(kw, ensure_ascii=False))
    doc = src.replace("</head>", js + "</head>", 1)
    tmp = out_dir / f"_probe_{w}.html"
    C.write_text(tmp, doc)
    wrap = None
    try:
        dump_target = tmp.as_uri()
        win_w = w
        if w < 600:
            wrap = _iframe_wrapper(out_dir, tmp.name, w, h, keep_meta=True)
            dump_target = wrap.as_uri()
            win_w = 512
        raw = run_chrome(chrome, [f"--window-size={win_w},{h}", "--virtual-time-budget=9000",
                                  "--dump-dom", dump_target])
    finally:
        for p in (tmp, wrap):
            if p and p.exists():
                p.unlink()
    m = re.search(r"<title>(.*?)</title>", raw, re.S)
    if not m or not m.group(1).startswith("PROBE::"):
        raise RuntimeError("无头浏览器没有返回探针结果（页面脚本可能崩溃）")
    data = urllib.parse.unquote(m.group(1)[len("PROBE::"):])
    if data == "ERR":
        raise RuntimeError("iframe 里的页面无法访问（宽度模拟失败）")
    return json.loads(data)


def shoot(chrome: str, out_dir: Path, src: str, num: int, dest: Path, w: int, h: int,
          query: str = "") -> bool:
    # 预览只展示一页：隐藏顶栏，避免“正在阅读”仍按整篇计算而显示成最后一页
    style = ("<style>.page{display:none!important}"
             f"#p{num}{{display:block!important}}"
             "#bar{display:none!important}"
             "@media(min-width:1001px){.group.landing{display:none!important}}</style>")
    doc = src.replace("</head>", style + "</head>", 1)
    tmp = out_dir / f"_preview_{num}_{w}.html"
    C.write_text(tmp, doc)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wrap = None
    try:
        target = tmp.as_uri() + query
        win_w = w
        if w < 600:
            wrap = _iframe_wrapper(out_dir, tmp.name, w, h, keep_meta=False)
            target = wrap.as_uri() + query
            win_w = 512
        run_chrome(chrome, [f"--window-size={win_w},{h}", "--virtual-time-budget=9000",
                            f"--screenshot={dest}", target])
    finally:
        for p in (tmp, wrap):
            if p and p.exists():
                p.unlink()
    # 窄屏截图外层窗口比 iframe 宽，裁掉右侧空白，方便直接看布局
    if w < 600 and dest.is_file():
        try:
            from PIL import Image
            im = Image.open(dest)
            im.crop((0, 0, min(w, im.width), im.height)).save(dest)
        except Exception:
            pass
    return dest.is_file() and dest.stat().st_size > 4096


# ---------------------------------------------------------------- 检查项
def check_html(out_dir: Path, src: str, cfg: dict, failures: list[str], notes: list[str]) -> dict:
    info = {}
    sections_n = len(re.findall(r'<section class="page"', src))
    pages = len(re.findall(r'<section class="page"[^>]*data-kind="page"', src))
    apps = len(re.findall(r'<section class="page"[^>]*data-kind="app"', src))
    ids = [int(x) for x in re.findall(r'<section class="page" id="p(\d+)"', src)]
    notes_n = len(re.findall(r'<div class="card notes">', src))
    figs = len(re.findall(r'<figure class="slidefig', src))
    toc = len(re.findall(r'<a class="toc-item"', src))
    info.update(pages=pages, appendices=apps, sections=sections_n, notes=notes_n,
                figs=figs, toc=toc, ids=ids)

    if cfg.get("page_count") and pages != int(cfg["page_count"]):
        failures.append(f"页面数 {pages} ≠ page_count={cfg['page_count']}")
    if len(ids) != sections_n or len(set(ids)) != len(ids):
        failures.append(f"页面 id 不唯一或缺失：{ids[:10]}…")
    if notes_n < pages:
        failures.append(f"注释卡 {notes_n} 张 < 页面 {pages}（每页至少一张注释卡）")
    if toc < sections_n:
        failures.append(f"目录项 {toc} < 页面 {sections_n}")
    if not re.search(r"<title>[^<]+</title>", src):
        failures.append("<title> 为空")

    for anchor in set(re.findall(r'href="#p(\d+)"', src)):
        if int(anchor) not in set(ids):
            failures.append(f"链接 #p{anchor} 没有对应 section")

    missing_imgs = []
    for rel in set(re.findall(r'<img[^>]+src="([^"]+)"', src)):
        if rel.startswith("data:"):
            continue
        if not (out_dir / rel).is_file():
            missing_imgs.append(rel)
    if missing_imgs:
        failures.append(f"图片路径不存在：{missing_imgs[:5]}（共 {len(missing_imgs)} 张）")

    leftovers = sorted(set(re.findall(r"@@[A-Z_]+@@|__[A-Z]+__", src)))
    if leftovers:
        failures.append(f"模板占位符未替换：{leftovers}")
    for bad in ("None", "%s", "%d"):
        if bad in src:
            notes.append(f"成品中出现可疑字符串 {bad!r}，请人工确认")

    if '@page{size:@@' in src:
        failures.append("@page 尺寸占位符未替换")
    if "data-label=" not in src:
        failures.append("section 缺少 data-label（附录页码会显示错误）")

    slides_dir = out_dir / (cfg.get("slides_subdir") or "slides")
    actual_slides = sorted(slides_dir.glob("p*.png")) if slides_dir.is_dir() else []
    info["slides_on_disk"] = len(actual_slides)
    if figs and figs != len(actual_slides):
        notes.append(f"HTML 原图 {figs} 张，磁盘 {len(actual_slides)} 张（可能有页面缺图）")
    return info


def check_dom(rep: dict, expect_sections: int, expect_notes: int,
              failures: list[str], skipped: list[str]) -> None:
    if rep.get("errors"):
        failures.append(f"页面 JS 报错：{rep['errors']}")
    if rep.get("pages") != expect_sections:
        failures.append(f"DOM 页面数 {rep.get('pages')} ≠ HTML {expect_sections}")
    if rep.get("notes") != expect_notes:
        failures.append(f"DOM 注释卡 {rep.get('notes')} ≠ HTML {expect_notes}")
    if not rep.get("search"):
        skipped.append("搜索框不存在，跳过搜索测试")
    else:
        if not rep.get("searchHits"):
            failures.append("搜索关键词命中 0 页")
        if rep.get("searchNo") != 0:
            failures.append(f"搜索乱词仍命中 {rep.get('searchNo')} 页")
        if rep.get("clearedPages") != expect_sections:
            failures.append(f"清空搜索后只显示 {rep.get('clearedPages')}/{expect_sections} 页")
        if not rep.get("restoredGroups"):
            failures.append("清空搜索后分组展开状态没有恢复")
        if rep.get("appendix") and rep.get("appendixHits") != rep.get("appendix"):
            failures.append(f"搜索“附录”命中 {rep.get('appendixHits')}/{rep.get('appendix')} 篇")
    if rep.get("notesTested"):
        if rep.get("notesHidden") != 0:
            failures.append(f"点“隐藏注释”后仍有 {rep.get('notesHidden')} 张可见")
        if rep.get("notesRestored") != expect_notes:
            failures.append(f"恢复注释后可见 {rep.get('notesRestored')}/{expect_notes} 张")
    if rep.get("imgsTested"):
        if rep.get("imgsShown") != rep.get("figs"):
            failures.append(f"点“显示原图”后显示 {rep.get('imgsShown')}/{rep.get('figs')} 张")
        if rep.get("imgsRestored") != 0:
            failures.append("再次点击后原图没有全部收起")
    elif rep.get("figs"):
        failures.append("存在原图但“显示原图”按钮不可用")
    else:
        skipped.append("没有原课件图，原图开关与单页按钮测试已跳过")
    if rep.get("keyboardExpected") and rep.get("keyboardHash") != rep.get("keyboardExpected"):
        failures.append(f"方向键翻页 hash={rep.get('keyboardHash')!r}，期望 {rep.get('keyboardExpected')!r}")
    if not rep.get("slashFocus"):
        failures.append("按 / 没有聚焦搜索框")


def check_layout(rep: dict, width: int, failures: list[str]) -> None:
    if rep.get("overflow"):
        failures.append(f"{width}px：页面出现横向溢出")
    if rep.get("outOfViewport"):
        failures.append(f"{width}px：{rep['outOfViewport']} 超出视口")
    if rep.get("overlap"):
        failures.append(f"{width}px：侧栏与正文重叠")
    if width <= 1000 and not rep.get("menuVisible"):
        failures.append("移动端目录按钮不可见")
    if width > 1000 and rep.get("menuVisible"):
        failures.append("桌面端不应显示移动目录按钮")


def check_pdf(pdf: Path, expect_min: int, failures: list[str], notes: list[str],
              shots_dir: Path, cfg: dict) -> dict:
    info = {"pdf": str(pdf)}
    if not pdf.is_file():
        failures.append(f"找不到 PDF：{pdf}")
        return info
    try:
        import pymupdf
    except Exception:
        notes.append("未安装 PyMuPDF，跳过 PDF 内容校验")
        return info
    doc = pymupdf.open(str(pdf))
    info["pages"] = doc.page_count
    info["size_pt"] = [round(doc[0].rect.width, 1), round(doc[0].rect.height, 1)]
    if doc.page_count < expect_min:
        failures.append(f"PDF 只有 {doc.page_count} 页，少于 {expect_min} 页")
    sizes = {"A4": (595.28, 841.89), "A3": (841.89, 1190.55),
             "LETTER": (612.0, 792.0), "LEGAL": (612.0, 1008.0)}
    want = sizes.get(str(cfg["pdf"].get("page_size") or "A4").upper())
    if want and (abs(doc[0].rect.width - want[0]) > 3 or abs(doc[0].rect.height - want[1]) > 3):
        failures.append(f"PDF 首页尺寸 {info['size_pt']} pt，与 {cfg['pdf'].get('page_size')} 不符")
    texts = []
    for i in (0, doc.page_count // 2, doc.page_count - 1):
        try:
            texts.append(doc[i].get_text("text"))
        except Exception:
            texts.append("")
    info["text_chars"] = [len(t.strip()) for t in texts]
    if not any(len(t.strip()) > 20 for t in texts):
        failures.append("PDF 抽样页几乎没有可提取文字（可能整页被当作图片）")
    if "第 1 页" not in (texts[0] + texts[1]):
        notes.append("PDF 前几页未找到“第 1 页”文本，请人工确认打印顺序")
    shots_dir.mkdir(parents=True, exist_ok=True)
    for i in sorted({0, doc.page_count // 2, doc.page_count - 1}):
        if 0 <= i < doc.page_count:
            doc[i].get_pixmap(dpi=80).save(str(shots_dir / f"pdf_p{i + 1:03d}.png"))
    doc.close()
    return info


def pick_pages(spec: str | None, nums: list[int]) -> list[int]:
    """解析 verify.sample_pages：first / middle / last / 页码，逗号分隔。"""
    tokens = [t.strip().lower() for t in str(spec or "first,middle,last").split(",") if t.strip()]
    picked: list[int] = []
    for tok in tokens:
        if tok == "first":
            picked.append(nums[0])
        elif tok == "middle":
            picked.append(nums[len(nums) // 2])
        elif tok == "last":
            picked.append(nums[-1])
        elif tok.isdigit() and int(tok) in nums:
            picked.append(int(tok))
    return sorted(dict.fromkeys(picked)) or [nums[0], nums[len(nums) // 2], nums[-1]]


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="电子书成品自检")
    ap.add_argument("--config", required=True)
    ap.add_argument("--html")
    ap.add_argument("--pdf")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check-html", action="store_true")
    ap.add_argument("--dom", action="store_true")
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--pdf-check", dest="pdf_check", action="store_true")
    ap.add_argument("--chrome")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    cfg, base = C.load_config(args.config)
    if args.all:
        args.check_html = args.dom = args.layout = args.shots = args.pdf_check = True
    if not any((args.check_html, args.dom, args.layout, args.shots, args.pdf_check)):
        args.check_html = args.dom = args.layout = True

    out_dir = C.resolve(cfg, "out_dir")
    html_path = Path(args.html).expanduser().resolve() if args.html else out_dir / "index.html"
    if not html_path.is_file():
        C.fail(f"找不到网页：{html_path}")
    src = C.read_text(html_path)
    verify_dir = out_dir / "_verify"
    verify_dir.mkdir(exist_ok=True)

    failures: list[str] = []
    notes: list[str] = []
    skipped: list[str] = []
    report: dict = {"html": str(html_path)}

    if args.check_html:
        info = check_html(out_dir, src, cfg, failures, notes)
        report["structure"] = info
        print(f"结构：{info['pages']} 页 + {info['appendices']} 附录 / {info['notes']} 注释 / "
              f"{info['figs']} 原图 / {info['toc']} 目录项")

    chrome = C.detect_chrome(args.chrome or cfg["verify"].get("chrome") or cfg["pdf"].get("chrome"))
    need_browser = args.dom or args.layout or args.shots
    if need_browser and not chrome:
        C.fail("找不到 Chrome 或 Edge，无法做 DOM/布局/截图检查。")

    kw = cfg["verify"].get("probe_keyword")
    if not kw:
        m = re.search(r'<section class="page"[^>]*data-title="([^"]+)"', src)
        title = H.unescape(m.group(1)) if m else ""
        kw = re.sub(r"[\s·—–\-]+", "", title)[:6] or "第"
    report["probe_keyword"] = kw

    if need_browser:
        st = report.get("structure", {})
        n_sections = st.get("sections") or len(re.findall(r'<section class="page"', src))
        n_notes = st.get("notes") or len(re.findall(r'<div class="card notes">', src))
        design_w = int(cfg["verify"].get("shot_width") or 1400)
        design_h = int(cfg["verify"].get("shot_height") or 1200)
        try:
            desk = probe(chrome, out_dir, src, kw, design_w, design_h)
            mob = probe(chrome, out_dir, src, kw, 430, 900)
        except Exception as exc:
            C.fail(f"DOM 探针失败：{exc}")
        report["dom_desktop"] = desk
        report["dom_mobile"] = mob

        if args.dom:
            check_dom(desk, n_sections, n_notes, failures, skipped)
            print(f"DOM：搜索“{kw}”命中 {desk.get('searchHits')} 页；"
                  f"注释 {desk.get('notes')} 张；键盘 {desk.get('keyboardHash')}")
        if args.layout:
            check_layout(desk, desk.get("innerWidth", design_w), failures)
            check_layout(mob, mob.get("innerWidth", 430), failures)
            print(f"布局：桌面 {desk.get('innerWidth')}px 溢出={desk.get('overflow')} 重叠={desk.get('overlap')}；"
                  f"移动 {mob.get('innerWidth')}px 溢出={mob.get('overflow')} 菜单={mob.get('menuVisible')}")

    if args.shots and chrome:
        nums = [int(x) for x in re.findall(r'<section class="page" id="p(\d+)"', src)]
        if nums:
            picks = pick_pages(cfg["verify"].get("sample_pages"), nums)
            ok = 0
            for n in picks:
                if shoot(chrome, out_dir, src, n, verify_dir / f"desktop_p{n:03d}.png", 1400, 1600):
                    ok += 1
            for n in picks[:2]:
                if shoot(chrome, out_dir, src, n, verify_dir / f"mobile_p{n:03d}.png", 430, 900):
                    ok += 1
            report["shots"] = ok
            print(f"截图：{ok} 张 → {verify_dir}")
            if ok == 0:
                failures.append("截图全部失败")

    if args.pdf_check:
        pdf = Path(args.pdf).expanduser().resolve() if args.pdf else C.pdf_output(cfg)
        expect_min = int(cfg["verify"].get("min_pdf_pages") or 1)
        if not cfg["verify"].get("min_pdf_pages"):
            expect_min = max(1, report.get("structure", {}).get("sections", 1))
        info = check_pdf(pdf, expect_min, failures, notes, verify_dir, cfg)
        report["pdf"] = info
        print(f"PDF：{info.get('pages', '?')} 页，尺寸 {info.get('size_pt')}")

    for s in skipped:
        print("  ↷ " + s)
    for n in notes:
        print("  ⚠ " + n)
    for f in failures:
        print("  ✗ " + f)
    ok = not failures
    print("自检：" + ("通过" if ok else f"失败（{len(failures)} 项）"))
    if args.json:
        report["failures"] = failures
        report["warnings"] = notes
        report["ok"] = ok
        C.emit_json(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
