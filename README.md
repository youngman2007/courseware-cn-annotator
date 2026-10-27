# courseware-cn-annotator

一个 Claude Code Skill：把课件、讲义或课堂 PPT 的 **PDF** 一次性做成完整的中文学习包。

产出包含：

- 逐页中文翻译
- 面向零基础读者的**三问式逐页注释**（这页在说什么 / 为什么 / 怎么用）
- 可编辑的 Markdown 源稿
- 离线单文件 HTML 电子书（分组目录、全文搜索、注释与原图开关、深色主题、键盘翻页、深链）
- A4 打印版 PDF
- 使用说明，以及 1–2 篇学科速查附录（速查表 / 答题模板）

## 安装

把这个仓库克隆到 Claude Code 的技能目录。**目录名必须是 `courseware-cn-annotator`**。

macOS / Linux：

```bash
git clone https://github.com/<your-name>/courseware-cn-annotator.git \
  ~/.claude/skills/courseware-cn-annotator
```

Windows（PowerShell）：

```powershell
git clone https://github.com/<your-name>/courseware-cn-annotator.git "$env:USERPROFILE\.claude\skills\courseware-cn-annotator"
```

克隆后重启 Claude Code（或在会话里重新加载技能），然后对 Claude 说：

> 把这份课件做成学习包：`D:\课程\第1章.pdf`

## 依赖

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| Python 3.10+ | 必需 | 所有脚本的运行环境 |
| [PyMuPDF](https://pypi.org/project/PyMuPDF/) | 必需 | PDF 解析与逐页渲染 `python -m pip install pymupdf` |
| Pillow | 可选 | 裁剪移动端截图 `python -m pip install pillow` |
| Chrome 或 Edge | 可选 | 生成打印 PDF、DOM 自检与截图；找不到浏览器时相关步骤会跳过 |
| `vision` skill | 可选 | 模型化截图检查；不可用时降级为几何断言，并在报告中注明 |

## 使用方式

不需要手动敲脚本。安装好后直接把 PDF 路径交给 Claude，并说明要"做成学习包"。
Claude 会按 `SKILL.md` 里固定的五步流程执行：

1. `scaffold.py` 建工作目录、抽取逐页文本、渲染逐页 PNG
2. 分批撰写 `_out/partNN.md`（翻译 + 注释）
3. `check_md.py` 校验 Markdown 契约，`merge_parts.py` 合并
4. `build_book.py` 生成离线电子书，`make_pdf.py` 生成打印版
5. `verify_book.py` 做几何断言、截图与 PDF 抽样自检

想了解完整流程、参数和写作规范，直接读 [SKILL.md](SKILL.md)，细节在
[references/](references/) 里。

## 仓库结构

```
SKILL.md                 技能主文件（流程、写作规范、质检要求）
references/              详细参考：注释风格、Markdown 契约、配置与 CLI、排查、QA 清单
scripts/                 可执行脚本（建目录、抽取、校验、合并、出书、出 PDF、自检）
assets/                  电子书模板（CSS / JS / 使用说明模板）
evals/                   流水线冒烟测试与夹具
```

## 常见问题

**输入只有 PPTX 怎么办？**
先用 PowerPoint「另存为 PDF」，或 `soffice --headless --convert-to pdf 课件.pptx`，再处理。
脚本不直接解析 PPTX。

**PDF 是扫描版、没有文字层？**
可以做，但必须逐页看渲染图转写，速度会慢很多；注释里不会凭空编造图上的标注。

**打印 PDF 失败？**
确认装了 Chrome 或 Edge；也可以用 `CHROME=/path/to/chrome` 显式指定。
详见 [references/troubleshooting.md](references/troubleshooting.md)。

## 许可

[MIT](LICENSE)
