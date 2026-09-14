# vhs 终端回放脚本 —— 需要 charmbracelet/vhs: brew install vhs
# 用法: vhs demo/demo.tape    （产物 demo/terminal.gif）
#
# 它录的是真实命令回放，不是摆拍。

Output demo/terminal.gif
Set Shell bash
Set FontSize 15
Set Width 1100
Set Height 640
Set Padding 16
Set TypingSpeed 35ms

Type "# 一条命令跑完整条流水线"
Enter
Sleep 400ms
Type "bash scripts/run_pipeline.sh book.pdf book.json out/"
Enter
Sleep 3s

Type "# 零漏检审计：原文出现次数 vs 明细覆盖次数"
Enter
Sleep 400ms
Type "python3 scripts/audit.py --lines out/lines.jsonl --hits out/命中明细.json --config book.json"
Enter
Sleep 3s

Type "# Tier 3 语义候选（判断性，单独输出，不混进主索引）"
Enter
Sleep 400ms
Type "python3 scripts/semantic.py --lines out/lines.jsonl --hits out/命中明细.json --out out --config book.json"
Enter
Sleep 3s
