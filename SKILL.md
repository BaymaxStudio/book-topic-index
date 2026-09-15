---
name: book-topic-index
description: 从成书（PDF/Word，含扫描件）中抽取某个主题或关键词的全部原文段落，标注书内印刷页码与 PDF 物理页，产出可直接引用的索引 Word、明细 Excel、高亮标注版 PDF。当用户上传一本书、一篇文献、扫描件或 Word，并要求「标出有关 X 的部分」「找出讲 X 的段落」「标出页码和内容」「做主题检索/文献索引」「这本书里 X 出现在哪几页」「把 PDF 里讲 X 的地方标出来」时，务必使用本技能；即使只说「从这本书里找 X」，或只给一个 PDF 加一个关键词，也应触发。也适用于需要把 PDF 物理页换算成书内印刷页码、或需要给 PDF 加批注高亮的场景。
---

# 书籍主题检索（勘校索引）

## 这个技能解决什么

用户手上常有一本书的 PDF（多半是扫描件，没有文字层）和一个主题词，想要的是
**"这本书里讲 X 的地方都在哪几页、原文是什么"**。听起来简单，实际上有四个坑，
每一个都会让结果错得很隐蔽：

1. 扫描版 PDF 根本没有文字层，pdftotext 只能提出水印；
2. PDF 的物理页序和书上印的页码对不上（前面有封面、目录、序言）；
3. OCR 会把关键词拆到两行（"意识 / 形态"），按行搜索会漏；
4. 正文、标题、目录里的关键词要分别处理，目录的页码还常常单独排一行。

这个技能把四件事都做对，并留下可核对的痕迹。

## 两条核心承诺

**页码必须准。** 用户拿这份索引是要去引用的。交付里同时给"书内印刷页码"和
"PDF 物理页"，两者的差值靠自动校准得到；校准结果连同投票分布一起写进
统计.json。如果投票分散（说明这本书的页码规律特殊），要在交付时明确告诉
用户，而不是假装准确。

**不能漏。** 每个主题词都要跑一次"零漏检审计"（scripts/audit.py），拿原文真实
出现次数和检索结果对账。审计不通过就不要交付。

## 三层检索：可信度必须分开标注

概念检索有三个层次，**混在一起会毁掉研究可信度**，所以要分开输出：

| 层 | 机制 | 可信度 | 输出位置 |
|---|---|---|---|
| **Tier 1 字面** | 正则精确匹配 | **可审计**（零漏检对账） | 主索引、明细表 |
| **Tier 2 相关词** | config.related 里的同义/派生表述 | **可审计**（同一条流水线） | 明细表（层级=相关） |
| **Tier 3 语义** | 启发式候选（信号词 + 命中的邻段） | **判断性，不保证查全** | 单独"待确认"清单 |

铁律：**Tier 3 的结论绝不能写进主索引的页码表**。用户敢说"我查全了"，靠的是
Tier 1/2 的对账；Tier 3 只是把"可能讲了但没用这个词"的段落缩小到可控规模，
判定权必须交回人。

候选生成见 scripts/semantic.py。**不要**用向量相似度自动判定语义——
实测 macOS NLEmbedding 中文句向量 AUC 仅 0.806（去均值后），过不了"召回不能漏"的门。

## 工作流程

### 第 0 步：盘清输入

先弄清（或从用户消息里读出来）：

- 哪本书？作者/版次（写封面用）。
- 主题词是什么？单个词，还是一组同义词/派生词？
- **有没有 Word 版？** 有的话优先用 Word 的文本（没有 OCR 错字），用 PDF 锚定页码。
- 要哪些输出？默认三件套：索引 Word + 明细 Excel + 标注版 PDF。

### 第 1 步：写 book.json

所有脚本吃同一份配置，这样换一本书不用改代码：

