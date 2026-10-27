# -*- coding: utf-8 -*-
"""逐页抽取 PDF 文本，并标记疑似扫描页 / 文字顺序可疑页。

输出（默认在工作目录的 _extract/）：
  pNNN.txt        该页纯文本
  pNNN.blocks.txt （--layout blocks|both）按块坐标排序后的文本
  index.json      页数、字符数、图片数、scanned_pages、needs_vision_pages

用法：
  python extract_text.py --config courseware.json
  python extract_text.py --pdf deck.pdf --out-dir _extract
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C


def open_pdf(path: Path):
    try:
        import pymupdf  # noqa: F401
    except Exception:
        C.fail("未安装 PyMuPDF。请运行：python -m pip install pymupdf")
    import pymupdf

    if not path.is_file():
        C.fail(f"找不到 PDF：{path}")
    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:
        C.fail(f"无法打开 PDF：{path}\n{exc}")
    if doc.needs_pass:
        C.fail("PDF 已加密，需要密码，无法抽取。")
    return pymupdf, doc


def block_text(block) -> str:
    # block = (x0, y0, x1, y1, text, block_no, block_type)
    if len(block) < 5:
        return ""
    return (block[4] or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="逐页抽取 PDF 文本并标记扫描页")
    ap.add_argument("--config")
    ap.add_argument("--pdf")
    ap.add_argument("--out-dir")
    ap.add_argument("--pages", help="如 1-20,25；默认全部")
    ap.add_argument("--layout", choices=["raw", "blocks", "both"], default="raw")
    ap.add_argument("--min-chars", type=int, default=20, help="低于此字符数视为无文本层")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    cfg = None
    if args.config:
        cfg, base = C.load_config(args.config)
        pdf = Path(args.pdf).expanduser().resolve() if args.pdf else C.resolve(cfg, "source_pdf")
        out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (base / "_extract")
    else:
        if not args.pdf:
            C.fail("需要 --config 或 --pdf")
        pdf = Path(args.pdf).expanduser().resolve()
        if not args.out_dir:
            C.fail("未提供 --out-dir")
        out_dir = Path(args.out_dir).expanduser().resolve()

    if not pdf.is_file():
        C.fail(f"找不到 PDF：{pdf}")
    out_dir.mkdir(parents=True, exist_ok=True)

    pymupdf, doc = open_pdf(pdf)
    total = doc.page_count
    wanted = C.parse_page_spec(args.pages, total) if args.pages else list(range(1, total + 1))

    pages = []
    scanned, needs_vision = [], []
    for num in wanted:
        page = doc[num - 1]
        raw = page.get_text("text") or ""
        raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()

        # 块坐标总是算：即使不写 blocks.txt，也要用它判断文字层是否可靠
        blocks = []
        for b in sorted(page.get_text("blocks"), key=lambda b: (round(b[1]), round(b[0]))):
            t = block_text(b)
            if t:
                blocks.append(t)
        # 按块顺序拼出的文本，供文字层顺序错乱的页面参考
        blocks_text = "\n".join(blocks)

        n_chars = len(raw)
        n_img = len(page.get_images(full=True))
        is_scanned = n_chars < args.min_chars
        # 图片多、短文本块多 → 大概率是图上的标注，纯文本顺序不可靠，需要看渲染图
        vision = (not is_scanned) and (n_img >= 3 or (len(blocks) >= 25 and n_chars / max(1, len(blocks)) < 18))

        txt_path = out_dir / ("p%03d.txt" % num)
        if args.force or not txt_path.exists():
            C.write_text(txt_path, raw + "\n")
        if args.layout in ("blocks", "both"):
            C.write_text(out_dir / ("p%03d.blocks.txt" % num), blocks_text + "\n")

        first = next((ln.strip() for ln in raw.split("\n") if ln.strip()), "")
        pages.append({
            "page": num,
            "chars": n_chars,
            "images": n_img,
            "blocks": len(blocks),
            "width": round(page.rect.width, 1),
            "height": round(page.rect.height, 1),
            "scanned": is_scanned,
            "needs_vision": vision,
            "first_line": first[:120],
        })
        if is_scanned:
            scanned.append(num)
        if vision:
            needs_vision.append(num)

    index = {
        "source_pdf": str(pdf),
        "page_count": total,
        "extracted": len(wanted),
        "scanned_pages": scanned,
        "needs_vision_pages": needs_vision,
        "pages": pages,
    }
    C.write_text(out_dir / "index.json", json.dumps(index, ensure_ascii=False, indent=2) + "\n")

    msg = f"抽取 {len(wanted)}/{total} 页 → {out_dir}"
    print(msg)
    if scanned:
        C.warn(f"以下页面几乎没有文本层（疑似扫描/纯图片页）：{scanned}")
        print("  提示：这些页必须看渲染图转写，不能凭想象补文字。")
    if needs_vision:
        C.warn(f"以下页面图片/短文本块较多，文字层顺序可能错乱：{needs_vision}")
        print("  提示：优先看 pNNN.png 再翻译。")
    if args.json:
        C.emit_json(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
