# Word 版式设计系统（勘校索引）

## 为什么不是普通报告模板

这份文档的职责是**让人快速定位并引用**，不是"呈现内容"。所以版式的骨架必须
编码内容本身的结构：页码。于是做成左栏页码导轨 + 右栏引文的索引形态。

## 设计令牌

**配色**（刻意避开 AI 常见的"奶油底+陶土红"）：

| 名称 | 值 | 用途 |
|---|---|---|
| 墨 | 16181D | 正文 |
| 靛 | 1F3A5F | 结构色：页码、章节眉、分隔线 |
| 朱 | A8322A | **只用于关键词** |
| 灰 | 6B7280 | 次要信息 |
| 银 | D9DCE1 | 发丝分隔线 |

朱色只出现在一个地方，是有意的克制：整份文档的"记忆点"应该是"被朱笔标出的
关键词"，其他一律安静。这正是"朱批"的隐喻，也是这个技能名字的由来。

**字体**：标题黑体 / 引文宋体 / 数字 Times New Roman。
引文用宋体是因为要与原书同体——它在视觉上提示"这是原文"。

**结构**：每个书内页码一个表行，左栏大号页码 + 小号 PDF 页，右栏章节眉 + 引文，
两栏之间一条发丝竖线。行底一条发丝横线。

## OOXML 元素次序（最容易踩的坑）

w:pPr、w:rPr、w:tcPr、w:tblPr 的子元素次序在 schema 里是**固定序列**，
用 append 随手加会生成 Word 能打开、但严格校验器报错的文件（换 Word 版本可能掉格式）。

正确的插入顺序（节选）：

- pPr：pStyle → keepNext → ... → pBdr → shd → ... → spacing → ind → jc → rPr
- rPr：rFonts → b → ... → color → spacing → sz
- tcPr：tcW → tcBorders → shd → tcMar → vAlign
- tblPr：tblW → jc → tblLayout → tblCellMar → tblLook

用 python-docx 的 `insert_element_before(elm, *successors)` 按后续元素列表插入即可。
本技能的 scripts/make_docx.py 已经把这些次序固化在常量里。

另一个坑：**一个单元格只能有一个 w:tcBorders**。要同时加左边线和下边线，必须
合并进同一个 tcBorders，不能 append 两次。

还有：`table.autofit = False` 会自动生成 w:tblLayout，如果代码里再手工加一个就会
出现重复元素。列宽要同时写 `cell.width` 和 `table.columns[i].width`，否则
tblGrid 仍是均分，正文会被挤进半页窄栏。

## 空段落禁令

不要用空段落当间距或分隔线——它会被 lint 出来，而且分页行为不可控。
间距用 space_before/after，分隔线用段落或单元格的 pBdr / tcBorders。

## 交付前检查

~~~bash
officecli validate 索引.docx     # 必须 no errors found
officecli view 索引.docx issues  # 必须 0 issues
soffice --headless --convert-to pdf --outdir /tmp 索引.docx
pdftoppm -f 1 -l 1 -r 100 -png /tmp/索引.pdf /tmp/pg   # 渲染出来亲眼看
~~~
