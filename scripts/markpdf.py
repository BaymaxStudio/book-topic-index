#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF 高亮回写（PyMuPDF 后端，跨平台，替代 macOS markpdf.swift）。

用法: python3 markpdf.py <in.pdf> <annotations.json> <out.pdf>

annotations.json: [{"page":P,"rects":[[x,y,w,h],...],"label":"..."}]
x/y/w/h 归一化到 0~1、原点左上。PyMuPDF 同为左上原点，因此**不需要** swift 版里的 y 翻转。

- 文字版页：用 add_highlight_annot（贴合文字的标注）
- 扫描页（无文字层）：用 add_rect_annot 的半透明黄色方框，扫描件同样可见
不修改输入文件，始终另存新 PDF。
"""

import argparse
import json


def main():
    ap = argparse.ArgumentParser(description="PDF highlight via PyMuPDF")
    ap.add_argument("in_pdf")
    ap.add_argument("annotations")
    ap.add_argument("out_pdf")
    a = ap.parse_args()

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("缺少 PyMuPDF。安装：pip install pymupdf")

    with open(a.annotations, encoding="utf-8") as fh:
        anns = json.load(fh)

    doc = fitz.open(a.in_pdf)
    count = 0
    for entry in anns:
        try:
            pno = int(entry.get("page", 0))
        except (TypeError, ValueError):
            continue
        if pno < 1 or pno > doc.page_count:
            continue
        page = doc[pno - 1]
        W, H = page.rect.width, page.rect.height
        has_text = bool(page.get_text().strip())
        label = entry.get("label") or ""
        for r in entry.get("rects") or []:
            if len(r) < 4:
                continue
            x, y, w, h = float(r[0]) * W, float(r[1]) * H, float(r[2]) * W, float(r[3]) * H
            rect = fitz.Rect(x, y, x + w, y + h)
            try:
                annot = page.add_highlight_annot(rect) if has_text else page.add_rect_annot(rect)
            except Exception:  # noqa: BLE001 - 个别矩形异常不应中断整本
                continue
            if annot is None:
                continue
            try:
                annot.set_colors(stroke=(1, 1, 0), fill=(1, 1, 0))
            except Exception:  # noqa: BLE001 - highlight 标注只接受 stroke
                try:
                    annot.set_colors(stroke=(1, 1, 0))
                except Exception:
                    pass
            try:
                annot.set_opacity(0.35)
            except Exception:
                pass
            try:
                annot.set_border(width=0)
            except Exception:
                pass
            if label:
                try:
                    annot.set_info(content=label)
                except Exception:
                    pass
            try:
                annot.update()
            except Exception:
                pass
            count += 1

    doc.save(a.out_pdf)
    doc.close()
    print("annotation-rects=%d" % count)


if __name__ == "__main__":
    main()
