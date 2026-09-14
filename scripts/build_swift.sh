#!/usr/bin/env bash
# 编译两个 Swift 工具（扫描版 OCR 与 PDF 高亮标注）。
#
# 为什么要这么写：swiftc 默认把 clang 模块缓存写到 $TMPDIR 下，
# 在沙箱或含空格/中文的路径里会 "Operation not permitted" 或直接崩溃。
# 唯一可靠的解法是把 -module-cache-path 指到一个无空格的可写目录。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# 技能目录可能只读，产物放缓存目录
BTI_HOME="${BTI_HOME:-$HOME/.cache/book-topic-index}"
BIN="${BTI_HOME}/bin"
mkdir -p "$BIN"

CACHE="${TMPDIR:-/tmp}/bti-swift-cache"
mkdir -p "$CACHE"

for tool in ocrpdf markpdf; do
  src="${HERE}/${tool}.swift"
  out="${BIN}/${tool}"
  echo "compiling ${tool} ..."
  swiftc -O -module-cache-path "$CACHE" -o "$out" "$src"
done
echo "built: $BIN/ocrpdf $BIN/markpdf"
