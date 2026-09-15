#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Word 文本 → 命中明细（可选与 PDF 对齐得到页码）。

用户常常同时有扫描 PDF 和转好的 Word。Word 文本没有 OCR 错字，
所以用它做「原文」；但 Word 没有固定页码，所以页码要靠 PDF 来锚定——
把 Word 段落和 PDF 每页文本做模糊匹配，命中哪一页就把那一页的页码借过来。

用法:
  python3 word_scan.py --word <file.docx> --out <dir> --config book.json
                       [--lines <dir>/lines.jsonl]
"""
import argparse, difflib, json, os, re, subprocess, sys

from bti_console import force_utf8

def extract_paragraphs(path):
    """优先 pandoc，其次 macOS 自带的 textutil"""
    for cmd in (["pandoc", "-t", "plain", str(path)],
                ["textutil", "-convert", "txt", "-stdout", str(path)]):
        try:
            r = subprocess.run(cmd, capture_output=True, check=True)
            txt = r.stdout.decode("utf-8", "ignore")
            if txt.strip():
                return [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
        except Exception:
            continue
    raise SystemExit("无法读取 Word：需要 pandoc 或 macOS textutil")

def page_texts(lines_path):
    pages, order = {}, []
    for ln in open(lines_path, encoding="utf-8"):
        ln = ln.strip()
        if not ln: continue
        p = json.loads(ln)
        pages[p["page"]] = "".join(l["t"] for l in p["lines"])
        order.append(p)
    return pages, order

def calibrate(order):
    """复用 scan.py 的页眉页码众数法"""
    from collections import Counter
    pat = re.compile(r"^[\s\.,，。·\-—]*(\d{1,4})[\s\.,，。·\-—]*$")
    offs = Counter()
    for p in order:
        cand = None
        lines = [l for l in p["lines"] if l["t"].strip()]
        for l in lines[:3] + lines[-3:]:
            m = pat.match(l["t"].strip())
            if m and 1 <= int(m.group(1)) <= 9999:
                cand = int(m.group(1)); break
        if cand:
            offs[p["page"] - cand] += 1
    return offs.most_common(1)[0][0] if offs else 0

def main():
    force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--word", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    ap.add_argument("--lines")
    a = ap.parse_args()
    cfg = {"title": "未命名", "terms": [r"意识\s*形\s*态"], "term_label": ""}
    if a.config and os.path.exists(a.config):
        cfg.update(json.load(open(a.config, encoding="utf-8")))
    pats = [(t, re.compile(t)) for t in cfg["terms"]]
    paras = extract_paragraphs(a.word)
    os.makedirs(a.out, exist_ok=True)

    pages, order, offset = {}, [], 0
    if a.lines and os.path.exists(a.lines):
        pages, order = page_texts(a.lines)
        offset = calibrate(order)

    rows = []
    for i, text in enumerate(paras):
        found = [(n, m.group(0), m.start()) for n, pat in pats for m in pat.finditer(text)]
        if not found:
            continue
        pdf_page, printed = None, None
        if pages:
            probe = text[:60]
            best, best_r = None, 0.0
            for pno, ptxt in pages.items():
                r = difflib.SequenceMatcher(None, probe, ptxt[:400]).ratio()
                if r > best_r:
                    best, best_r = pno, r
            if best_r >= 0.3:
                pdf_page = best
                cand = best - offset
                printed = cand if cand > 0 else None
        pos, st0, sent = 0, found[0][2], text
        for sn in re.split(r"(?<=[。；！？])", text):
            if pos <= st0 < pos + len(sn):
                sent = sn; break
            pos += len(sn)
        rows.append({
            "类型": "正文", "书内页码": printed, "PDF页": pdf_page, "指向页码": None,
            "章": "", "节": "", "命中次数": len(found),
            "命中词": "、".join(sorted({f[0] for f in found})),
            "定位句": sent.strip(), "段落": text.strip(), "lines": [],
            "对齐置信度": round(best_r, 2) if pages else None,
        })
    for i, r in enumerate(rows, 1):
        r["序号"] = i
    json.dump(rows, open(os.path.join(a.out, "命中明细.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({"来源": "word", "段落数": len(paras), "命中段落": len(rows),
                      "有页码的": sum(1 for r in rows if r["书内页码"])},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
