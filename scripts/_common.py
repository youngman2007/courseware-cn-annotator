# -*- coding: utf-8 -*-
"""courseware-cn-annotator 的公共工具：配置、路径、Chrome、分组、输出约定。

所有脚本都从这里取配置和路径，避免在 Windows / 中文路径 / 相对路径上各写一套。
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1

DEFAULT_LABELS = {
    "translation": "课件中文版",
    "notes": "注释",
    "notes_suffix": "写给零基础的同学",
    "empty_page": "（本页为纯标题页，课件无正文。）",
    "empty_notes": "（本页无注释。）",
    "search_placeholder": "搜索：页码 / 标题 / 关键词",
    "toc_overview": "章节总览",
    "overview_hint": "导读",
    "landing_pages": "第 {a} – {b} 页 · 共 {n} 页",
    "landing_appendix": "附录 · 共 {n} 篇",
    "prev": "← 上一页",
    "next": "下一页 →",
    "top": "↑ 顶部",
    "slide_button": "原课件图",
    "slide_button_open": "收起原图",
    "notes_on": "隐藏注释",
    "notes_off": "显示注释",
    "imgs_on": "隐藏原图",
    "imgs_off": "显示原图",
    "theme_dark": "深色",
    "theme_light": "浅色",
    "print": "打印 / 存 PDF",
}

DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "short_title": None,
    "subtitle": "中文翻译 + 逐页注释",
    "parts_dir": "_out",
    "part_glob": "part*.md",
    "out_dir": "网页版电子书",
    "slides_subdir": "slides",
    "pdf_out": None,
    "dpi": 110,
    "page_count": None,
    "sections": [],
    "auto_sections": True,
    "auto_section_size": 14,
    "appendix": True,
    "labels": {},
    "html": {
        "title": None,
        "brand": None,
        "brand_sub": None,
        "lang": "zh-CN",
        "open_groups": 1,
        "default_theme": "light",
        "storage_key": "book",
        "include_landing": True,
        "footer_lines": [],
    },
    "pdf": {
        "chrome": None,
        "page_size": "A4",
        "margin": "12mm 11mm",
        "timeout_sec": 180,
    },
    "verify": {
        "chrome": None,
        "probe_keyword": None,
        "sample_pages": "first,middle,last",
        "shot_width": 1400,
        "shot_height": 1200,
        "min_pdf_pages": None,
    },
}


def setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def fail(msg: str, code: int = 2) -> "NoReturn":
    print("✗ " + msg, file=sys.stderr)
    raise SystemExit(code)


def warn(msg: str) -> None:
    print("⚠ " + msg, file=sys.stderr)


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike) -> tuple[dict, Path]:
    """读取 courseware.json，补默认值，返回 (cfg, config_dir)。"""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        fail(f"找不到配置文件：{p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        fail(f"配置文件不是合法 JSON：{p}\n{exc}")
    if not isinstance(raw, dict):
        fail("配置文件顶层必须是 JSON 对象")
    ver = raw.get("schema_version", SCHEMA_VERSION)
    if ver != SCHEMA_VERSION:
        fail(f"不支持的 schema_version={ver}（本技能支持 {SCHEMA_VERSION}）")
    cfg = deep_merge(DEFAULTS, raw)
    cfg["labels"] = deep_merge(DEFAULT_LABELS, raw.get("labels") or {})
    for key in ("title", "source_pdf", "md_file", "out_dir"):
        if not cfg.get(key):
            fail(f"配置缺少必填字段：{key}", 1)
    cfg["_config_path"] = str(p)
    cfg["_config_dir"] = str(p.parent)
    return cfg, p.parent


def resolve(cfg: dict, key: str) -> Path:
    """把配置里的相对路径解析成绝对路径（相对于 courseware.json 所在目录）。"""
    value = cfg.get(key)
    if value is None or value == "":
        return Path("")
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = Path(cfg["_config_dir"]) / p
    return p.resolve()


def out_path(cfg: dict, key: str) -> Path:
    """out_dir 下的子路径。"""
    p = Path(cfg.get(key) or "")
    if p.is_absolute():
        return p
    return (resolve(cfg, "out_dir") / p).resolve()


def pdf_output(cfg: dict) -> Path:
    if cfg.get("pdf_out"):
        return out_path(cfg, "pdf_out")
    title = (re.sub(r'[\\/:*?"<>|]+', "_", cfg["title"]).strip() or "课件")[:80]
    return resolve(cfg, "out_dir") / f"{title}（原课件图+译文+注释）.pdf"


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def page_png(slides_dir: Path, num: int) -> Path:
    return slides_dir / ("p%03d.png" % num)


def detect_chrome(explicit: str | None = None) -> str | None:
    """按 显式参数 → 环境变量 → 常见安装位置 → PATH 的顺序找 Chrome/Edge。"""
    if explicit:
        p = Path(explicit).expanduser()
        return str(p) if p.is_file() else None
    env = os.environ.get("CHROME") or os.environ.get("CHROME_PATH")
    if env and Path(env).is_file():
        return env
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def parse_page_spec(spec: str, total: int) -> list[int]:
    """'1-5,8,10-' → [1..5,8,10..total]"""
    out: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else total
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    return [n for n in dict.fromkeys(out) if 1 <= n <= total]


def balanced_groups(n: int, size: int) -> list[tuple[int, int]]:
    """把 1..n 均衡切成若干组，避免出现只有 1 页的尾巴。"""
    if n <= 0:
        return []
    size = max(1, int(size or 14))
    k = max(1, math.ceil(n / size))
    base, rem = divmod(n, k)
    groups, start = [], 1
    for i in range(k):
        length = base + (1 if i < rem else 0)
        groups.append((start, start + length - 1))
        start += length
    return groups


def _group(name, short, a, b, desc, kind):
    return {"name": name, "short": short, "from": a, "to": b, "desc": desc, "kind": kind}


def resolve_sections(cfg: dict, page_titles: dict[int, str], n_page: int, n_app: int) -> list[dict]:
    """把配置里的 sections（可为空）变成覆盖 1..n_page+n_app 的完整分组列表。"""
    units = n_page + n_app
    raw = cfg.get("sections") or []
    groups: list[dict] = []

    if raw:
        for item in raw:
            if not isinstance(item, dict):
                fail("sections 里的每一项都必须是对象", 1)
            a = int(item.get("from", 0) or 0)
            b = item.get("to")
            b = units if b is None else int(b)
            if a < 1 or b < a or b > units:
                fail(f"分组范围越界：{item}（有效范围 1..{units}）", 1)
            kind = item.get("kind") or ("appendix" if a > n_page else "pages")
            name = item.get("name") or (f"第 {a}–{b} 页")
            groups.append(_group(name, item.get("short") or name, a, b, item.get("desc") or "", kind))
        groups.sort(key=lambda g: g["from"])
        for prev, cur in zip(groups, groups[1:]):
            if cur["from"] <= prev["to"]:
                fail(f"分组范围重叠：{prev['name']} 与 {cur['name']}", 1)
        # 补齐缺口
        filled, cursor = [], 1
        for g in groups:
            if g["from"] > cursor:
                filled.extend(_auto_groups(cfg, page_titles, cursor, g["from"] - 1, n_page))
            filled.append(g)
            cursor = g["to"] + 1
        if cursor <= units:
            filled.extend(_auto_groups(cfg, page_titles, cursor, units, n_page))
        groups = filled
    elif cfg.get("auto_sections", True):
        groups = _auto_groups(cfg, page_titles, 1, n_page, n_page) if n_page else []
    else:
        fail("sections 为空且 auto_sections=false，无法确定分组", 1)

    # 附录组兜底：有附录但没有覆盖附录范围的组时补一个
    covered_app = any(g["to"] > n_page for g in groups)
    if n_app and not covered_app:
        titles = "；".join(page_titles.get(n_page + 1 + i, "") for i in range(n_app))
        groups.append(_group("附录", "附录", n_page + 1, units, titles, "appendix"))
    return groups


def _auto_groups(cfg, page_titles, start, end, n_page) -> list[dict]:
    """为 [start, end] 生成自动分组；跨页区与附录区分别处理。"""
    out: list[dict] = []
    if start > end:
        return out
    page_end = min(end, n_page)
    if start <= page_end:
        for a, b in balanced_groups(page_end - start + 1, cfg.get("auto_section_size", 14)):
            a2, b2 = start + a - 1, start + b - 1
            name = f"第 {a2}–{b2} 页" if a2 != b2 else f"第 {a2} 页"
            t1 = page_titles.get(a2, "")
            t2 = page_titles.get(b2, "")
            desc = f"从“{t1}”到“{t2}”" if t1 and t2 and t1 != t2 else (t1 or t2)
            out.append(_group(name, name, a2, b2, desc[:80], "pages"))
    if end > n_page:
        a, b = max(start, n_page + 1), end
        name = "附录" if a == n_page + 1 else f"附录 {a - n_page}–{b - n_page}"
        desc = "；".join(page_titles.get(i, "") for i in range(a, b + 1))
        out.append(_group(name, "附录", a, b, desc[:120], "appendix"))
    return out


def read_text(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        fail(f"文件不是 UTF-8 编码：{path}\n请先转成 UTF-8（无 BOM 或有 BOM 均可）。\n{exc}")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def emit_json(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# 导入即统一切到 UTF-8：这样 --help 和 argparse 报错也不会在管道里变成乱码
setup_stdout()
