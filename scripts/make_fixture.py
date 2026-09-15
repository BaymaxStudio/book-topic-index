#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一个小的合成『扫描件』PDF + 配置，供跨平台 smoke test / CI 使用。

    python3 scripts/make_fixture.py
      -> evals/fixtures/synthetic-scan.pdf      只有图像、无文字层（模拟扫描书）
      -> evals/fixtures/synthetic-book.json     对应检索配置

用 PyMuPDF 内置中文字体绘制页面后栅格化，内容纯合成、可公开。
"""

import argparse
import json
from pathlib import Path

import fitz  # PyMuPDF

PAGES = [
    ("42", ["第一章 理论基础", "本章讨论意识形态的基本内涵与功能。",
            "意识形态工作是一项极端重要的工作。", "我们要重视意识形态领域的建设。"]),
    ("43", ["第二章 现实问题", "意识形态的吸引力来自解释力。",
            "任何社会的意识形态都服务于其经济基础。"]),
    ("44", ["第三章 实践路径", "加强意识形态阵地建设。",
            "意识形态安全是国家总体安全的一部分。", "做好意识形态工作人人有责。"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evals/fixtures/synthetic-scan.pdf")
    ap.add_argument("--config", default="evals/fixtures/synthetic-book.json")
    a = ap.parse_args()

    src = fitz.open()
    for header, lines in PAGES:
        page = src.new_page(width=595, height=842)
        page.insert_text((300, 60), header, fontname="china-s", fontsize=14)
        y = 120
        for i, ln in enumerate(lines):
            page.insert_text((72, y), ln, fontname="china-s", fontsize=16 if i == 0 else 13)
            y += 34

    out = fitz.open()
    for pno in range(src.page_count):
        pix = src[pno].get_pixmap(dpi=200)
        p = out.new_page(width=595, height=842)
        p.insert_image(p.rect, stream=pix.tobytes("jpg", jpg_quality=80))

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)

    cfg = {"title": "合成扫描样本", "term_label": "意识形态",
           "terms": ["意识\\s*形\\s*态"], "noise": ["欢迎关注"]}
    Path(a.config).parent.mkdir(parents=True, exist_ok=True)
    Path(a.config).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", a.out, "and", a.config)


if __name__ == "__main__":
    main()
