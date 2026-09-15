#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台准备 Python 依赖（venv 落在 BTI_HOME，不污染全局环境）。

    python3 scripts/setup_env.py            # 全量：python-docx + pymupdf + rapidocr + onnxruntime
    python3 scripts/setup_env.py --no-ocr   # 只装基础（macOS 用本机 Vision 时可省 OCR 依赖）

Windows 与 macOS/Linux 通用；替代原来的 bash 版 setup_env.sh。
"""
import argparse
import os
import subprocess
import venv
from pathlib import Path

BTI_HOME = Path(os.environ.get("BTI_HOME", os.path.expanduser("~/.cache/book-topic-index")))
VENV = BTI_HOME / "venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ocr", action="store_true", help="不安装 rapidocr/onnxruntime")
    a = ap.parse_args()

    BTI_HOME.mkdir(parents=True, exist_ok=True)
    if not VENV.exists():
        print("creating venv:", VENV)
        venv.EnvBuilder(with_pip=True).create(str(VENV))

    pkgs = ["python-docx", "pymupdf"] + ([] if a.no_ocr else ["rapidocr", "onnxruntime"])
    print("installing:", " ".join(pkgs))
    subprocess.run([str(PY), "-m", "pip", "install", "--quiet",
                    "--disable-pip-version-check", *pkgs], check=True)
    print("env ready:", VENV)


if __name__ == "__main__":
    main()
