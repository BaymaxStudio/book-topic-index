#!/usr/bin/env bash
# 一条命令跑完整流水线：PDF → lines → 检索 → Word/Excel/标注版PDF
#
# 用法: run_pipeline.sh <book.pdf> <book.json> <outdir>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${HERE}/.."
PDF="${1:?用法: run_pipeline.sh <book.pdf> <book.json> <outdir>}"
CFG="${2:?需要 book.json}"
OUT="${3:?需要输出目录}"
BTI_HOME="${BTI_HOME:-$HOME/.cache/book-topic-index}"
PY="${BTI_HOME}/venv/bin/python"
MARK="${BTI_HOME}/bin/markpdf"

[ -x "$PY" ] || bash "${HERE}/setup_env.sh"
[ -x "$MARK" ] || bash "${HERE}/build_swift.sh"

mkdir -p "${OUT}/交付"

echo "── 1/4 抽取文本与坐标"
"${PY}" "${HERE}/pdf_lines.py" --pdf "${PDF}" --out "${OUT}" --noise "${CFG}"

echo "── 2/4 切段 + 页码校准 + 检索"
"${PY}" "${HERE}/scan.py" --lines "${OUT}/lines.jsonl" --out "${OUT}" --config "${CFG}"

echo "── 审计：零漏检对账"
"${PY}" "${HERE}/audit.py" --lines "${OUT}/lines.jsonl" --hits "${OUT}/命中明细.json" --config "${CFG}"

echo "── 3/4 生成索引 Word"
"${PY}" "${HERE}/make_docx.py" --hits "${OUT}/命中明细.json" \
    --out "${OUT}/交付/索引.docx" --config "${CFG}"

echo "── 4/4 生成标注版 PDF"
"${MARK}" "${PDF}" "${OUT}/annotations.json" "${OUT}/交付/标注版.pdf"

echo "── 完成，产物在 ${OUT}/交付/"
ls -la "${OUT}/交付/"
