# -*- coding: utf-8 -*-
"""生成 3 页测试 PDF：第 1、2 页有文本层，第 3 页只有图片（模拟扫描页）。

用法：
  python make_fixture.py [--out fixture.pdf]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("fixture.pdf")))
    args = ap.parse_args()

    try:
        import pymupdf
    except Exception:
        print("需要 PyMuPDF：python -m pip install pymupdf", file=sys.stderr)
        return 2

    doc = pymupdf.open()

    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((60, 90), "Chapter 1  Logic Gates", fontsize=26)
    p1.insert_text((60, 140), "1.1  Basic gates", fontsize=16)
    p1.insert_text((60, 175), "AND, OR and NOT are the three basic logic gates.", fontsize=12)
    p1.insert_text((60, 200), "A truth table lists every input combination and its output.", fontsize=12)
    p1.insert_text((60, 240), "1.2  Why it matters", fontsize=16)
    p1.insert_text((60, 275), "Every digital circuit can be built from these gates.", fontsize=12)

    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((60, 90), "1.3  Example: majority function", fontsize=22)
    p2.insert_text((60, 135), "F = A*B + B*C + A*C", fontsize=14)
    p2.insert_text((60, 170), "The output is 1 when at least two inputs are 1.", fontsize=12)
    p2.insert_text((60, 210), "A   B   C   |  F", fontsize=12)
    p2.insert_text((60, 230), "0   0   0   |  0", fontsize=12)
    p2.insert_text((60, 250), "0   1   1   |  1", fontsize=12)
    p2.insert_text((60, 270), "1   1   1   |  1", fontsize=12)
    p2.draw_rect(pymupdf.Rect(60, 300, 535, 430), color=(0.2, 0.3, 0.6), width=1.5)
    p2.insert_text((80, 350), "Karnaugh map goes here", fontsize=14, color=(0.2, 0.3, 0.6))

    # 第 3 页：先做一张“扫描图”，再整页贴图、不写任何文字
    tmp = pymupdf.open()
    tp = tmp.new_page(width=500, height=360)
    tp.insert_text((30, 50), "Scanned page", fontsize=22)
    tp.draw_rect(pymupdf.Rect(30, 80, 470, 330), color=(0.8, 0.2, 0.2), width=2)
    tp.insert_text((50, 130), "This page has no text layer.", fontsize=14)
    tp.insert_text((50, 165), "Read the rendered PNG before translating.", fontsize=14)
    pix = tp.get_pixmap(dpi=110)
    tmp.close()

    p3 = doc.new_page(width=595, height=842)
    p3.insert_image(pymupdf.Rect(40, 60, 555, 430), pixmap=pix)

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    doc.close()
    print(f"fixture: {out} (3 pages, page 3 is image-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
