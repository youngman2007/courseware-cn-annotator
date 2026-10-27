# -*- coding: utf-8 -*-
"""把 _out/part*.md 合并成主 Markdown，并自动插入（或替换）目录。

目录用 <!-- AUTO-TOC:START --> / <!-- AUTO-TOC:END --> 包住：重复运行不会叠加。
分批写作时可先用 --allow-partial 预览，缺页只警告不报错。

用法：
  python merge_parts.py --config courseware.json
  python merge_parts.py --config courseware.json --allow-partial
  python merge_parts.py --config courseware.json --no-toc
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

PAGE_HEAD = re.compile(r"^第\s*(\d+)\s*页\s*·?\s*(.*)$")
APP_HEAD = re.compile(r"^附录\s*([A-Za-z0-9]+)\s*[·:：\-]?\s*(.*)$")
TOC_BLOCK = re.compile(r"(?ms)^<!-- AUTO-TOC:START -->.*?<!-- AUTO-TOC:END -->\n?")


def parse_pages(doc: str):
    """返回 (pages, apps)；每项 {num, title, label, kind}。"""
    m0 = re.search(r"(?m)^### 第 1 页", doc)
    if not m0:
        C.fail("合并结果里没有 '### 第 1 页'，无法生成目录。", 1)
    body = doc[m0.start():]
    pages, apps = [], []
    for chunk in re.split(r"(?m)^### ", body):
        if not chunk.strip():
            continue
        head = chunk.split("\n", 1)[0].strip()
        mp = PAGE_HEAD.match(head)
        ma = APP_HEAD.match(head)
        if mp:
            n = int(mp.group(1))
            pages.append({"num": n, "title": mp.group(2).strip(), "label": f"第 {n} 页", "kind": "page"})
        elif ma:
            aid = ma.group(1)
            title = ma.group(2).strip()
            apps.append({"num": None, "app_id": aid, "title": title, "label": f"附录 {aid}", "kind": "app"})
    nums = [p["num"] for p in pages]
    if len(set(nums)) != len(nums):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        C.fail(f"页码重复：{dup}", 1)
    if nums != sorted(nums):
        C.warn("页面顺序与页码顺序不一致")
    nxt = max(nums) + 1 if nums else 1
    for a in apps:
        a["num"] = nxt
        nxt += 1
    return pages + apps


def page_range_label(a: int, b: int) -> str:
    return f"第 {a} 页" if a == b else f"第 {a} ～ {b} 页"


def build_toc(cfg: dict, pages: list[dict], groups: list[dict], n_page: int, n_app: int) -> str:
    labels = cfg["labels"]
    app_labels = [p["label"] for p in pages if p["kind"] == "app"]
    app_names = "、".join(app_labels)
    if n_app:
        tail = f"末尾另附 **{app_names}** 速查附录。"
    else:
        tail = "本文档不含附录。"

    rows = []
    for g in groups:
        a, b = g["from"], g["to"]
        if a > n_page:
            rng = "——"
        else:
            pa, pb = a, min(b, n_page)
            rng = page_range_label(pa, pb)
        desc = g.get("desc") or ""
        parts = []
        if a <= n_page:
            pa, pb = a, min(b, n_page)
            parts.append(f"`### 第 {pa} 页`" if pa == pb else f"`### 第 {pa} 页` ～ `### 第 {pb} 页`")
        if b > n_page:
            labels_in = [p["label"] for p in pages if p["kind"] == "app" and max(a, n_page + 1) <= p["num"] <= b]
            parts.append("、".join(f"`### {x}`" for x in labels_in))
        search = "；".join(x for x in parts if x)
        rows.append(f"| {g['name']} | {rng} | {desc} | {search} |")

    head = (
        "<!-- AUTO-TOC:START -->\n"
        "## 目录（按 PPT 页码索引）\n\n"
        f"本文件共 {n_page} 节，与课件 PDF 的 {n_page} 页一一对应；{tail}\n\n"
        "| 板块 | 页码 | 内容 | 在本文件中搜索 |\n"
        "|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n"
        f"**使用建议**：先读某一页的【{labels['translation']}】了解“课件说了什么”，"
        f"再读【{labels['notes']}】的“这页在说什么 / 为什么 / 怎么用”。\n"
        "<!-- AUTO-TOC:END -->\n"
    )
    return head


def main() -> int:
    ap = argparse.ArgumentParser(description="合并逐页 Markdown 并插入目录")
    ap.add_argument("--config")
    ap.add_argument("--parts-dir")
    ap.add_argument("--part-glob")
    ap.add_argument("--out")
    ap.add_argument("--page-count", type=int)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--no-toc", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    if args.config:
        cfg, base = C.load_config(args.config)
        parts_dir = Path(args.parts_dir).expanduser().resolve() if args.parts_dir else C.resolve(cfg, "parts_dir")
        out = Path(args.out).expanduser().resolve() if args.out else C.resolve(cfg, "md_file")
        pattern = args.part_glob or cfg.get("part_glob") or "part*.md"
        expected = args.page_count or cfg.get("page_count")
    else:
        if not args.parts_dir or not args.out:
            C.fail("需要 --config，或同时提供 --parts-dir 与 --out")
        parts_dir = Path(args.parts_dir).expanduser().resolve()
        out = Path(args.out).expanduser().resolve()
        pattern = args.part_glob or "part*.md"
        expected = args.page_count
        cfg = C.deep_merge(C.DEFAULTS, {
            "title": out.stem, "short_title": out.stem, "source_pdf": "",
            "md_file": out.name, "out_dir": ".", "_config_dir": str(out.parent),
        })
        cfg["labels"] = dict(C.DEFAULT_LABELS)

    if not parts_dir.is_dir():
        C.fail(f"找不到分批目录：{parts_dir}")
    parts = sorted(parts_dir.glob(pattern), key=lambda p: C.natural_key(p.name))
    if not parts:
        C.fail(f"{parts_dir} 里没有匹配 {pattern} 的文件", 1)

    nums = []
    for p in parts:
        m = re.search(r"(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    if nums:
        expect_nums = list(range(1, max(nums) + 1))
        missing_parts = [n for n in expect_nums if n not in nums]
        if missing_parts:
            C.warn(f"分批文件编号不连续，缺少：{missing_parts}")

    texts = []
    for p in parts:
        t = C.read_text(p).strip()
        t = re.sub(r"\n-{3,}\s*$", "", t).strip()
        if not t:
            C.warn(f"空文件已跳过：{p.name}")
            continue
        texts.append(t)
    doc = "\n\n---\n\n".join(texts) + "\n"

    # 防止上游 part 里残留旧目录
    doc = TOC_BLOCK.sub("", doc)
    pages = parse_pages(doc)
    page_items = [p for p in pages if p["kind"] == "page"]
    n_page = len(page_items)
    n_app = len(pages) - n_page

    if page_items:
        actual = [p["num"] for p in page_items]
        missing = [n for n in range(1, max(actual) + 1) if n not in set(actual)]
        if missing:
            msg = f"缺少页面：{missing}"
            if args.allow_partial:
                C.warn(msg + "（--allow-partial，已继续）")
            else:
                C.fail(msg + "。分批写作时可加 --allow-partial。", 1)
        if expected and max(actual) > int(expected):
            C.fail(f"页码超出配置页数：最大 {max(actual)} > {expected}", 1)
        if expected and not args.allow_partial and len(page_items) != int(expected):
            C.fail(f"页面数 {len(page_items)} ≠ 配置页数 {expected}", 1)

    if not args.no_toc:
        page_titles = {p["num"]: p["title"] for p in pages}
        groups = C.resolve_sections(cfg, page_titles, n_page, n_app)
        toc = build_toc(cfg, pages, groups, n_page, n_app)
        # 目录必须紧跟引言、插在第一个页面标题之前；不能按第一个 --- 插，
        # 因为分批文件之间也用 --- 分隔，那样会把目录塞进第 1 页的注释卡里。
        m = re.search(r"(?m)^### 第 1 页", doc)
        at = m.start() if m else len(doc)
        head = doc[:at].rstrip()
        rest = doc[at:].lstrip("\n")
        if head:
            sep = "\n\n" if head.endswith("---") else "\n\n---\n\n"
            doc = head + sep + toc + "\n---\n\n" + rest
        else:
            doc = toc + "\n---\n\n" + rest

    C.write_text(out, doc)
    print(f"已合并 {len(parts)} 个分批 → {out}")
    print(f"页面 {n_page} 页，附录 {n_app} 篇，字符 {len(doc)}")
    if args.json:
        C.emit_json({"out": str(out), "parts": [str(p) for p in parts], "page_count": n_page,
                     "appendix": n_app, "chars": len(doc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
