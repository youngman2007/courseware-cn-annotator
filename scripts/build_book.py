# -*- coding: utf-8 -*-
"""把合并后的逐页 Markdown 编译成单文件、可离线阅读的 HTML 电子书（纯标准库）。

特性：侧栏分组目录、全文搜索、注释/原图/主题开关、键盘翻页、深链接、图片灯箱、
打印样式。除“原课件图”外不依赖任何外部资源。

用法：
  python build_book.py --config courseware.json
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TAG_LINE = re.compile(r"(?m)^\*\*【(.+?)】\*\*\s*$")
PAGE_HEAD = re.compile(r"^第\s*(\d+)\s*页\s*·?\s*(.*)$")
APP_HEAD = re.compile(r"^附录\s*([A-Za-z0-9]+)\s*[·:：\-]?\s*(.*)$")


# ---------------------------------------------------------------- markdown
def esc(t: str) -> str:
    return html.escape(t, quote=False)


def inline(t: str) -> str:
    t = esc(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t


def md2html(text: str) -> str:
    out, i, lines = [], 0, text.split("\n")
    n = len(lines)

    def is_table_row(s):
        return s.lstrip().startswith("|") and s.rstrip().endswith("|")

    def is_sep_row(s):
        return bool(re.fullmatch(r"\|[\s:\-|]+\|", s.strip()))

    def flush_list(stack, kind_stack):
        while stack:
            out.append("</%s>" % stack.pop())
            kind_stack.pop()

    ul_stack, kind_stack, para = [], [], []

    def flush_para():
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para.clear()

    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            flush_para(); flush_list(ul_stack, kind_stack)
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + esc("\n".join(buf)) + "</code></pre>")
            continue

        if is_table_row(line) and i + 1 < n and is_sep_row(lines[i + 1]):
            flush_para(); flush_list(ul_stack, kind_stack)
            head = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and is_table_row(lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ['<div class="tw"><table><thead><tr>']
            t += ["<th>%s</th>" % inline(c) for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                cells = r + [""] * max(0, len(head) - len(r))
                t.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cells[:len(head)]) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue

        if re.fullmatch(r"-{3,}", s):
            flush_para(); flush_list(ul_stack, kind_stack)
            i += 1
            continue

        m = re.match(r"(#{1,6})\s+(.*)", s)
        if m:
            flush_para(); flush_list(ul_stack, kind_stack)
            lv = min(len(m.group(1)) + 1, 6)
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            i += 1
            continue

        if s.startswith(">"):
            flush_para(); flush_list(ul_stack, kind_stack)
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(inline(lines[i].strip()[1:].strip())); i += 1
            out.append("<blockquote>%s</blockquote>" % "<br>".join(x for x in buf if x))
            continue

        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            flush_para()
            indent = len(m.group(1))
            level = 1 if indent >= 2 else 0
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            while len(ul_stack) - 1 > level:
                out.append("</%s>" % ul_stack.pop()); kind_stack.pop()
            if not ul_stack or len(ul_stack) == level:
                if ul_stack and kind_stack[-1] != kind:
                    out.append("</%s>" % ul_stack.pop()); kind_stack.pop()
                if len(ul_stack) < level + 1:
                    out.append("<%s>" % kind)
                    ul_stack.append(kind); kind_stack.append(kind)
            out.append("<li>%s</li>" % inline(m.group(3)))
            i += 1
            continue

        if not s:
            flush_para(); flush_list(ul_stack, kind_stack)
            i += 1
            continue

        para.append(s)
        i += 1

    flush_para(); flush_list(ul_stack, kind_stack)
    return "\n".join(out)


# ---------------------------------------------------------------- 解析
def split_cards(text: str):
    """按行首独立的 **【标签】** 切分，返回 (前言, [(标签, 内容)])。"""
    text = re.sub(r"\n-{3,}\s*$", "\n", text).strip()
    marks = list(TAG_LINE.finditer(text))
    if not marks:
        return text, []
    cards = []
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        cards.append((mk.group(1).strip(), text[mk.end():end].strip()))
    return text[:marks[0].start()], cards


def parse_pages(md: str):
    m0 = re.search(r"(?m)^### 第 1 页", md)
    if not m0:
        C.fail("Markdown 里没有行首的 '### 第 1 页'", 1)
    body = md[m0.start():]
    patches = []
    for chunk in re.split(r"(?m)^### ", body):
        if not chunk.strip():
            continue
        head, _, rest = chunk.partition("\n")
        head = head.strip()
        mp = PAGE_HEAD.match(head)
        ma = APP_HEAD.match(head)
        pre, cards = split_cards(rest)
        if mp:
            patches.append({"kind": "page", "num": int(mp.group(1)), "title": mp.group(2).strip(),
                            "cards": cards, "pre": pre.strip()})
        elif ma:
            patches.append({"kind": "app", "app_id": ma.group(1), "num": None,
                            "title": ma.group(2).strip(), "cards": cards, "pre": pre.strip()})
    if not patches:
        C.fail("没有解析出任何页面", 1)

    page_nums = [p["num"] for p in patches if p["kind"] == "page"]
    if len(set(page_nums)) != len(page_nums):
        dup = sorted({n for n in page_nums if page_nums.count(n) > 1})
        C.fail(f"页码重复：{dup}", 1)
    if page_nums != list(range(1, len(page_nums) + 1)):
        missing = [n for n in range(1, max(page_nums) + 1) if n not in set(page_nums)]
        C.fail(f"页码必须从 1 连续编号；当前缺失 {missing}。请先运行 merge_parts.py / check_md.py。", 1)

    nxt = len(page_nums) + 1
    for p in patches:
        if p["kind"] == "page":
            p["label"] = f"第 {p['num']} 页"
        else:
            p["num"] = nxt
            nxt += 1
            p["label"] = f"附录 {p['app_id']}"
    return patches


def appendix_short(p: dict) -> str:
    return p["label"].replace("附录 ", "")


# ---------------------------------------------------------------- 组装
def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown → 单文件 HTML 电子书")
    ap.add_argument("--config", required=True)
    ap.add_argument("--md")
    ap.add_argument("--out-dir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    cfg, base = C.load_config(args.config)
    md_path = Path(args.md).expanduser().resolve() if args.md else C.resolve(cfg, "md_file")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else C.resolve(cfg, "out_dir")
    slides = out_dir / (cfg.get("slides_subdir") or "slides")
    if not md_path.is_file():
        C.fail(f"找不到 Markdown：{md_path}")
    md = C.read_text(md_path)
    labels = cfg["labels"]

    pages = parse_pages(md)
    n_page = sum(1 for p in pages if p["kind"] == "page")
    n_app = len(pages) - n_page
    if cfg.get("page_count") and int(cfg["page_count"]) != n_page:
        C.fail(f"Markdown 有 {n_page} 页，但配置 page_count={cfg['page_count']}。", 1)

    for p in pages:
        pre = p.pop("pre", "")
        if pre:
            if p["cards"]:
                tag, body = p["cards"][0]
                p["cards"][0] = (tag, pre + ("\n\n" + body if body else ""))
            else:
                p["cards"] = [(labels["translation"], pre)]
        if not p["cards"]:
            p["cards"] = [(labels["translation"], "")]
        if p["kind"] == "page" and len(p["cards"]) < 2:
            p["cards"].append((labels["notes"], ""))

    page_titles = {p["num"]: p["title"] for p in pages}
    groups = C.resolve_sections(cfg, page_titles, n_page, n_app)
    covered = set()
    for g in groups:
        covered.update(range(g["from"], g["to"] + 1))
    missing_cover = [p["num"] for p in pages if p["num"] not in covered]
    if missing_cover:
        C.fail(f"分组没有覆盖这些页：{missing_cover}", 1)

    def slide_img(p):
        if p["kind"] == "app":
            return ""
        path = C.page_png(slides, p["num"])
        return f"{cfg.get('slides_subdir') or 'slides'}/p{p['num']:03d}.png" if path.exists() else ""

    open_n = int(cfg["html"].get("open_groups", 1) or 0)
    nav, nav_i = [], 0
    for g in groups:
        items = []
        for p in pages:
            if g["from"] <= p["num"] <= g["to"]:
                display = str(p["num"]) if p["kind"] == "page" else appendix_short(p)
                items.append(
                    '<a class="toc-item" href="#p%d" data-num="%d"><span class="num">%s</span>'
                    '<span class="tt">%s</span></a>' % (p["num"], p["num"], esc(display), esc(p["title"]))
                )
        is_open = nav_i < open_n
        nav_i += 1
        rng = ("附录" if g["from"] > n_page else
               (f"{g['from']}–{g['to']} 页" if g["from"] != g["to"] else f"{g['from']} 页"))
        nav.append(
            '<div class="group" data-a="%d" data-b="%d" data-open="%d" title="%s">'
            '<button class="group-h" type="button"><span class="arrow">%s</span><span class="gt">%s</span>'
            '<span class="rng">%s</span></button>'
            '<div class="group-b" %s><p class="gsub">%s</p>%s</div></div>'
            % (g["from"], g["to"], 1 if is_open else 0, esc(g["name"] + "：" + g["desc"]),
               "▾" if is_open else "▸", esc(g["short"]), esc(rng),
               "" if is_open else 'style="display:none"', esc(g["desc"]), "".join(items))
        )

    secs = []
    for idx, p in enumerate(pages):
        img = slide_img(p)
        fig = ('<figure class="slidefig hidden"><img loading="lazy" src="%s" alt="%s 原课件图">'
               '<figcaption>%s · 原课件画面（点击图片可放大）</figcaption></figure>'
               % (esc(img), esc(p["label"]), esc(p["label"]))) if img else ""
        first_tag, first_body = p["cards"][0]
        cards_html = ('<div class="card slides"><div class="tag">%s</div><div class="body">%s</div></div>'
                      % (esc(first_tag),
                         md2html(first_body) if first_body else f'<p class="empty">{esc(labels["empty_page"])}</p>'))
        for i, (tag, bodytxt) in enumerate(p["cards"][1:], 1):
            if p["kind"] == "page" and i == 1:
                tag = tag + " · " + labels["notes_suffix"]
            cards_html += ('<div class="card notes"><div class="tag">%s</div><div class="body">%s</div></div>'
                           % (esc(tag),
                              md2html(bodytxt) if bodytxt else f'<p class="empty">{esc(labels["empty_notes"])}</p>'))
        prev_p = pages[idx - 1] if idx > 0 else None
        next_p = pages[idx + 1] if idx + 1 < len(pages) else None
        pager = '<div class="pager">'
        pager += (f'<a class="btn" href="#p{prev_p["num"]}">{esc(labels["prev"])}</a>'
                  if prev_p else '<span class="btn ghost disabled">—</span>')
        pager += f'<span class="mid">{p["num"]} / {len(pages)}</span>'
        pager += (f'<a class="btn" href="#p{next_p["num"]}">{esc(labels["next"])}</a>'
                  if next_p else '<span class="btn ghost disabled">—</span>')
        pager += '</div>'
        secs.append(
            '<section class="page" id="p%(n)d" data-num="%(n)d" data-title="%(t)s" data-label="%(lb)s"'
            ' data-kind="%(k)s">'
            '<div class="page-head"><h2><span class="pnum">%(lb)s</span>%(t)s</h2>'
            '<div class="page-tools">%(btn)s<a class="btn ghost" href="#top">%(top)s</a></div></div>'
            '%(fig)s%(cards)s%(pager)s</section>'
            % dict(n=p["num"], t=esc(p["title"]), k=p["kind"], lb=esc(p["label"]), cards=cards_html,
                   fig=fig, pager=pager, top=esc(labels["top"]),
                   btn=('<button class="btn ghost slidetoggle" type="button">%s</button>' % esc(labels["slide_button"])) if img else "")
        )

    landing_items = []
    for g in groups:
        cnt = sum(1 for p in pages if g["from"] <= p["num"] <= g["to"])
        if g["from"] > n_page:
            sub = labels["landing_appendix"].format(n=cnt)
        else:
            sub = labels["landing_pages"].format(a=g["from"], b=min(g["to"], n_page), n=cnt)
        landing_items.append(
            '<a class="lcard" href="#p%d"><h3>%s</h3><p class="rng">%s</p><p class="sub">%s</p></a>'
            % (g["from"], esc(g["name"]), esc(sub), esc(g["desc"]))
        )

    css = (ASSETS / "book.css").read_text(encoding="utf-8")
    js = (ASSETS / "book.js").read_text(encoding="utf-8")
    css = css.replace("@@PAGE_SIZE@@", str(cfg["pdf"].get("page_size") or "A4"))
    css = css.replace("@@PAGE_MARGIN@@", str(cfg["pdf"].get("margin") or "12mm 11mm"))

    title = cfg["html"].get("title") or f"{cfg['title']} · 中文翻译与逐页注释"
    brand = cfg["html"].get("brand") or cfg.get("short_title") or cfg["title"]
    brand_sub = cfg["html"].get("brand_sub") or (
        f"{cfg.get('subtitle') or ''} · 共 {n_page} 页" + (f" + 附录 {n_app} 篇" if n_app else "")
    )
    app_names = "、".join(p["label"] for p in pages if p["kind"] == "app")

    footer_lines = list(cfg["html"].get("footer_lines") or [])
    if not footer_lines:
        footer_lines = [
            f"本网页由课件 `{Path(str(cfg.get('source_pdf', ''))).name}`（{n_page} 页）逐页翻译并注释而成。",
            f"每页分两块：**{labels['translation']}**（原文译文）与 **{labels['notes']}**（{labels['notes_suffix']}）。"
            "发现课件笔误处已在注释中用 ⚠️ 标出。",
        ]
        if n_app:
            footer_lines.append(f"文末另附 **{app_names}**，复习时可当速查表直接查。")
    footer_html = "\n    ".join("<p>%s</p>" % inline(x) for x in footer_lines)

    js_cfg = {
        "storageKey": cfg["html"].get("storage_key") or "book",
        "defaultTheme": cfg["html"].get("default_theme") or "light",
        "i18n": {
            "notesOn": labels["notes_on"], "notesOff": labels["notes_off"],
            "imgsOn": labels["imgs_on"], "imgsOff": labels["imgs_off"],
            "themeDark": labels["theme_dark"], "themeLight": labels["theme_light"],
            "slideBtn": labels["slide_button"], "slideBtnOpen": labels["slide_button_open"],
            "reading": "正在阅读：{label} · {title}", "noMatch": "没有匹配的页面",
        },
    }
    import json as _json
    cfg_script = "window.BOOK_CFG = " + _json.dumps(js_cfg, ensure_ascii=False) + ";"

    doc = """<!DOCTYPE html>
