# 故障排查

先定位是哪一层：**读 PDF → 写 Markdown → 构建 HTML → 打印 PDF → 自检**。
每一层都有独立的诊断命令，不要一上来就重跑全流程。

## 依赖与环境

### `未安装 PyMuPDF`

```bash
python -m pip install pymupdf
```

Python 需要 3.10+。如果 `python` 指向 Microsoft Store 的占位程序，改用实际解释器
（例如 Anaconda 的 `python.exe`）。所有脚本只用标准库 + PyMuPDF；Pillow 只在裁剪
移动端截图时用到，缺失只会跳过裁剪，不影响主流程。

### 找不到 Chrome / Edge

```bash
# 显式指定
python make_pdf.py --config courseware.json --chrome "C:/Program Files/Google/Chrome/Application/chrome.exe"

# 或设环境变量
set CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
```

macOS 路径：

```
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

只有打印 PDF、DOM 探针、截图需要浏览器；Markdown 校验和 HTML 构建不需要。

### 中文 / 空格路径

脚本内部用 `Path.as_uri()` 生成 `file://` URL，理论上支持中文和空格。仍然出错时：

- 命令行参数全部加引号；
- 确认没有把路径拆成多个参数；
- 在 Git Bash 里设置 `export PYTHONIOENCODING=utf-8`；
- Windows 控制台乱码时执行 `chcp 65001`。

### 路径过长

Windows 默认 260 字符限制。`scaffold.py` 会把标题截到 80 字符，但工作目录本身很深时
仍可能超限。把工作目录移到较短的路径（如 `D:\course\ch1`）再试。

## PDF 读取

### `PDF 已加密`

需要先解密：

```bash
python -c "import pymupdf; d=pymupdf.open('x.pdf'); print(d.needs_pass)"
```

有密码时本技能不会尝试破解；请让用户提供无密码版本。

### 扫描页 / 没有文本层

`_extract/index.json` 的 `scanned_pages` 列出这些页。处理顺序：

1. 打开 `slides/pNNN.png`，按图逐行转写；
2. 有 OCR 工具时可以先 OCR 再人工校对；
3. 图太模糊/分辨率太低：用 `render_pages.py --pages N --dpi 200 --force` 重渲染；
4. 仍然看不清：写“本页为图片，文字以讲义为准”，并在最终报告中说明，**不要编内容**。

### 文字顺序错乱

`needs_vision_pages` 是提示列表。也可以手动比对：

```bash
python extract_text.py --config courseware.json --pages 12 --layout both --force
```

- `p012.txt`：默认阅读顺序；
- `p012.blocks.txt`：按坐标从上到下、从左到右排序。

两者差异大时，以渲染图为准。多栏排版、公式标注、流程图最容易错序。

### 字体嵌入导致复制出乱码

某些 PDF 的 ToUnicode 表缺失，抽取出来是 `����` 或私用区字符。此时文本层不可信，
只能看渲染图转写；不要试图“猜”原字。

### 页数对不上

- `page_count` 必须是 **PDF 物理页数**，用 `pymupdf.open(...).page_count` 确认。
- 封面、目录、空白页、分隔页都算页，都要写。
- 课件印刷页码 ≠ PDF 页码；不要按印刷页码编号。
- `build_book.py` 报 `Markdown 有 X 页，但配置 page_count=Y`：先补页或改配置，
  不要绕过。

## Markdown 校验

### `没有找到正文起点（'### 第 1 页'）`

- 标题被写成了 `## 第 1 页`、`# 第 1 页` 或 `### 第1页`（后者其实能匹配，
  但推荐加空格）；
- 标题前有空格或 BOM；`read_text` 会去掉 BOM，但行首空格不会；
- 文件编码不是 UTF-8。

### `缺少页面：[7]`

分批写作的正常现象。加 `--allow-partial` 继续；最终合并后必须补齐。
如果确实没有第 7 页，说明 `page_count` 或页序错了。

### `页码重复`

复制上一页后忘了改标题。用编辑器的查找 `### 第` 逐条核对。

### `### … 不是页面/附录标题`

