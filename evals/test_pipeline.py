# -*- coding: utf-8 -*-
"""端到端自测：3 页样例（含 1 页扫描页）走完整流程，并覆盖主要失败模式。

用法：
  python test_pipeline.py            # 需要 Chrome/Edge（DOM、截图、PDF）
  python test_pipeline.py --no-browser
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
TMP = HERE / "_tmp" / "样例 测试 中文路径"
FAILURES: list[str] = []

SAMPLE = """### 第 1 页 · 逻辑门

**【课件中文版】**

**第 1 章　逻辑门**

**1.1 基本门电路**
与门（AND）、或门（OR）、非门（NOT）是三种基本逻辑门。
真值表（truth table）列出每一种输入组合及对应的输出。

**【注释】**

**这页在说什么**
这一页把“逻辑”落到三种最基本的电路元件上：与门、或门、非门。必须记住：再复杂的数字电路，也只是这三种门的组合。

**为什么 / 直觉**
与门像两个串联开关，两个都闭合灯才亮；或门像并联，任意一个闭合灯就亮；非门就是反着来。

**怎么用**
先判断题目要“同时满足”（与）还是“满足一个即可”（或），再选门。常见错误是把“或”理解成二选一。

---

### 第 2 页 · 多数表决函数

**【课件中文版】**

**1.3 例子：多数表决函数**

`F = A·B + B·C + A·C`

当至少两个输入为 1 时，输出为 1。

| A | B | C | F |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 0 | 1 | 1 | 1 |
| 1 | 1 | 1 | 1 |

**【注释】**

**这页在说什么**
这是第一个完整的逻辑函数例子：三输入多数表决，至少两人同意才通过。

**为什么 / 直觉**
三项分别对应 AB、BC、AC 同意，任一项成立就说明至少两人同意，所以三项之间用“或”。

**怎么用**
遇到“至少 k 个为 1”，先列满足条件的组合，再“与”成项、“或”成式；最后用真值表代回自检。

---

### 第 3 页 · 扫描页示例

**【课件中文版】**

（本页没有文本层，以下内容按渲染图转写。）

**Scanned page**
This page has no text layer.
Read the rendered PNG before translating.

**【注释】**

**这页在说什么**
这一页是整页图片，PDF 里提取不到文字。必须先看 `slides/p003.png`，照着图上真实可见的内容转写。

**为什么 / 直觉**
扫描页和图片型 PPT 很常见。文字层为空不代表没有内容，直接跳过会漏掉一整页。

**怎么用**
看渲染图 → 逐行抄写 → 再翻译和写注释。看不清就写“以讲义为准”，不要编造。

---

### 附录 A · 三种基本门速查

**【速查表】**

