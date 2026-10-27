# 配置与命令行

一个课件 = 一个工作目录 = 一份 `courseware.json`。所有脚本都读同一份配置，
配置里的相对路径一律相对于**配置文件所在目录**解析，所以整个工作目录可以随便移动。

## 目录结构

```
<工作目录>/
  courseware.json              配置
  <title>_中文翻译与注释.md      合并后的主 Markdown
  _out/part01.md …             分批写作的源文件
  _extract/pNNN.txt            逐页抽取的文本
  _extract/index.json          页数 / 字符数 / 扫描页 / 需看图页
  网页版电子书/
    index.html                 单文件离线电子书
    slides/pNNN.png            逐页渲染的原图
    <title>（原课件图+译文+注释）.pdf
    使用说明.txt
    _verify/                   自检截图与 PDF 抽样图
```

除 `courseware.json` 外，其余名字都可在配置里改。

## 快速开始

```bash
python "<技能目录>/scripts/scaffold.py" \
  --pdf "课件.pdf" \
  --workdir "课件_学习包" \
  --title "第 1 章 数字逻辑基础"
```

`scaffold.py` 会：检查 PDF 可读 → 写 `courseware.json` → 建 `_out/` →
逐页抽取文本 → 逐页渲染 PNG。已有配置时默认拒绝覆盖；加 `--force`
会先把旧配置备份成 `courseware.json.bak`。

## 必填字段

| 字段 | 说明 |
|---|---|
| `schema_version` | 固定为 `1` |
| `title` | 完整标题，用于网页、PDF 文件名、报告 |
| `source_pdf` | 原课件 PDF；相对路径按配置目录解析 |
| `md_file` | 合并后的 Markdown 路径 |
| `out_dir` | 网页成品目录（默认 `网页版电子书`） |

缺任一字段会以退出码 1 停止。`scaffold.py` 会自动生成这五项。

## 顶层字段

| 字段 | 默认 | 作用 |
|---|---|---|
| `short_title` | 等于 `title` | 侧栏品牌名、窄屏标题 |
| `subtitle` | `中文翻译 + 逐页注释` | 侧栏副标题的一部分 |
| `parts_dir` | `_out` | 分批写作目录 |
| `part_glob` | `part*.md` | 分批文件匹配；按自然排序合并 |
| `slides_subdir` | `slides` | 原图子目录（相对 `out_dir`） |
| `pdf_out` | 自动 | 打印版路径；默认 `<out_dir>/<title>（原课件图+译文+注释）.pdf` |
| `dpi` | `110` | 幻灯片 PNG 的渲染 DPI；公式密集可设 150–180 |
| `page_count` | 自动探测 | 期望的 PDF 物理页数；不一致时 `build_book` 直接失败 |
| `sections` | `[]` | 侧栏分组；空则自动分组 |
| `auto_sections` | `true` | `sections` 为空时是否自动分组 |
| `auto_section_size` | `14` | 自动分组的目标大小（页） |
| `appendix` | `true` | 是否要求至少一篇附录（`check_md` 据此报错） |
| `labels` | 中文默认 | 界面与卡片标签，见下表 |

## labels（会真正生效的键）

| 键 | 默认 | 出现位置 |
|---|---|---|
| `translation` | `课件中文版` | 第一张卡的标签；`check_md` 校验它 |
| `notes` | `注释` | 第二张卡的标签；`check_md` 校验它 |
| `notes_suffix` | `写给零基础的同学` | 注释卡标题后缀 |
| `empty_page` | `（本页为纯标题页，课件无正文。）` | 译文卡为空时 |
| `empty_notes` | `（本页无注释。）` | 注释卡为空时 |
| `search_placeholder` | `搜索：页码 / 标题 / 关键词` | 搜索框 |
| `toc_overview` | `章节总览` | 侧栏导读组标题 |
| `overview_hint` | `导读` | 导读组右上角小字 |
| `landing_pages` | `第 {a} – {b} 页 · 共 {n} 页` | 导读卡片副标题 |
| `landing_appendix` | `附录 · 共 {n} 篇` | 附录导读卡片 |
| `prev` / `next` / `top` | `← 上一页` / `下一页 →` / `↑ 顶部` | 页内导航 |
| `slide_button` / `slide_button_open` | `原课件图` / `收起原图` | 单页原图按钮 |
| `notes_on` / `notes_off` | `隐藏注释` / `显示注释` | 注释开关（`_on` 是当前已显示时的文案） |
| `imgs_on` / `imgs_off` | `隐藏原图` / `显示原图` | 原图开关 |
| `theme_dark` / `theme_light` | `深色` / `浅色` | 主题开关 |
| `print` | `打印 / 存 PDF` | 打印按钮 |

附录卡片标签（`【速查表】`、`【用法速记】`、`【术语表】`…）由 Markdown 决定，
不需要在配置里声明；`check_md` 只要求附录至少有一张卡。

## html

