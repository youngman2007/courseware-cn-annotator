---
name: courseware-cn-annotator
description: 当用户说“做成学习包”（例如“把这份课件做成学习包”）时，使用本技能。把课件、讲义或课堂 PPT 的 PDF 一次性做成中文学习包：逐页中文翻译、面向零基础读者的三问式逐页注释（这页在说什么、为什么、怎么用）、可直接编辑的 Markdown 源稿、离线单文件 HTML 电子书（分组目录、全文搜索、注释与原图开关、深色主题、键盘翻页、深链）、A4 打印 PDF、使用说明，以及一到两篇学科速查附录。用户提供课件 PDF 并提到翻译、逐页讲解、注释版、电子书、可打印讲义、复习资料、速查表等任一需求时，也使用本技能，即使没有明确说“技能”。默认一次产出全套，用户明确只要其中某几项时才裁剪。
license: MIT
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
compatibility: 需要 Python 3.10+ 与 PyMuPDF；打印 PDF、DOM 自检和截图需要 Chrome 或 Edge；Pillow 仅用于裁剪移动端截图，可缺省。
---

# 课件中文注解学习包

把一份课件 PDF 变成学生能自学的完整资料：**逐页翻译 + 逐页注释 + 离线网页 + 打印版 + 速查附录**。
流程是固定的，质量取决于两件事：**有没有看图**、**注释有没有说清为什么和怎么用**。

## 成品

默认一次产出五件套（用户明确只要其中几项时才裁剪）：

```
<工作目录>/
  courseware.json                 配置（脚本唯一入口）
  <title>_中文翻译与注释.md        主 Markdown（可编辑源稿）
  _out/part01.md …                分批写作源文件
  _extract/pNNN.txt, index.json   逐页文本与扫描页标记
  网页版电子书/
    index.html                    离线单文件网页
    slides/pNNN.png               逐页原图
    <title>（原课件图+译文+注释）.pdf
    使用说明.txt
    _verify/                      自检截图与 PDF 抽样图
```

附录默认 1–2 篇：**A 速查表**（公式/规则/术语），**B 用法速记**（解题步骤/答题模板/决策流程）。
没有公式的学科，A 改成术语表 + 时间线/框架，B 改成答题模板或案例分析步骤。

## 开工前

```bash
SKILL="$HOME/.claude/skills/courseware-cn-annotator"
python -c "import pymupdf; print('pymupdf ok')"
```

- **输入必须是 PDF。** 只有 PPTX 时，先让用户用 PowerPoint“另存为 PDF”，或用
  `soffice --headless --convert-to pdf 课件.pptx` 转换，再处理；不要直接解析 PPTX。
- 先确认页数、是否加密、前几页有没有文本层：

```bash
python - "$PDF" <<'PY'
import sys, pymupdf
d = pymupdf.open(sys.argv[1])
print("pages:", d.page_count, "encrypted:", bool(d.needs_pass))
for i in range(min(5, d.page_count)):
    print(i + 1, len(d[i].get_text("text").strip()))
PY
```

- 加密且无密码：停下，请用户提供无密码版本。
- 前几页字符数接近 0：大概率是扫描版；仍可做，但必须逐页看渲染图转写。
- **绝不凭文字层想象图上的标注。** 看不清就写“以讲义为准”，并在报告中说明。

## 主工作流

### 1. 建工作目录

工作目录放在 PDF 旁边，单独一层，避免污染原文件夹：

```bash
PDF="/path/to/课件.pdf"
WORK="/path/to/课件_学习包"
python "$SKILL/scripts/scaffold.py" --pdf "$PDF" --workdir "$WORK" \
  --title "第 1 章 数字逻辑基础"
```

`scaffold.py` 会写配置、抽取逐页文本、渲染逐页 PNG。已有配置时默认拒绝覆盖；
确需重建加 `--force`（旧配置备份为 `courseware.json.bak`）。

完成后先看：

```bash
cat "$WORK/_extract/index.json"
```

重点字段：

- `scanned_pages`：几乎没有文本层，必须看图；
- `needs_vision_pages`：图片/短文本块多，文字顺序可能错乱；
- `pages[].first_line`：每页首行，用来定章节分组。

公式密集、字号小的课件，把 `dpi` 调到 150–180 再重渲染：

```bash
python "$SKILL/scripts/render_pages.py" --config "$WORK/courseware.json" --dpi 150
```

### 2. 配置

编辑 `courseware.json`。至少确认：

- `title` / `short_title`：完整标题、侧栏品牌名；
- `subtitle`：例如“中文翻译 + 逐页注释（面向零基础的大二同学）”；
- `page_count`：**PDF 物理页数**，必须完全一致；
- `sections`：有空就填，没有就留空自动分组；
- `verify.probe_keyword`：正文里一定存在的一个词，用于搜索自检（默认取第一页标题前 6 字，
  可能带标点导致 0 命中）；
- `html.storage_key`：多本书共用一个浏览器时改成不同值，避免记忆串台。

按真实章节分组更利于阅读。范围是**连续编号**（第 1 页 = 1，附录 = 页数 + 1）：