| 门 | 表达式 | 口诀 | 什么时候输出 1 |
|---|---|---|---|
| 与门 AND | `F = A·B` | 全 1 才 1 | 所有输入都是 1 |
| 或门 OR | `F = A + B` | 有 1 就 1 | 至少一个输入是 1 |
| 非门 NOT | `F = A′` | 反着来 | 输入是 0 |
"""


def run(name: str, args: list[str], expect: int = 0, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + args, cwd=str(cwd or TMP),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    ok = (p.returncode == expect)
    print(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else f"（退出码 {p.returncode}，期望 {expect}）"))
    if not ok:
        FAILURES.append(name)
        print("    stdout:", (p.stdout or "").strip()[-600:])
        print("    stderr:", (p.stderr or "").strip()[-600:])
    return p


def check(cond: bool, msg: str, failures: list[str]) -> None:
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures.append(msg)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    failures: list[str] = []
    FAILURES.clear()
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)

    fixture = HERE / "fixture.pdf"
    if not fixture.exists():
        run("生成 3 页 fixture", [str(HERE / "make_fixture.py")])
    if not fixture.exists():
        return 1

    py = sys.executable
    print("== 初始化 ==")
    run("scaffold", [str(SCRIPTS / "scaffold.py"), "--pdf", str(fixture),
                     "--workdir", str(TMP), "--title", "测试课件：逻辑门", "--dpi", "80"])
    cfg = TMP / "courseware.json"
    check(cfg.is_file(), "生成 courseware.json", failures)

    index = json.loads((TMP / "_extract" / "index.json").read_text(encoding="utf-8"))
    check(index["scanned_pages"] == [3], f"扫描页识别 = {index['scanned_pages']}", failures)
    slides = sorted((TMP / "网页版电子书" / "slides").glob("p*.png"))
    check(len(slides) == 3, f"渲染原图 {len(slides)}/3 张", failures)

    print("== 写作与合并 ==")
    (TMP / "_out" / "part01.md").write_text(SAMPLE, encoding="utf-8")
    run("分批校验（--allow-partial）", [str(SCRIPTS / "check_md.py"), "--config", str(cfg),
                                   "--md", str(TMP / "_out" / "part01.md"), "--allow-partial"])
    run("merge_parts", [str(SCRIPTS / "merge_parts.py"), "--config", str(cfg)])
    run("全量 check_md", [str(SCRIPTS / "check_md.py"), "--config", str(cfg)])
    md = TMP / "测试课件：逻辑门_中文翻译与注释.md"
    check(md.is_file(), "生成主 Markdown", failures)
    h1 = hashlib.md5(md.read_bytes()).hexdigest() if md.is_file() else ""
    run("merge_parts 第二次", [str(SCRIPTS / "merge_parts.py"), "--config", str(cfg)])
    h2 = hashlib.md5(md.read_bytes()).hexdigest() if md.is_file() else ""
    check(h1 == h2 and md.read_text(encoding="utf-8").count("AUTO-TOC:START") == 1,
          "重复合并幂等、目录不叠加", failures)
    text = md.read_text(encoding="utf-8")
    check(text.index("<!-- AUTO-TOC:START -->") < text.index("### 第 1 页"),
          "目录插在第 1 页之前", failures)

    print("== 构建与自检 ==")
    run("build_book", [str(SCRIPTS / "build_book.py"), "--config", str(cfg)])
    html = TMP / "网页版电子书" / "index.html"
    page = html.read_text(encoding="utf-8") if html.is_file() else ""
    check("__CSS__" not in page and "@@CSS@@" not in page, "CSS 占位符已替换", failures)
    check(len(re.findall(r'<section class="page"[^>]*data-kind="app"', page)) == 1,
          "附录标记存在", failures)
    if not args.no_browser:
        run("verify html/dom/layout", [str(SCRIPTS / "verify_book.py"), "--config", str(cfg),
                                       "--check-html", "--dom", "--layout"])
        run("make_pdf", [str(SCRIPTS / "make_pdf.py"), "--config", str(cfg)])
        run("verify pdf", [str(SCRIPTS / "verify_book.py"), "--config", str(cfg), "--pdf-check"])
        shot_cfg = json.loads(cfg.read_text(encoding="utf-8"))
        shot_cfg["verify"] = {"sample_pages": "1,3"}
        shot_path = TMP / "shot.json"
        shot_path.write_text(json.dumps(shot_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        run("verify shots（自定义抽样页）", [str(SCRIPTS / "verify_book.py"),
                                         "--config", str(shot_path), "--shots"])
        vdir = TMP / "网页版电子书" / "_verify"
        check((vdir / "desktop_p003.png").is_file(), "sample_pages 命中了第 3 页", failures)
        check(not (vdir / "desktop_p002.png").exists(), "sample_pages 未截第 2 页", failures)

    print("== 失败模式 ==")
    bad = TMP / "_bad.md"
    base = md.read_text(encoding="utf-8")
    bad.write_text(re.sub(r"(?ms)^### 第 2 页.*?(?=^### 第 3 页)", "", base), encoding="utf-8")
    run("缺页 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    run("缺页 + --allow-partial → 通过", [str(SCRIPTS / "check_md.py"), "--config", str(cfg),
                                     "--md", str(bad), "--allow-partial"], 0)
    bad.write_text(base.replace("### 第 2 页", "### 第 1 页", 1), encoding="utf-8")
    run("重复页码 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    bad.write_text(re.sub(r"(?ms)^### 附录 A.*$", "", base), encoding="utf-8")
    run("缺少附录 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    bad.write_text(base.replace(
        "### 附录 A · 三种基本门速查",
        "### 附录 A · 重复\n\n**【速查表】**\n\n重复。\n\n---\n\n### 附录 A · 三种基本门速查", 1),
        encoding="utf-8")
    run("附录编号重复 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    bad.write_text(base.replace("这一页把", "### 页内小标题\n\n这一页把", 1), encoding="utf-8")
    run("页内三级标题 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    bad_text = base.replace("这一页把",
                            "见 [链接](x.md) ![图](a.png) *斜体* <b>x</b> $a+b$ 这一页把", 1)
    bad.write_text(bad_text, encoding="utf-8")
    p = run("禁用语法 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)
    expect_line = bad_text[:bad_text.index("见 [链接]")].count("\n") + 1
    check(f"第 {expect_line} 行" in (p.stdout or ""), "报错行号是全文行号", failures)
    bad.write_text(base.replace("| 0 | 1 | 1 | 1 |", "| 0 | 1 | 1 |", 1), encoding="utf-8")
    run("表格列数不齐 → 报错", [str(SCRIPTS / "check_md.py"), "--config", str(cfg), "--md", str(bad)], 1)

    print("== 无原图模式 ==")
    nosl = TMP / "noslides"
    nosl.mkdir(exist_ok=True)
    c = json.loads(cfg.read_text(encoding="utf-8"))
    c["out_dir"] = str(nosl)
    c["md_file"] = str(md)          # 配置在子目录里，Markdown 用绝对路径
    (nosl / "courseware.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    run("build_book（无 slides）", [str(SCRIPTS / "build_book.py"), "--config", str(nosl / "courseware.json")])
    if not args.no_browser:
        run("verify（无 slides）", [str(SCRIPTS / "verify_book.py"),
                                    "--config", str(nosl / "courseware.json"),
                                    "--check-html", "--dom", "--layout"])
    nh = (nosl / "index.html").read_text(encoding="utf-8") if (nosl / "index.html").is_file() else ""
    check('<button id="btnImgs" hidden' in nh, "无原图时按钮隐藏", failures)

    print()
    failures = list(dict.fromkeys(FAILURES + failures))
    if failures:
        print(f"失败 {len(failures)} 项：")
        for f in failures:
            print("  - " + f)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