| 字段 | 默认 | 作用 |
|---|---|---|
| `title` | `<title> · 中文翻译与逐页注释` | 浏览器标题 |
| `brand` | `short_title` | 侧栏顶部品牌名 |
| `brand_sub` | 自动（含页数与附录数） | 品牌下的小字 |
| `lang` | `zh-CN` | `<html lang>` |
| `open_groups` | `1` | 初始展开前几个侧栏分组 |
| `default_theme` | `light` | 首次打开的主题（`light` / `dark`） |
| `storage_key` | `book` | localStorage 前缀；多本书共用一个域名时改成不同的值 |
| `include_landing` | `true` | 是否显示“章节总览”导读卡片 |
| `footer_lines` | `[]` | 自定义页脚（数组，每项一行 Markdown 行内文本）；空则自动生成 |

## pdf

| 字段 | 默认 | 作用 |
|---|---|---|
| `chrome` | 自动探测 | Chrome / Edge 可执行文件 |
| `page_size` | `A4` | 注入 CSS `@page{size:…}`，并用于 PDF 校验；支持 A4 / A3 / LETTER / LEGAL |
| `margin` | `12mm 11mm` | 注入 `@page{margin:…}` |
| `timeout_sec` | `180` | 无头打印超时；图多时加大 |

## verify

| 字段 | 默认 | 作用 |
|---|---|---|
| `chrome` | 自动探测 | 覆盖 `pdf.chrome`，仅自检用 |
| `probe_keyword` | 自动取第一页标题前 6 字 | DOM 搜索测试关键词；自动值命中 0 页时手动指定 |
| `sample_pages` | `first,middle,last` | 截图页；可写 `first,20,last`（数字是 `#pN` 的 N，不是序号） |
| `shot_width` / `shot_height` | `1400` / `1200` | DOM 布局探针的桌面视口 |
| `min_pdf_pages` | 内容 section 数 | PDF 至少多少页；不设时用页数 + 附录数 |

## sections：手工分组

`sections` 为空时自动分组。手工分组示例：

```json
"sections": [
  {"name": "第 1 部分 逻辑代数", "short": "逻辑代数", "from": 1, "to": 18,
   "desc": "基本运算、公式、定理"},
  {"name": "第 2 部分 组合逻辑", "short": "组合逻辑", "from": 19, "to": 55,
   "desc": "分析、设计、卡诺图"},
  {"name": "附录", "short": "附录", "from": 83, "to": 84, "kind": "appendix"}
]
```

规则：

- 范围是**连续编号**，不是 PDF 页码：第 1 页 = 1，附录第一篇 = 页数 + 1。
  上例假设正文 82 页。
- `from`/`to` 必须落在 `1..页数+附录数`；越界、`from > to`、范围重叠都会报错（退出码 1）。
- `kind` 可省略：`from > 页数` 自动视为附录。
- 有缺口会自动补组（用自动分组规则），不会丢页。
- 附录没有被任何组覆盖时，会自动补一个“附录”组。

## 自动分组算法

`sections` 为空且 `auto_sections=true` 时：

1. `k = ceil(页数 / auto_section_size)`，例如 82 页、每组 14 页 → `k=6`。
2. 把 82 页均衡切成 6 组：`base=13, rem=4` → 前 4 组 14 页，后 2 组 13 页。
   这样不会出现“最后一组只有 1 页”。
3. 组名 `第 a–b 页`；描述取首末页标题（`从“…”到“…”`）。
4. 附录单独成组，描述取各附录标题。

想按课件真实的章来分组，就填 `sections`；只想快速出成品，留空即可。

## 附录编号与深链接

- 合并时附录被重新编号为 `页数 + 1`、`页数 + 2`…，所以 `#p83` 一定指向第一篇附录。
- 显示文字仍是“附录 A”“附录 B”，不会显示成“第 83 页”。
- 附录**永不配课件原图**，即使 `slides/` 里残留了对应 PNG。

## 脚本与参数

所有脚本都在 `<技能目录>/scripts/`。公共约定：

- 配置里的相对路径按 `courseware.json` 所在目录解析；CLI 里传的路径按当前目录解析。
- 退出码：`0` 成功（可有警告）；`1` 内容/校验失败；`2` 环境/输入错误
  （找不到 PDF/配置、缺依赖、找不到浏览器、JSON 非法等）。
- `--json` 会在人类可读输出之后追加一段 JSON，便于程序读取。

### scaffold.py

```bash
python scaffold.py --pdf "课件.pdf" [--workdir DIR] [--title "标题"] \
  [--out-name 网页版电子书] [--dpi 110] [--no-render] [--force]
```

`--no-render` 只抽取文本，不渲染 PNG（先快速看页数/扫描页时用）。

### extract_text.py

```bash
python extract_text.py --config courseware.json [--pages 1-20,25] \
  [--layout raw|blocks|both] [--min-chars 20] [--force]
```

- 文本写在 `_extract/pNNN.txt`；默认不覆盖已有文件，`--force` 才重写。
- `index.json` 里：
  - `scanned_pages`：字符数 < `--min-chars`，几乎没有文本层；
  - `needs_vision_pages`：图片 ≥ 3 张，或短文本块 ≥ 25 且平均每块 < 18 字符，
    文字顺序可能不可靠。