```json
"sections": [
  {"name": "第 1 部分 逻辑代数", "short": "逻辑代数", "from": 1, "to": 18,
   "desc": "基本运算、公式、定理"},
  {"name": "第 2 部分 组合逻辑", "short": "组合逻辑", "from": 19, "to": 55,
   "desc": "分析、设计、卡诺图"},
  {"name": "附录", "short": "附录", "from": 83, "to": 84, "kind": "appendix"}
]
```

不确定章节边界就留空：自动分组会均衡切分（默认每组约 14 页，不留 1 页尾巴），
附录单独成组。详细字段见 `references/config-and-cli.md`。

### 3. 读原稿、建术语表

**写作前必须先看材料，不能只看抽取文本就翻译。** 每批开始前：

1. 读该批的 `_extract/pNNN.txt`；
2. 用 Read 打开对应的 `slides/pNNN.png` 看实际排版；扫描页只能靠图；
3. 读上一批最后一页的注释，保持术语和记号连续。

在工作目录根目录建 `术语表.md`（**不要放进 `_out/`**，否则会被 `part*.md` 匹配合并）：

```markdown
| 英文/缩写 | 中文 | 首次出现 | 备注 |
|---|---|---|---|
| Karnaugh map (K-map) | 卡诺图 | 第 24 页 | 不译成“卡诺映射” |
| implicant | 蕴含项 | 第 26 页 | 与 prime implicant 区分 |
```

新术语先登记再使用。变量名、符号、单位、数字一律原样保留。

### 4. 分批写作

每批 **8–12 页**，按章节边界切。文件命名 `_out/part01.md`、`part02.md`…，自然排序。
每页严格按契约写：

```markdown
### 第 12 页 · 卡诺图的圈组规则

**【课件中文版】**

（译文：正文、图注、表头、脚注都要译；公式用行内代码）

**【注释】**

**这页在说什么**
2–4 句，点出唯一必须记住的事。

**为什么 / 直觉**
推导、类比、适用条件、与上一页的联系。

**怎么用**
编号步骤 + 3–6 行小例子 + 常见错误 + 自检方法。

---
```

硬性要求：

- 页码从 1 连续，不重不漏；每页两张卡，顺序固定；
- 标签 `**【课件中文版】**`、`**【注释】**` 必须**独占一行、行首无空格**；
- 禁用链接、图片、斜体、原始 HTML、`$...$`、删除线、表格里的 `|`；
- 页面内小标题用 `####`，不要用 `###`（会被当成新页，后半页丢失）；
- 普通页注释 150–400 字；公式/图密集页 400–800 字；封面/过渡页 50–150 字，不灌水；
- 每个新公式至少做一种核验（代值/真值表/量纲/极限/重推）；发现笔误标
  `⚠️ 课件笔误：原文 …，应为 …。理由：…`，没把握就写“建议对照教材”。

完整规范见 `references/annotation-style.md`；语法细节见 `references/md-contract.md`。

每批写完立刻校验该批：

```bash
python "$SKILL/scripts/check_md.py" --config "$WORK/courseware.json" \
  --md "$WORK/_out/part01.md" --allow-partial
```

报错行号是全文行号，直接改。`--allow-partial` 只放宽缺页/缺附录，不禁用语法和表格检查。

### 5. 附录

在最后一批或单独 `part99.md` 写 1–2 篇附录：

```markdown
### 附录 A · 公式与定理速查

**【速查表】**

| 编号 | 公式 | 名称 | 使用条件 |
|---|---|---|---|
| T1 | `A + 0 = A` | 0-1 律 | … |

---

### 附录 B · 化简与设计步骤

**【用法速记】**

1. 列真值表；
2. 写最小项；
3. 圈组；
4. 回代自检。
```

附录要求：只收本课件真正用到的内容；每个公式都与正文核对过；表格能直接打印使用。
附录不配课件图，编号自动排到页数之后（深链接 `#p83` 之类）。

### 6. 合并与全量校验

```bash
python "$SKILL/scripts/merge_parts.py" --config "$WORK/courseware.json"
python "$SKILL/scripts/check_md.py" --config "$WORK/courseware.json"
```

- 合并会自动插入目录（幂等，重复运行不叠加），目录固定在第 1 页之前；
- 最终校验**不能**带 `--allow-partial`；所有错误清零，警告逐条看过；
- 斜体、嵌套列表、注释过短、卡前正文等警告建议一并修掉；需要严格时加 `--strict`；
- 缺页就从 `_out/` 补写对应页，再重新合并。

### 7. 构建网页与 PDF

```bash
python "$SKILL/scripts/build_book.py" --config "$WORK/courseware.json"
python "$SKILL/scripts/make_pdf.py" --config "$WORK/courseware.json"
python "$SKILL/scripts/verify_book.py" --config "$WORK/courseware.json" --all
```

顺序不能反：先 HTML，再 PDF，最后自检。`make_pdf.py` 默认把原课件图一起打印
（内部生成 eager 加载的临时 HTML，打印后自动删除）。

自检必须全过：

