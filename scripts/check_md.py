# -*- coding: utf-8 -*-
"""校验逐页注释稿是否符合 build_book.py 的 Markdown 契约。

检查项：
  · 页码从 1 开始连续、不重复、与配置页数一致
  · 每页都有【译文】与【注释】两张卡
  · 需要附录时确实存在附录
  · 表格列数一致、分隔行合法
  · 会被解析器静默丢弃的语法（链接/图片/斜体/原始 HTML/数学公式）
  · 嵌套列表（会压平，默认警告）

用法：
  python check_md.py --config courseware.json
  python check_md.py --config courseware.json --allow-partial   # 分批写作时
  python check_md.py --config courseware.json --strict
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
TAG_LINE = re.compile(r"(?m)^\*\*【(.+?)】\*\*\s*$")
TABLE_SEP = re.compile(r"^\|[\s:\-|]+\|$")


def split_cards(text: str):
    """按行首独立的 **【标签】** 切分；返回 (首个标签前的文字, [(标签, 内容)])。"""
    marks = list(TAG_LINE.finditer(text))
    if not marks:
        return text, []
    cards = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        cards.append((m.group(1).strip(), text[m.end():end].strip()))
    return text[:marks[0].start()], cards


def table_errors(lines: list[str], first_lineno: int) -> list[str]:
    errs = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("|") and s.endswith("|") and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1].strip()):
            head_cols = len(s.strip("|").split("|"))
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|") and lines[j].strip().endswith("|"):
                cols = len(lines[j].strip().strip("|").split("|"))
                if cols != head_cols:
                    errs.append(f"第 {first_lineno + j} 行：表格列数 {cols} ≠ 表头 {head_cols}")
                j += 1
            i = j
        else:
            i += 1
    return errs


def scan_syntax(text: str, lineno0: int, errors: list[str], warnings: list[str]) -> None:
    in_fence = False
    for k, line in enumerate(text.split("\n")):
        ln = lineno0 + k
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.search(r"!\[[^\]]*\]\(", line):
            errors.append(f"第 {ln} 行：Markdown 图片语法会被丢弃（原课件图由渲染脚本生成）")
        if re.search(r"(?<!!)\[[^\]]*\]\([^)]*\)", line):
            errors.append(f"第 {ln} 行：链接语法会被丢弃，请改成纯文本")
        if re.search(r"(?<!\$)\$[^$\n]+\$(?!\$)", line):
            errors.append(f"第 {ln} 行：$…$ 数学语法会被丢弃，请用代码/纯文本写公式")
        if re.search(r"</?[a-zA-Z][^>]*>", line):
            errors.append(f"第 {ln} 行：原始 HTML 会被丢弃，请删除")
        if "~~" in line:
            errors.append(f"第 {ln} 行：删除线语法会被丢弃，请改成纯文本")
        # 斜体：排除 **bold** 与代码里的 *
        plain = re.sub(r"`[^`]*`", "", line)
        plain = re.sub(r"\*\*[^*]+\*\*", "", plain)
        if re.search(r"(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)", plain):
            warnings.append(f"第 {ln} 行：*斜体* 会被当作普通星号，请改用 **粗体** 或纯文本")
        if re.match(r"^\s{2,}([-*]|\d+\.)\s+", line):
            warnings.append(f"第 {ln} 行：嵌套列表会被压平，请改成同一层或拆成段落")
        if s and not TAG_LINE.match(s) and "**【" in s:
            warnings.append(f"第 {ln} 行：正文中出现 **【…】**，不会生成卡片；卡片标记必须独占一行")


def main() -> int:
    ap = argparse.ArgumentParser(description="校验逐页注释 Markdown")
    ap.add_argument("--config")
    ap.add_argument("--md")
    ap.add_argument("--expected-pages", type=int)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    if args.config:
        cfg, base = C.load_config(args.config)
        md_path = Path(args.md).expanduser().resolve() if args.md else C.resolve(cfg, "md_file")
        expected = args.expected_pages or cfg.get("page_count")
        want_appendix = bool(cfg.get("appendix", True))
        labels = cfg["labels"]
        trans_tag, notes_tag = labels["translation"], labels["notes"]
    else:
        if not args.md:
            C.fail("需要 --config 或 --md")
        md_path = Path(args.md).expanduser().resolve()
        expected = args.expected_pages
        want_appendix = False
        trans_tag, notes_tag = "课件中文版", "注释"

    if not md_path.is_file():
        C.fail(f"找不到 Markdown：{md_path}")
    text = C.read_text(md_path)
    errors: list[str] = []
    warnings: list[str] = []

    m0 = re.search(r"(?m)^### 第 1 页", text)
    if not m0:
        C.fail(f"没有找到正文起点（行首的 '### 第 1 页'）：{md_path}", 1)
    body = text[m0.start():]
    # 正文之前还有标题/自动目录，行号必须把这部分算进去才是全文行号
    prefix_lines = text.count("\n", 0, m0.start())
    # 目录表格里也含 "### 第 1 页"，只认行首；用 finditer 是为了拿到每个块的起始行号
    marks = list(re.finditer(r"(?m)^### ", body))

    pages: list[dict] = []
    apps: list[dict] = []
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        chunk = body[mk.end():end]
        if not chunk.strip():
            continue
        head, _, rest = chunk.partition("\n")
        head = head.strip()
        line0 = prefix_lines + body.count("\n", 0, mk.end()) + 2  # rest 第一行在全文中的行号
        mp = PAGE_HEAD.match(head)
        ma = APP_HEAD.match(head)
        if mp:
            pages.append({"num": int(mp.group(1)), "title": mp.group(2).strip(),
                          "text": rest, "line0": line0})
        elif ma:
            apps.append({"id": ma.group(1), "title": ma.group(2).strip(), "text": rest,
                         "line0": line0})
        else:
            # 页面内部的三级标题会被当成新页开头，导致后半页内容丢失
            errors.append(f"第 {line0 - 1} 行：### {head} 不是页面/附录标题；"
                          "页面内的小标题请改用 #### 或 **粗体**")

    if not pages:
        C.fail("没有解析出任何页面", 1)

    app_ids = [a["id"] for a in apps]
    if len(set(app_ids)) != len(app_ids):
        dups = sorted({x for x in app_ids if app_ids.count(x) > 1})
        errors.append(f"附录编号重复：{dups}")

    nums = [p["num"] for p in pages]
    if len(set(nums)) != len(nums):
        dups = sorted({n for n in nums if nums.count(n) > 1})
        errors.append(f"页码重复：{dups}")
    if nums != sorted(nums):
        warnings.append("页面顺序与页码顺序不一致")
    mx = max(nums)
    missing = [n for n in range(1, mx + 1) if n not in set(nums)]
    if missing:
        msg = f"缺少页面：{missing}"
        (warnings if args.allow_partial else errors).append(msg)
    if expected and mx > int(expected):
        errors.append(f"页码超出配置页数：最大 {mx} > {expected}")
    if expected and not args.allow_partial and len(pages) != int(expected):
        errors.append(f"页面数 {len(pages)} ≠ 配置页数 {expected}")

    for p in pages:
        pre, cards = split_cards(p["text"])
        tags = [t for t, _ in cards]
        if len(cards) < 2:
            errors.append(f"第 {p['num']} 页：只有 {len(cards)} 张卡，应有【{trans_tag}】和【{notes_tag}】")
        if tags and tags[0] != trans_tag:
            errors.append(f"第 {p['num']} 页：第一张卡标签是【{tags[0]}】，应为【{trans_tag}】")
        if len(cards) >= 2 and tags[1] != notes_tag:
            errors.append(f"第 {p['num']} 页：第二张卡标签是【{tags[1]}】，应为【{notes_tag}】")
        if len(cards) >= 2 and len(cards[1][1]) < 20:
            warnings.append(f"第 {p['num']} 页：注释内容过短（{len(cards[1][1])} 字符），请确认不是占位")
        if pre.strip():
            warnings.append(f"第 {p['num']} 页：第一张卡之前有正文，构建时会并入第一张卡（建议移进卡片内）")
        scan_syntax(p["text"], p["line0"], errors, warnings)
        errors.extend(table_errors(p["text"].split("\n"), p["line0"]))

    if want_appendix and not apps:
        msg = "配置要求附录，但没有找到 '### 附录 X · 标题'"
        if args.allow_partial:
            warnings.append(msg + "（分批校验时允许，最终合并前必须补上）")
        else:
            errors.append(msg)
    for a in apps:
        pre, cards = split_cards(a["text"])
        if len(cards) < 1:
            errors.append(f"附录 {a['id']}：没有卡片内容")
        if pre.strip():
            warnings.append(f"附录 {a['id']}：第一张卡之前有正文，构建时会并入第一张卡")
        scan_syntax(a["text"], a["line0"], errors, warnings)
        errors.extend(table_errors(a["text"].split("\n"), a["line0"]))

    if args.strict:
        errors.extend(warnings)
        warnings = []

    report = {
        "md": str(md_path),
        "pages": len(pages),
        "max_page": mx,
        "appendices": len(apps),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    print(f"页面 {len(pages)} 页，附录 {len(apps)} 篇 → {'通过' if not errors else '未通过'}")
    for e in errors:
        print("  ✗ " + e)
    for w in warnings:
        print("  ⚠ " + w)
    if args.json:
        C.emit_json(report)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
