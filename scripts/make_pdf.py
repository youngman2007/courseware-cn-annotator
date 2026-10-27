# -*- coding: utf-8 -*-
"""用无头 Chrome / Edge 把电子书打印成 A4 PDF，并校验页数与纸张尺寸。

用法：
  python make_pdf.py --config courseware.json
  python make_pdf.py --config courseware.json --chrome "C:/.../chrome.exe"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

PAGE_SIZES_PT = {
    "A4": (595.28, 841.89),
    "A3": (841.89, 1190.55),
    "LETTER": (612.0, 792.0),
    "LEGAL": (612.0, 1008.0),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="电子书 HTML → A4 PDF")
    ap.add_argument("--config")
    ap.add_argument("--html")
    ap.add_argument("--out")
    ap.add_argument("--chrome")
    ap.add_argument("--timeout", type=int)
    ap.add_argument("--no-imgs", action="store_true", help="不打印原课件图，只打印译文与注释")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    C.setup_stdout()
    if args.config:
        cfg, base = C.load_config(args.config)
        html_path = Path(args.html).expanduser().resolve() if args.html else C.resolve(cfg, "out_dir") / "index.html"
        out = Path(args.out).expanduser().resolve() if args.out else C.pdf_output(cfg)
        chrome = C.detect_chrome(args.chrome or cfg["pdf"].get("chrome"))
        timeout = args.timeout or int(cfg["pdf"].get("timeout_sec") or 180)
        page_size = str(cfg["pdf"].get("page_size") or "A4").upper()
    else:
        if not args.html or not args.out:
            C.fail("需要 --config，或同时提供 --html 与 --out")
        html_path = Path(args.html).expanduser().resolve()
        out = Path(args.out).expanduser().resolve()
        chrome = C.detect_chrome(args.chrome)
        timeout = args.timeout or 180
        page_size = "A4"

    if not html_path.is_file():
        C.fail(f"找不到网页：{html_path}")
    if not chrome:
        C.fail("找不到 Chrome 或 Edge。请安装，或用 --chrome 指定可执行文件路径。")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    # 打印时默认显示原课件图；lazy 图片在无头打印里可能不加载，复制一份改成 eager
    target = html_path
    tmp_html = None
    query = ""
    if not args.no_imgs:
        doc_src = C.read_text(html_path).replace('loading="lazy"', 'loading="eager"')
        tmp_html = html_path.with_name("_print_tmp.html")
        C.write_text(tmp_html, doc_src)
        target = tmp_html
        query = "?imgs=1&notes=1"

    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        f"--print-to-pdf={out}",
        target.as_uri() + query,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        C.fail(f"Chrome 打印超时（>{timeout}s）。可加大 --timeout 或减少图片体积。")
    finally:
        if tmp_html and tmp_html.exists():
            tmp_html.unlink()
    if not out.is_file() or out.stat().st_size < 1024:
        tail = (proc.stderr or b"").decode("utf-8", "replace")[-800:]
        C.fail(f"Chrome 没有生成有效 PDF（退出码 {proc.returncode}）。\n{tail}")

    info = {"pdf": str(out), "bytes": out.stat().st_size, "seconds": round(time.time() - t0, 1)}
    try:
        import pymupdf
        doc = pymupdf.open(str(out))
        info["pages"] = doc.page_count
        w, h = doc[0].rect.width, doc[0].rect.height
        info["size_pt"] = [round(w, 1), round(h, 1)]
        want = PAGE_SIZES_PT.get(page_size)
        if want:
            ok = abs(w - want[0]) <= 3 and abs(h - want[1]) <= 3
            info["page_size_ok"] = ok
            if not ok:
                C.warn(f"首页尺寸 {w:.0f}×{h:.0f} pt 与 {page_size} 不符，请检查 @page 设置。")
        doc.close()
    except Exception as exc:
        C.warn(f"PyMuPDF 校验失败：{exc}")

    print(f"✓ PDF：{out}（{info['bytes'] / 1024 / 1024:.1f} MB，{info.get('pages', '?')} 页，"
          f"{info['seconds']}s）")
    if args.json:
        C.emit_json(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