页面内部用了 `### 小标题`，构建器会把它当成新页开头，导致后半页内容丢失。
改成 `#### 小标题` 或 `**粗体小标题**`。

### `表格列数不齐`

表头、分隔行、数据行的 `|` 数量必须一致。注意单元格里的 `|` 也会被当成分列符，
包括行内代码里的 `|`。

### 误报：`$...$` / 链接 / HTML

`check_md.py` 是保守的逐行扫描：

- 金额 `$5` 和 `$10` 可能被误判成公式 → 改成“5 美元”或去掉 `$`；
- 代码块里的 `###` 仍会被当作页标题 → 代码里不要用行首 `###`，或改成 `# 注释`；
- 正文里真的要展示 `<tag>` → 用反引号包起来也可能仍被扫描；改成文字描述。

无法规避时，人工确认后可以临时用 `--allow-partial` 之外的方式跳过，但要在报告中记录；
不要为了让校验通过而删掉真实内容。

### 注释过短警告

`< 20` 字符几乎一定是占位。封面/过渡页可以短，但仍要写清“这页的作用”。

### `配置要求附录，但没有找到`

补 `### 附录 A · 标题`。分批阶段可加 `--allow-partial`，最终稿不行。

### 合并后目录位置不对 / 出现两份目录

- 目录只认 `<!-- AUTO-TOC:START -->` / `<!-- AUTO-TOC:END -->`；
  手写的“目录”不会被替换。
- 重复运行 `merge_parts.py` 是幂等的；如果仍有两份，说明旧目录没有标记，
  手工删除旧目录后重跑。
- 目录固定插在第一个 `### 第 1 页` 之前，不会进第 1 页的注释卡。

## HTML 构建

### `页码必须从 1 连续编号`

`build_book.py` 比 `check_md.py` 更严格：它不允许缺页，因为缺页会让深链接和页码错位。
先合并、补齐、再构建预览。

### 页面数为 0 / 没有解析出页面

- 页面标题不在行首；
- 用了全角空格或不可见字符；
- 文件不是 UTF-8；
- `### 第 1 页` 出现在 YAML frontmatter 或引用块里。

### 正文少了一段

最常见原因：页面内出现行首 `###`，被切成新页；其次是卡片标签没有独占一行，
导致后续内容被吞进上一张卡。用 `check_md.py` 定位行号。

### 图片不显示

- `slides/pNNN.png` 不存在 → 重新渲染；
- `index.html` 与 `slides/` 被分开移动 → 放回同一目录；
- 文件名不是三位数（`p1.png` 不会匹配，必须是 `p001.png`）；
- 浏览器阻止本地文件？Chrome/Edge 打开本地 HTML 和同目录图片是允许的。

### 按钮没反应 / 页面空白

1. 用 Chrome 或 Edge 打开，不要用 IE；
2. 打开开发者工具 Console 看报错；
3. 确认 `index.html` 里内联了 `book.js`（构建时会替换 `@@JS@@`，不应残留）；
4. 无原图模式应隐藏“显示原图”按钮，而不是报错；
5. 如果是从旧版本构建的页面，重新 `build_book.py`。

### 搜索没有结果

- 搜索是“页面全文包含”，多个关键词是“与”关系；
- 索引会去掉空白，所以“5 变量”和“5变量”都能命中；
- `probe_keyword` 默认取第一页标题前 6 字，可能包含标点；手动设成正文里确定存在的词；
- 搜“附录”应命中附录 section；如果为 0，检查附录的 `data-title` 是否为空。

### 移动端截图宽度不对

Windows 无头 Chrome 的窗口最小宽度约 512px，直接设 `--window-size=430` 得到的
视口仍是 512。`verify_book.py` 用 iframe 包装模拟 430px，并用
`--allow-file-access-from-files` 读取 iframe 标题。若看到 `iframe 里的页面无法访问`：

- 确认 Chrome 版本支持 `--allow-file-access-from-files`；
- 确认临时 HTML 没有被杀毒软件拦截；
- 退化为只看桌面截图，并在报告中说明移动端未验证。

### 截图被裁切

