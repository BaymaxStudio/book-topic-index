#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描版 PDF → lines.jsonl（RapidOCR 后端，跨平台，替代 macOS Vision）。

与 scripts/ocrpdf.swift 输出**完全一致**的 schema：
    {"page":N,"w":W,"h":H,"lines":[{"t":文本,"x":..,"y":..,"w":..,"h":..,"c":..}]}
x/y/w/h 归一化到 0~1、原点左上；W/H 为该页渲染像素尺寸（--dpi，默认 300）。

依赖:
    pip install rapidocr onnxruntime pymupdf
（Windows / macOS / Linux 通用；模型随包内置，首次运行若缺模型会提示联网获取）

用法:
    python3 ocr_rapid.py <pdf> <outdir> [firstPage] [lastPage] [--dpi 300]
"""

import argparse
import json
import sys
from pathlib import Path

from bti_console import force_utf8


def main():
    force_utf8()
    ap = argparse.ArgumentParser(description="RapidOCR: scanned PDF -> lines.jsonl")
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=0)  # 0 = 到末页
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--limit-side-len", type=int, default=2000,
                    help="检测端最长边像素；扫描小字被漏检时调大（默认 2000，太大变慢）")
    a = ap.parse_args()

    try:
        import numpy as np
        import fitz
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise SystemExit(
            "缺少跨平台 OCR 依赖：%s\n"
            "  安装：pip install rapidocr onnxruntime pymupdf\n"
            "  或运行：python3 scripts/setup_env.py" % exc.name
        )

    pdf_path = Path(a.pdf).resolve()
    outdir = Path(a.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # 某些推理依赖会在「当前工作目录」写会话文件（如 :memory:.ses）。
    # 先切到独立临时目录，避免污染用户的项目目录；之后一律使用绝对路径。
    import os
    import tempfile
    scratch = Path(tempfile.gettempdir()) / "book-topic-index-ocr"
    scratch.mkdir(parents=True, exist_ok=True)
    os.chdir(scratch)

    try:
        engine = RapidOCR(params={"Det.limit_side_len": a.limit_side_len})
    except Exception as exc:  # noqa: BLE001 - 模型缺失/初始化失败都要给可执行指引
        raise SystemExit(
            "RapidOCR 初始化失败：%s\n"
            "首次运行可能需要联网下载模型；离线机器请先在有网环境执行 rapidocr check 预取。" % exc
        )

    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    first = max(1, a.first)
    last = total if not a.last else min(a.last, total)

    with open(outdir / "lines.jsonl", "w", encoding="utf-8") as fh, \
         open(outdir / "text.txt", "w", encoding="utf-8") as th:
        for pno in range(first, last + 1):
            page = doc[pno - 1]
            pix = page.get_pixmap(dpi=a.dpi, alpha=False)
            W, H = pix.width, pix.height
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(H, W, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            img = img[:, :, ::-1].copy()  # PyMuPDF 出 RGB，cv2 系约定要 BGR

            lines = []
            try:
                res = engine(img)
            except Exception as exc:  # noqa: BLE001 - 单页失败不中断整本
                print("page %d OCR failed: %s" % (pno, exc), file=sys.stderr)
                res = None
            boxes = getattr(res, "boxes", None) if res is not None else None
            txts = getattr(res, "txts", None) if res is not None else None
            scores = getattr(res, "scores", None) if res is not None else None
            if boxes is not None and txts:
                for i, box in enumerate(boxes):
                    t = txts[i] if i < len(txts) else ""
                    if not str(t).strip():
                        continue
                    s = float(scores[i]) if scores is not None and i < len(scores) else 0.0
                    xs = [float(p[0]) for p in box]
                    ys = [float(p[1]) for p in box]
                    x0, x1 = min(xs), max(xs)
                    y0, y1 = min(ys), max(ys)
                    lines.append({
                        "t": str(t),
                        "x": x0 / W, "y": y0 / H,
                        "w": (x1 - x0) / W, "h": (y1 - y0) / H,
                        "c": round(s, 2),
                    })
            lines.sort(key=lambda l: (l["y"], l["x"]))

            fh.write(json.dumps({"page": pno, "w": W, "h": H, "lines": lines},
                                ensure_ascii=False) + "\n")
            th.write("\n===== [PDF p.%d] =====\n" % pno)
            for l in lines:
                th.write(l["t"] + "\n")
            if pno % 10 == 0 or pno == first or pno == last:
                print("page %d/%d lines=%d" % (pno, last, len(lines)), file=sys.stderr)

    doc.close()
    print("DONE pages %d-%d of %d" % (first, last, total))


if __name__ == "__main__":
    main()
