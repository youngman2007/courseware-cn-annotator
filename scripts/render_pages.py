# -*- coding: utf-8 -*-
"""把 PDF 逐页渲染成 PNG（默认 110 dpi，命名 p001.png …）。

用法：
  python render_pages.py --config courseware.json
  python render_pages.py --config courseware.json --dpi 160 --out-dir _review --pages 12-18
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C


def main() -> int:
    ap = argparse.ArgumentParser(description="逐页渲染 PDF 为 PNG")
    ap.add_argument("--config")
    ap.add_argument("--pdf")
    ap.add_argument("--out-dir")
    ap.add_argument("--dpi", type=int)
    ap.add_argument("--pages", help="如 1-20,25；默认全部")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    if args.config:
        cfg, base = C.load_config(args.config)
        pdf = Path(args.pdf).expanduser().resolve() if args.pdf else C.resolve(cfg, "source_pdf")
        out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else C.out_path(cfg, "slides_subdir")
        dpi = args.dpi or int(cfg.get("dpi") or 110)
    else:
        if not args.pdf or not args.out_dir:
            C.fail("需要 --config，或同时提供 --pdf 与 --out-dir")
        pdf = Path(args.pdf).expanduser().resolve()
        out_dir = Path(args.out_dir).expanduser().resolve()
        dpi = args.dpi or 110

    try:
        import pymupdf
    except Exception:
        C.fail("未安装 PyMuPDF。请运行：python -m pip install pymupdf")
    if not pdf.is_file():
        C.fail(f"找不到 PDF：{pdf}")
    try:
        doc = pymupdf.open(str(pdf))
    except Exception as exc:
        C.fail(f"无法打开 PDF：{pdf}\n{exc}")
    if doc.needs_pass:
        C.fail("PDF 已加密，无法渲染。")

    out_dir.mkdir(parents=True, exist_ok=True)
    total = doc.page_count
    wanted = C.parse_page_spec(args.pages, total) if args.pages else list(range(1, total + 1))

    made, skipped = [], []
    for num in wanted:
        dest = C.page_png(out_dir, num)
        if dest.exists() and not args.force:
            skipped.append(num)
            continue
        page = doc[num - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(str(dest))
        made.append({"page": num, "file": str(dest), "width": pix.width, "height": pix.height})

    print(f"渲染完成：新生成 {len(made)} 张，跳过 {len(skipped)} 张，dpi={dpi} → {out_dir}")
    if args.json:
        C.emit_json({"out_dir": str(out_dir), "dpi": dpi, "rendered": made, "skipped": skipped})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