- 结构：section 数 = 页数 + 附录数，`#pN` 都有目标，图片都存在；
- DOM：无 JS 报错，搜索/注释/原图/键盘/深链正常；
- 布局：1400px 与 430px 无横向溢出、无重叠、移动菜单可见；
- PDF：A4、页数足够、抽样页可提取中文。

失败时按 `references/troubleshooting.md` 定位，不要绕过检查。

### 8. 视觉验收

按全局规则，**布局问题必须看实际渲染，不能逐行读 CSS 推断**。

```bash
python "$SKILL/scripts/verify_book.py" --config "$WORK/courseware.json" --shots
```

截图在 `<out_dir>/_verify/`。逐张检查：对齐、间距、溢出、截断、遮挡、长标题、宽表格、
深色对比度、移动端目录、附录页码标签、打印分页。

环境里有 vision 技能时，直接用 DeepSeek 识图：

```bash
python ~/.claude/skills/vision/vision.py --provider deepseek \
  "_verify/desktop_p001.png" \
  "分析布局问题：对齐、间距、溢出、留白、截断、空白区域、遮挡、对比度"
```

`vision.py` 默认提供方就是 `deepseek`（读取 `DEEPSEEK_API_KEY`，缺省时回退到
`ANTHROPIC_AUTH_TOKEN`）；无需再指定 qwen 或 openai。vision 不可用（401、缺 key、
网络失败）时不要反复重试：直接看截图 + 依赖几何断言，并在最终报告里明确写
“**未完成模型化视觉分析**”，不得声称“视觉上完全正常”。

完整清单见 `references/qa-checklist.md`。

### 9. 使用说明与交付

复制模板并逐项替换占位符：

```bash
cp "$SKILL/assets/usage-template.txt" "$WORK/网页版电子书/使用说明.txt"
```

必须替换：`{{TITLE}}`、`{{DATE}}`、`{{SOURCE_PDF}}`、`{{PDF_OUT}}`、`{{PAGES}}`、
`{{OUT_DIR}}`、`{{MD_NAME}}`、`{{APPENDIX_LIST}}`、`{{SKILL_DIR}}`、`{{WORKDIR}}`。
交付前确认没有 `{{...}}` 残留。

最终报告写清：

- 原 PDF 页数、翻译页数、附录篇数；
- 成品路径（网页、PDF、Markdown、使用说明）；
- 通过的检查（check_md、verify_book 各项）；
- 视觉检查方式和限制；
- 疑似笔误、无法辨认的页、任何未完成项。

## 质量红线

1. **不跳页、不合并页、不改页序。** 封面、目录、空白页也要写。
2. **不臆造。** 图上的字、公式、数字，看不清就标注，不猜。
3. **不把译文当注释。** 注释必须补充重点、理由、用法。
4. **不隐藏问题。** 校验失败、视觉没做、笔误没把握，都要在报告里说。
5. **不交给用户一个需要联网的网页。** 除原图外，HTML/CSS/JS 全部内联。
6. **不覆盖用户原文件。** 配置和成品都在独立工作目录；`--force` 前先备份。

## 命令速查

```bash
SKILL="$HOME/.claude/skills/courseware-cn-annotator"
CFG="$WORK/courseware.json"

python "$SKILL/scripts/scaffold.py" --pdf "$PDF" --workdir "$WORK" --title "标题"
python "$SKILL/scripts/extract_text.py" --config "$CFG" [--pages 1-20] [--layout both]
python "$SKILL/scripts/render_pages.py" --config "$CFG" [--dpi 150] [--force]
python "$SKILL/scripts/check_md.py" --config "$CFG" [--md part.md --allow-partial] [--strict]
python "$SKILL/scripts/merge_parts.py" --config "$CFG" [--allow-partial]
python "$SKILL/scripts/build_book.py" --config "$CFG"
python "$SKILL/scripts/make_pdf.py" --config "$CFG" [--no-imgs] [--timeout 300]
python "$SKILL/scripts/verify_book.py" --config "$CFG" [--all|--shots|--pdf-check]
```

退出码：`0` 成功（可有警告）；`1` 内容/校验失败；`2` 环境/输入错误。

## 参考文件（按需加载）

| 文件 | 什么时候读 |
|---|---|
| `references/config-and-cli.md` | 改配置、查字段、看每个脚本的参数与退出码 |
| `references/annotation-style.md` | 写第一批之前；注释质量的核心规范 |
| `references/md-contract.md` | 写稿前；解析器支持/禁用语法、卡片与附录规则 |
| `references/qa-checklist.md` | 验收前；结构、内容、视觉、PDF 的完整清单 |
| `references/troubleshooting.md` | 任何一步报错时；按层定位 |

## 规模策略

| 页数 | 写法 |
|---|---|
| 1–5 | 一次写完，仍要全量校验 + 截图 |
| 6–20 | 分 2 批 |
| 21–100 | 每批 8–12 页；每批后 `--allow-partial`；先建术语表 |
| 100+ | 先按章填 `sections`；每批 8–10 页；中途合并一次做结构冒烟测试 |

上下文不够时不要硬塞：每页文本都在 `_extract/`，每批只看当前批和上一批最后一页。
