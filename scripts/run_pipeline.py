#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台一条命令跑完整流水线：PDF → lines → 检索 → Word/Excel/标注版 PDF。

用法:
    python3 run_pipeline.py <book.pdf> <book.json> <outdir>
        [--ocr auto|vision|rapid] [--mark auto|swift|python] [--dpi 300]

- --ocr  auto：macOS 且 Swift 可用 → Vision；否则 RapidOCR
- --mark auto：macOS 且已编译 markpdf → Swift；否则 PyMuPDF
替代原来的 bash 版 run_pipeline.sh（Windows 无需 Git Bash）。
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BTI_HOME = Path(os.environ.get("BTI_HOME", os.path.expanduser("~/.cache/book-topic-index")))


def run(cmd):
    cmd = [str(c) for c in cmd]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def mark_backend(pref):
    if pref == "python":
        return "python"
    if pref == "swift":
        return "swift"
    swift = BTI_HOME / "bin" / "markpdf"
    return "swift" if (sys.platform == "darwin" and swift.exists()) else "python"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("config")
    ap.add_argument("out")
    ap.add_argument("--ocr", default="auto", choices=["auto", "vision", "rapid"])
    ap.add_argument("--mark", default="auto", choices=["auto", "swift", "python"])
    ap.add_argument("--dpi", type=int, default=300)
    a = ap.parse_args()

    py = sys.executable
    out = Path(a.out)
    (out / "交付").mkdir(parents=True, exist_ok=True)

    run([py, HERE / "pdf_lines.py", "--pdf", a.pdf, "--out", a.out,
         "--noise", a.config, "--ocr", a.ocr, "--dpi", a.dpi])
    run([py, HERE / "scan.py", "--lines", out / "lines.jsonl", "--out", a.out, "--config", a.config])
    run([py, HERE / "audit.py", "--lines", out / "lines.jsonl",
         "--hits", out / "命中明细.json", "--config", a.config])
    run([py, HERE / "make_docx.py", "--hits", out / "命中明细.json",
         "--out", out / "交付" / "索引.docx", "--config", a.config])

    if mark_backend(a.mark) == "swift":
        run([BTI_HOME / "bin" / "markpdf", a.pdf, out / "annotations.json", out / "交付" / "标注版.pdf"])
    else:
        run([py, HERE / "markpdf.py", a.pdf, out / "annotations.json", out / "交付" / "标注版.pdf"])

    print("完成，产物在", out / "交付")


if __name__ == "__main__":
    main()