`verify_book.py` 会对移动截图用 Pillow 裁到 430×900。Pillow 缺失时保留原始宽度，
不影响布局断言。

## PDF 打印

### PDF 里没有原课件图

默认模式会：

1. 复制 `index.html` 为 `_print_tmp.html`；
2. 把 `loading="lazy"` 改成 `loading="eager"`；
3. 用 `?imgs=1&notes=1` 打开；
4. 打印后删除临时文件。

排查：

- 是否加了 `--no-imgs`；
- `slides/` 是否有图；
- 临时文件是否因权限无法创建；
- `--virtual-time-budget=20000` 是否不够（图多时加大 `--timeout`）；
- Chrome 是否被其他进程占用。

### PDF 页数异常少

- 图片没加载，内容高度变小；
- 打印 CSS 把某些块隐藏了；
- 用户自定义的 `footer_lines` 太长导致溢出；
- 用 `--no-imgs` 本来就会少很多页。

### PDF 页数异常多 / 文件巨大

- DPI 太高：`render_pages.py --dpi 100 --force` 重渲染；
- 图片是 PNG 且尺寸很大；可接受时转 JPEG 或降 DPI；
- 每页都被分页符切开：检查 `book.css` 的 `break-inside`；
- 82 页含图约 10–15 MB 属正常。

### 打印出来没有底色

打印设置里勾选“背景图形 / Background graphics”。CSS 已加
`print-color-adjust: exact`，但浏览器仍可能默认关闭背景。

### 表格/代码块跨页断裂

在 `book.css` 里给 `table`、`pre`、`figure` 加 `break-inside: avoid`，
然后重新 `build_book.py` 和 `make_pdf.py`。

### Chrome 超时

```bash
python make_pdf.py --config courseware.json --timeout 600
```

仍超时：先用 `--no-imgs` 验证文字部分，再逐页排查超大图片。

### 打印顺序不对

`index.html` 的 DOM 顺序就是打印顺序：正文按页码，附录在最后。如果顺序错，
说明 Markdown 页序错了，`check_md.py` 会给“页面顺序与页码顺序不一致”警告。

## 自检脚本

### DOM 探针失败：`页面脚本可能崩溃`

- 打开 `index.html` 看 Console；
- 确认没有 `book.js` 语法错误（重新构建）；
- 确认没有残留 `@@...@@`；
- `--virtual-time-budget=9000` 对超大页面可能不够，临时调大。

### 布局失败：横向溢出

常见来源：

- 长公式/代码块没有 `overflow-x: auto`；
- 表格列太多；
- 超长英文单词/URL；
- 移动端固定宽度元素。

修 `book.css` 后重新构建。不要靠“缩小字号”掩盖溢出。

### 布局失败：侧栏与正文重叠

- 桌面断点 `1001px` 附近最容易出问题；
- 检查 `.side` 的宽度和 `main` 的 margin 是否同步；
- 移动端侧栏应作为抽屉覆盖，不应挤压正文。

### PDF 抽样页没有文字

整页被当成图片，或字体未嵌入。用 `pymupdf` 检查：

```bash
python -c "import pymupdf; d=pymupdf.open('x.pdf'); print([len(d[i].get_text()) for i in range(min(3,d.page_count))])"
```

全是 0 说明打印时内容被隐藏或仍是图片。

## 什么时候停下来问用户

以下情况不要硬编，先说明并请用户决定：

- PDF 加密且无密码；
- 大面积为无法辨认的扫描页，且没有 OCR/vision 可用；
- PDF 页数与用户描述的章节结构严重不符；
- 原课件含大量手写批注/复杂图表，无法可靠转写；
- 需要打印 PDF 但环境没有 Chrome/Edge，且用户不接受只交 HTML；
- 课件内容涉及考试答案、版权材料，用户要求整段复制而超出合理引用范围。

## 清理

- `_print_tmp.html` 正常会自动删除；Chrome 崩溃时可能残留，可手动删。
- `_probe_*.html`、`_wrap_*.html` 由探针生成，正常也会删除。
- `__pycache__/`、`*.pyc` 不需要交付。
- `_extract/`、`_out/`、`_verify/` 建议保留，便于修订和复检。