<html lang="@@LANG@@" data-theme="@@THEME@@">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="courseware-cn-annotator">
<title>@@TITLE@@</title>
<style>
@@CSS@@
</style>
</head>
<body>
<a id="top"></a>
<button id="menu" class="iconbtn" type="button" aria-label="@@TOC_LABEL@@">☰</button>
<aside id="side">
  <div class="side-head">
    <div class="brand">@@BRAND@@</div>
    <div class="brand-sub">@@BRAND_SUB@@</div>
  </div>
  <div class="searchwrap"><input id="q" type="search" placeholder="@@SEARCH@@" autocomplete="off"></div>
  <div class="side-actions">
    <button id="btnNotes" class="chip on" type="button">@@BTN_NOTES@@</button>
    <button id="btnImgs" class="chip" type="button">@@BTN_IMGS@@</button>
    <button id="btnTheme" class="chip" type="button">@@BTN_THEME@@</button>
    <button id="btnPrint" class="chip" type="button">@@BTN_PRINT@@</button>
  </div>
  <nav id="toc">
    @@LANDING_GROUP@@
    @@NAV@@
  </nav>
  <div class="side-foot">按 <kbd>←</kbd> <kbd>→</kbd> 翻页 · <kbd>/</kbd> 搜索 · 网页可离线使用</div>
