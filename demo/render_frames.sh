#!/usr/bin/env bash
# 把真实产物渲染成 demo 帧（PNG）。可复现：任何人有产物就能重跑。
# 用法: render_frames.sh <索引.docx> <标注版.pdf> <标注Pdf页> <输出目录>
set -euo pipefail
DOCX="${1:?需要 索引.docx}"
ANN="${2:?需要 标注版.pdf}"
ANNPAGE="${3:-12}"
OUT="${4:-frames}"
mkdir -p "$OUT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1) 索引 Word → PDF → 前两页
soffice --headless --convert-to pdf --outdir "$WORK" "$DOCX" >/dev/null 2>&1
IDX="$WORK/$(basename "${DOCX%.docx}").pdf"
pdftoppm -f 1 -l 2 -r 90 -png "$IDX" "$OUT/index"
# 2) 标注版原书页（看高亮）
pdftoppm -f "$ANNPAGE" -l "$ANNPAGE" -r 90 -png "$ANN" "$OUT/annotated"
ls "$OUT"