~~~json
{
  "title": "思想政治教育学原理",
  "edition": "第 3 版",
  "author": "陈万柏",
  "term_label": "意识形态",
  "terms": ["意识\s*形\s*态"],
  "related": ["社会意识形式", "观念上层建筑", "统治阶级的思想"],
  "signals": ["上层建筑", "社会意识", "灌输", "阶级性"],
  "noise": ["欢迎关注", "学习理论", "关注公众号"]
}
~~~

terms 是**正则列表**。写成 意识\s*形\s*态 而不是 意识形态，是为了接住 OCR
的跨行断字——这是必修项，不是可选优化。noise 放扫描件里的水印和公众号广告词，
这些行会在切段前被丢掉。

### 第 2 步：抽取文本与坐标

~~~bash
python3 scripts/pdf_lines.py --pdf book.pdf --out out/ --noise book.json
~~~

脚本先探测文字层（抽前几页、去噪声后数字符，≥200 算文字版），再自动分流：

- **文字版**：pdftotext -bbox 取词级坐标，按纵向重叠合成行，秒级完成；
- **扫描版**：走 OCR 后端。`--ocr auto`（默认）在 macOS 用 bin/ocrpdf（Vision），其余平台用 scripts/ocr_rapid.py（RapidOCR，内置离线模型）；也可 `--ocr vision|rapid` 强制。

两条路产出同一个 lines.jsonl，下游不必关心来源。

### 第 3 步：切段 + 页码校准 + 检索

~~~bash
python3 scripts/scan.py --lines out/lines.jsonl --out out/ --config book.json
~~~

这里做三件有讲究的事：

- **切段**：按行距突变 + 首行缩进（约 2 字符）把行还原成段落，再把段落内的行
  用空串拼起来——关键词被拆到两行时就能自动接回。
- **页码校准**：读每页页眉/页脚的纯数字行，取 PDF页 − 印刷页 的**众数**。
  一本书里这个差值几乎恒定，众数投票能免疫目录页、插图页的干扰。
  校准结果和投票数写进 统计.json 的"校准证据"字段——如果它是"无"，
  说明这份文档没有印刷页码可依据，交付时必须如实说明，不能把兜底的 0 当结论。
- **上下文跟踪**：页眉在奇数页/偶数页交替显示"章名/节名"，且**换章那一页
  常常没有页眉**。所以遇到新章要清空节名，否则会把上一章的节名串过来。

### 第 4 步：审计

~~~bash
python3 scripts/audit.py --lines out/lines.jsonl --hits out/命中明细.json --config book.json
~~~

对着 原文出现总次数 和 明细覆盖次数。两者不等说明有漏，回第 3 步查段落切分
阈值或跨页断字。

### 第 5 步：产出

~~~bash
python3 scripts/make_docx.py --hits out/命中明细.json --out out/交付/索引.docx --config book.json
python3 scripts/markpdf.py book.pdf out/annotations.json out/交付/标注版.pdf   # 跨平台
# macOS 也可继续用编译好的 ./bin/markpdf（Swift/PDFKit）
~~~

或者一条命令走完：

~~~bash
python3 scripts/run_pipeline.py book.pdf book.json out/      # 跨平台
bash scripts/run_pipeline.sh book.pdf book.json out/          # macOS 便捷入口
~~~

Word 单独输入时用 scripts/word_scan.py；同时有 Word 和 PDF 时，把 PDF 的
lines.jsonl 传给它做页码对齐（Word 没有固定页码，页码要借 PDF 的）。

### 第 6 步：自检后交付

- officecli validate <docx> 零错误、officecli view <docx> issues 零问题；
- 改过版式就把 Word 转 PDF **渲染几页出来看**，别凭想象；
- 抽查 2–3 个命中页，拿标注版 PDF 和原文对照；
- **主动说清 OCR 的局限**：扫描版正文约 99% 准确，个别错字存在，正式引用前
  对照原文；如果用了 Word 版，就说明错字已消除。