</aside>
<main id="main">
  <header id="bar">
    <div class="now" id="nowTitle">@@READING@@</div>
    <div class="progress"><div id="barFill"></div></div>
  </header>
  <div id="content">
@@SECTIONS@@
  </div>
  <footer class="docfoot">
    @@FOOTER@@
  </footer>
</main>
<div id="lightbox" class="hidden"><img id="lightboxImg" alt=""><div class="lb-tip">点击任意处关闭</div></div>
<script>
@@CFG_SCRIPT@@
</script>
<script>
@@JS@@
</script>
</body>
</html>
"""

    landing_group = ""
    if cfg["html"].get("include_landing", True):
        landing_group = (
            '<div class="group landing"><button class="group-h" type="button"><span class="arrow">▾</span>'
            '%s<span class="rng">%s</span></button><div class="group-b">%s</div></div>'
            % (esc(labels["toc_overview"]), esc(labels["overview_hint"]), "".join(landing_items))
        )

    first = pages[0]
    reading = f"正在阅读：{first['label']} · {first['title']}"

    replacements = {
        "@@LANG@@": esc(cfg["html"].get("lang") or "zh-CN"),
        "@@THEME@@": esc(cfg["html"].get("default_theme") or "light"),
        "@@TITLE@@": esc(title),
        "@@CSS@@": css,
        "@@JS@@": js,
        "@@CFG_SCRIPT@@": cfg_script,
        "@@BRAND@@": esc(brand),
        "@@BRAND_SUB@@": esc(brand_sub),
        "@@SEARCH@@": esc(labels["search_placeholder"]),
        "@@BTN_NOTES@@": esc(labels["notes_on"]),
        "@@BTN_IMGS@@": esc(labels["imgs_off"]),
        "@@BTN_THEME@@": esc(labels["theme_dark"]),
        "@@BTN_PRINT@@": esc(labels["print"]),
        "@@TOC_LABEL@@": esc(labels["toc_overview"]),
        "@@LANDING_GROUP@@": landing_group,
        "@@NAV@@": "\n    ".join(nav),
        "@@READING@@": esc(reading),
        "@@SECTIONS@@": "\n".join(secs),
        "@@FOOTER@@": footer_html,
    }
    for k, v in replacements.items():
        doc = doc.replace(k, v)

    if not any(slide_img(p) for p in pages):
        doc = doc.replace('<button id="btnImgs"', '<button id="btnImgs" hidden', 1)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    C.write_text(out, doc)

    imgs = sorted(slides.glob("p*.png")) if slides.is_dir() else []
    print(f"页面 {n_page} 页 + 附录 {n_app} 篇；分组 {len(groups)} 个；原图 {len(imgs)} 张")
    print(f"输出：{out}（{len(doc.encode('utf-8')) / 1024:.1f} KB）")
    if args.json:
        C.emit_json({"out": str(out), "pages": n_page, "appendix": n_app, "groups": len(groups),
                     "slides": len(imgs), "bytes": len(doc.encode("utf-8"))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
