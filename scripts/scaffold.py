# -*- coding: utf-8 -*-
"""为一个新课件建立工作目录、写 courseware.json，并完成文本抽取 + 页面渲染。

用法：
  python scaffold.py --pdf "课件.pdf" [--workdir DIR] [--title "第 1 章 …"] [--no-render]

生成：
  <workdir>/courseware.json
  <workdir>/_out/                 分批写作的 partNN.md
  <workdir>/_extract/pNNN.txt    逐页文本
  <workdir>/网页版电子书/slides/pNNN.png
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

HERE = Path(__file__).resolve().parent


def safe_name(s: str) -> str:
    # 过长的标题会把 Windows 路径顶到 260 字符上限，截断到 80
    return (re.sub(r'[\\/:*?"<>|]+', "_", s).strip().strip(".") or "课件")[:80]


def main() -> int:
    ap = argparse.ArgumentParser(description="初始化课件处理工作目录")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--workdir")
    ap.add_argument("--title")
    ap.add_argument("--out-name", default="网页版电子书")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.is_file():
        C.fail(f"找不到 PDF：{pdf}")
    work = Path(args.workdir).expanduser().resolve() if args.workdir else pdf.parent
    work.mkdir(parents=True, exist_ok=True)

    try:
        import pymupdf
    except Exception:
        C.fail("未安装 PyMuPDF。请运行：python -m pip install pymupdf")
    try:
        doc = pymupdf.open(str(pdf))
    except Exception as exc:
        C.fail(f"无法打开 PDF：{pdf}\n{exc}")
    if doc.needs_pass:
        C.fail("PDF 已加密，无法处理。")
    n_page = doc.page_count
    title = args.title or pdf.stem

    cfg_path = work / "courseware.json"
    if cfg_path.exists() and not args.force:
        C.fail(f"配置已存在：{cfg_path}\n如需重建，请加 --force（会先备份为 courseware.json.bak）。", 1)
    if cfg_path.exists():
        cfg_path.replace(cfg_path.with_suffix(".json.bak"))

    cfg = {
        "schema_version": 1,
        "title": title,
        "short_title": title,
        "subtitle": "中文翻译 + 逐页注释（面向零基础的大二同学）",
        "source_pdf": pdf.name if work == pdf.parent else str(pdf),
        "md_file": safe_name(title) + "_中文翻译与注释.md",
        "parts_dir": "_out",
        "out_dir": args.out_name,
        "dpi": args.dpi,
        "page_count": n_page,
        "sections": [],
        "auto_sections": True,
        "auto_section_size": 14,
        "appendix": True,
    }
    C.write_text(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    (work / "_out").mkdir(exist_ok=True)

    print(f"✓ 已建立配置：{cfg_path}")
    print(f"  PDF：{pdf}（{n_page} 页）")

    rc = subprocess.call([sys.executable, str(HERE / "extract_text.py"), "--config", str(cfg_path)])
    if rc != 0:
        return rc
    out_dir = work / args.out_name
    (out_dir / "slides").mkdir(parents=True, exist_ok=True)
    if not args.no_render:
        rc = subprocess.call([sys.executable, str(HERE / "render_pages.py"), "--config", str(cfg_path)])
        if rc != 0:
            return rc

    print("\n下一步：")
    print("  1) 看 _extract/index.json，确认 scanned_pages / needs_vision_pages")
    print("  2) 在 courseware.json 里填 sections（或留空自动分组）")
    print("  3) 分批把译文与注释写到 _out/part01.md、part02.md …")
    print(f'  4) python "{HERE / "merge_parts.py"}" --config "{cfg_path}"')
    print(f'  5) python "{HERE / "check_md.py"}" --config "{cfg_path}"')
    if args.json:
        C.emit_json({"config": str(cfg_path), "pdf": str(pdf), "page_count": n_page,
                     "workdir": str(work)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