- 这两个列表只是**提示**：所有页都应以渲染图为最终依据，标注页尤其不能凭文本想象。

### render_pages.py

```bash
python render_pages.py --config courseware.json [--pages 1-20] [--dpi 150] [--force]
```

默认输出到 `<out_dir>/<slides_subdir>/pNNN.png`，已存在的图默认跳过；
`--force` 全部重渲染。PDF 里公式/小字看不清时，用更高 DPI 只重渲染相关页。

### check_md.py

```bash
python check_md.py --config courseware.json
python check_md.py --config courseware.json --md _out/part01.md --allow-partial
python check_md.py --config courseware.json --strict
```

- 分批写作时用 `--allow-partial`：缺页、缺附录降级为警告。
- 最终合并后必须做一次**不带** `--allow-partial` 的全量校验。
- `--strict` 把警告（斜体、嵌套列表、注释过短、卡前正文等）升级为错误。
- `--expected-pages` 可临时覆盖配置里的 `page_count`。
- 报错行号是**全文行号**，可直接跳到主 Markdown 的对应行。

### merge_parts.py

```bash
python merge_parts.py --config courseware.json [--allow-partial] [--no-toc]
```

- 自然排序读取 `part*.md`，去掉每个文件末尾的 `---`，用 `---` 重连。
- 目录用 `<!-- AUTO-TOC:START/END -->` 包住，**替换式**插入；重复运行不会叠加。
- 目录固定插在第一个 `### 第 1 页` 之前，不会塞进第 1 页的注释卡。
- 合并时校验页码重复/超出页数；缺页默认报错，`--allow-partial` 只警告。
- `--no-toc` 不插目录（一般不用）。

### build_book.py

```bash
python build_book.py --config courseware.json [--md 主.md] [--out-dir 输出目录]
```

- 唯一必需参数是 `--config`；`--md`/`--out-dir` 可临时覆盖配置。
- Markdown 页数必须等于 `page_count`，否则退出码 1。PDF 多一页封面也算页数，
  所以 `page_count` 一定要用 PDF 物理页数。
- 输出 `<out_dir>/index.html`，并把 `book.css` / `book.js` 内联进去，得到单文件网页。
- 图片按 `slides/pNNN.png` 是否存在决定是否插入；缺图不会报错，`verify` 会提示。

### make_pdf.py

```bash
python make_pdf.py --config courseware.json [--chrome 路径] [--timeout 300] [--no-imgs]
```

- 默认**包含原课件图**：复制一份临时 HTML，把 `loading="lazy"` 改为 `loading="eager"`，
  用 `?imgs=1&notes=1` 打开后打印。这样无头浏览器不会漏掉图片。
- `--no-imgs` 只打印译文与注释（页数少、文件小）。
- 用 `Path.as_uri()` 处理中文和空格路径。
- 输出后自动用 PyMuPDF 校验页数和纸张尺寸；尺寸不符会给警告。
- 找不到 Chrome/Edge 时可用 `--chrome`，或设环境变量 `CHROME` / `CHROME_PATH`。

### verify_book.py

```bash
python verify_book.py --config courseware.json                # 结构 + DOM + 布局
python verify_book.py --config courseware.json --all          # 再加截图 + PDF
python verify_book.py --config courseware.json --shots --pdf-check
```

| 参数 | 检查内容 |
|---|---|
| `--check-html` | section 数、附录数、注释卡数、目录项、`#pN` 目标、图片文件、占位符残留 |
| `--dom` | 无头浏览器加载后：JS 报错、搜索命中/乱词清零/清空恢复、注释开关、原图开关、方向键、`/` 聚焦 |
| `--layout` | 桌面 1400px 与移动 430px：横向溢出、元素超出视口、侧栏与正文重叠、移动菜单 |
| `--shots` | `_verify/desktop_pNNN.png`、`_verify/mobile_pNNN.png` |
| `--pdf-check` | PDF 页数、A4 尺寸、抽样页文字、`_verify/pdf_pNNN.png` |

不给任何检查参数时，默认做 `--check-html --dom --layout`。移动端 430px 是通过
iframe 包装模拟的（Windows 无头 Chrome 的最小窗口宽度约 512px），因此移动截图的
真实 CSS 视口是 430px。

## 环境变量

| 变量 | 作用 |
|---|---|
| `CHROME` / `CHROME_PATH` | 显式指定浏览器可执行文件 |

## 一次完整流程

```bash
SKILL="$HOME/.claude/skills/courseware-cn-annotator"
cd "课件_学习包"

python "$SKILL/scripts/scaffold.py" --pdf "../课件.pdf" --workdir . --title "第 1 章 …"
# …分批写 _out/part01.md 等…

python "$SKILL/scripts/check_md.py" --config courseware.json --md _out/part01.md --allow-partial
python "$SKILL/scripts/merge_parts.py" --config courseware.json
python "$SKILL/scripts/check_md.py" --config courseware.json
python "$SKILL/scripts/build_book.py" --config courseware.json
python "$SKILL/scripts/make_pdf.py" --config courseware.json
python "$SKILL/scripts/verify_book.py" --config courseware.json --all
```
