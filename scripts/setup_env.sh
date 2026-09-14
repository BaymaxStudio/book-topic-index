#!/usr/bin/env bash
# 准备 Python 依赖（python-docx 用于生成 Word 索引）。
# 装在技能目录下的 .venv，不污染全局环境。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BTI_HOME="${BTI_HOME:-$HOME/.cache/book-topic-index}"
VENV="${BTI_HOME}/venv"
mkdir -p "$BTI_HOME"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
PIP_CACHE_DIR="${TMPDIR:-/tmp}/bti-pip-cache" \
  "$VENV/bin/pip" install --quiet --disable-pip-version-check python-docx
echo "env ready: $VENV"