## 关键陷阱（以及为什么）

| 现象 | 原因 | 解法 |
|---|---|---|
| swiftc 报 Operation not permitted 或直接崩溃 | 沙箱/含空格路径下 clang 写不了默认模块缓存 | 把 -module-cache-path 指到无空格目录，见 scripts/build_swift.sh |
| Windows 上 OCR 报缺依赖 | 未装 RapidOCR | `python scripts/setup_env.py`（装 rapidocr + onnxruntime） |
| RapidOCR 偶尔漏一行小字 | 检测端把长边缩得太小 | 调大 scripts/ocr_rapid.py 的 `--limit-side-len`（默认 2000） |
| 关键词总少几处 | OCR 把词拆到两行 | terms 用 \s* 连接每个字 |
| 目录页的关键词搜不到 | 标题行被排除在检索之外 | 标题也检索，并单列"目录条目" |
| 目录条目配不到页码 | 条目文字与页码是两行 | 按 y 坐标就近配对 |
| 双栏 PDF 里左右栏被粘成一句 | 只按 y 重叠合并行，忽略了栏间空隙 | 横向间距超过约 2.5 个字符宽就断行 |
| 整页正文被拆成一行一段、跨行关键词全漏 | 一条脚注/杂线把"左边距"最小值拉到最左，于是每行都像首行缩进 | 左边距取**众数**而非最小值 |
| 关键词那行被当成标题、段落被切断 | 带引号的行 bbox 偏高，行高启发式（≤30 字）误判 | 行高判标题要保守：长度 ≤16 且不以句读收尾 |
| 目录页没被识别，目录条目污染正文章节名 | 目录页码不在右边缘、点线只剩单个「•」，且"目录"二字被 OCR 拆行 | 目录判定改用整页版面特征（满页短条目+独立数字行+点线），并向相邻同构页扩张 |
| "2023.09" 这类小数被当成标题 | 标题正则 \d+ 不设上限 | 标题编号限 1–2 位，排除 pdf_lines 文字版取不到印刷页码 |
| 页码偏移=0 但没有投票 | 文档本身没有印刷页码（单页/无页眉） | 统计.json 的"校准证据"字段会写"无"，交付时要说明 |
| Word 打开掉格式 | 手工插入的 XML 子元素次序违反 schema | 按 OOXML 次序插入，用 officecli validate 把关 |

## 输出

| 文件 | 内容 |
|---|---|
| 交付/索引.docx | 勘校索引版式：左栏页码导轨 + 右栏引文，关键词朱色，首页页码可点击跳转 |
| 命中明细.csv / .json | 页码 / 章节 / 定位句 / 完整段落，可筛选 |
| 交付/标注版.pdf | 原书 + 高亮批注，供逐条核对 |
| 统计.json | 校准偏移、投票分布、命中统计 |
| 报告.md | 纯文本版索引 |

## 参考文件

- references/pipeline.md — 段落切分阈值、页码校准算法、排障清单
- references/docx-design.md — Word 版式设计系统与 OOXML 踩坑
- 每个脚本头部都写了"为什么这么写"的注释

## 兼容性

- **三平台一致**：扫描件 OCR + 页码校准 + 零漏检审计 + 索引 Word + 标注 PDF 在 Windows / macOS / Linux 都能跑。
- OCR 后端自适应：macOS 用本机 Vision（bin/ocrpdf），Windows/Linux 用 RapidOCR（scripts/ocr_rapid.py）；`--ocr vision|rapid` 可强制。
- PDF 高亮：macOS 可用 markpdf（Swift），其余平台用 markpdf.py（PyMuPDF）；run_pipeline.py 自动选。
- 文字层抽取优先 pdftotext，缺失时回退 PyMuPDF；Word 输入优先 pandoc。
- 依赖：`python scripts/setup_env.py` 建好缓存 venv（python-docx/pymupdf/rapidocr/onnxruntime）。
