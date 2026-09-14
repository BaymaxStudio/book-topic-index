#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF → lines.jsonl（统一中间格式）。

自动判别两种 PDF：
  * 文字版：用 pdftotext -bbox 直接取词级坐标，精确、秒级完成
  * 扫描版：用 macOS Vision 框架 OCR（bin/ocrpdf），逐行带坐标

两者都产出同一 schema，下游 scan.py 无需关心来源：
  {"page":1,"w":W,"h":H,"lines":[{"t":文本,"x":0.08,"y":0.09,"w":0.82,"h":0.02,"c":1.0}, ...]}
坐标归一化到 0~1，原点左上（与 Vision 一致）。

用法:
  python3 pdf_lines.py --pdf <file.pdf> --out <dir> [--lang zh-Hans] [--dpi 300]
                       [--noise <book.json>] [--force ocr|text]
"""
import argparse, json, os, re, shutil, statistics as st, subprocess, sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
# 技能目录在分发/安装后常常是只读的，所以把"可写产物"（虚拟环境、编译出的二进制）
# 放到缓存目录，而不是塞回技能目录里。
BTI_HOME = Path(os.environ.get("BTI_HOME", os.path.expanduser("~/.cache/book-topic-index")))
BIN = BTI_HOME / "bin"
DEFAULT_NOISE = ["欢迎关注", "关注公众号", "扫码", "微信", "学习理论"]

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)

def load_noise(path):
    if path and os.path.exists(path):
        cfg = json.load(open(path, encoding="utf-8"))
        return cfg.get("noise", DEFAULT_NOISE)
    return DEFAULT_NOISE

def doc_pages(pdf):
    try:
        out = run(["pdfinfo", str(pdf)]).stdout.decode("utf-8", "ignore")
        return int(re.search(r"Pages:\s*(\d+)", out).group(1))
    except Exception:
        return 1

def probe_text_layer(pdf, noise, pages=3):
    """判断 PDF 是否真有文字层。

    只数字符是不够的：很多扫描件里嵌了一层"欢迎关注公众号"之类的水印文字，
    页页重复，字符数很容易越过阈值。所以再加一道重复性检测——
    如果每页抽出来的文字几乎一样，那它是水印，不是正文。

    返回 (有效字符数, 是否疑似水印)。
    """
    import difflib
    n = min(pages, doc_pages(pdf))          # 单页文档不要去抽第 2、3 页
    texts = []
    for i in range(1, n + 1):
        try:
            r = run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"])
        except Exception:
            break
        t = r.stdout.decode("utf-8", "ignore")
        for w in noise:
            t = t.replace(w, "")
        texts.append(re.sub(r"[\s\W_]+", "", t))
    total = sum(len(t) for t in texts)
    if total < 200:
        return total, False
    same = counted = 0
    for x, y in zip(texts, texts[1:]):
        if len(x) < 50 or len(y) < 50:      # 空页/极短页不参与水印判断
            continue
        counted += 1
        if difflib.SequenceMatcher(None, x, y).ratio() > 0.9:
            same += 1
    return total, (counted > 0 and same == counted)

def lines_from_textpdf(pdf, outdir, noise):
    """文字版：pdftotext -bbox → 词级坐标 → 合并成行"""
    r = run(["pdftotext", "-bbox", "-q", str(pdf), "-"])
    xhtml = r.stdout.decode("utf-8", "ignore")
    out = outdir / "lines.jsonl"
    n_pages = n_lines = 0
    with open(out, "w", encoding="utf-8") as f:
        for pm in re.finditer(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', xhtml, re.S):
            W, H, body = float(pm.group(1)), float(pm.group(2)), pm.group(3)
            n_pages += 1
            words = []
            for wm in re.finditer(
                r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
                body, re.S):
                x0, y0, x1, y1 = (float(wm.group(i)) for i in range(1, 5))
                txt = (wm.group(5).replace("&amp;", "&").replace("&lt;", "<")
                       .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
                if txt.strip():
                    words.append((y0, y1, x0, x1, txt))
            # 按纵向重叠合并成行；同时用横向间距切断分栏——
            # 双栏排版里左右栏常处在同一视觉行，只按 y 合并会把两栏粘成一句。
            words.sort(key=lambda w: (w[0], w[2]))
            cw = st.median([w[3] - w[2] for w in words]) if words else 1.0
            lines, cur = [], []
            for w in words:
                if not cur:
                    cur = [w]; continue
                top = min(x[0] for x in cur); bot = max(x[1] for x in cur)
                ov = min(bot, w[1]) - max(top, w[0])
                hh = min(bot - top, w[1] - w[0]) or 1
                gap = w[2] - max(x[3] for x in cur)
                if ov / hh > 0.5 and gap < cw * 2.5:
                    cur.append(w)
                else:
                    lines.append(cur); cur = [w]
            if cur:
                lines.append(cur)
            items = []
            for ln in lines:
                ln.sort(key=lambda w: w[2])
                buf = ""
                for w in ln:
                    if buf and re.search(r"[A-Za-z0-9]$", buf) and re.match(r"^[A-Za-z0-9]", w[4]):
                        buf += " "
                    buf += w[4]
                if noise and any(n in buf for n in noise):
                    continue
                x0 = min(w[2] for w in ln); x1 = max(w[3] for w in ln)
                y0 = min(w[0] for w in ln); y1 = max(w[1] for w in ln)
                items.append({"t": buf, "x": x0 / W, "y": y0 / H,
                              "w": (x1 - x0) / W, "h": (y1 - y0) / H, "c": 1.0})
            n_lines += len(items)
            f.write(json.dumps({"page": n_pages, "w": int(W), "h": int(H), "lines": items},
                               ensure_ascii=False) + "\n")
    return {"mode": "text", "pages": n_pages, "lines": n_lines, "path": str(out)}

def lines_from_ocr(pdf, outdir, lang, dpi):
    exe = BIN / "ocrpdf"
    if not exe.exists():
        build = SKILL_ROOT / "scripts" / "build_swift.sh"
        run(["bash", str(build)])
    pages = int(run(["pdfinfo", str(pdf)]).stdout.decode().split("Pages:")[1].split()[0])
    run([str(exe), str(pdf), str(outdir), "1", str(pages)])
    n_lines = sum(1 for _ in open(outdir / "lines.jsonl", encoding="utf-8"))
    return {"mode": "ocr", "pages": pages, "lines": n_lines,
            "path": str(outdir / "lines.jsonl")}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="zh-Hans")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--noise", help="book.json，用其中的 noise 列表")
    ap.add_argument("--force", choices=["ocr", "text"])
    a = ap.parse_args()

    pdf = Path(a.pdf)
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    noise = load_noise(a.noise)

    chars, watermark = probe_text_layer(pdf, noise)
    if a.force:
        mode = a.force
    else:
        mode = "text" if (chars >= 200 and not watermark) else "ocr"
    print("[probe] 有效字符=%d 疑似水印=%s → 走 %s 路径" % (chars, watermark, mode),
          file=sys.stderr)

    res = (lines_from_textpdf(pdf, outdir, noise) if mode == "text"
           else lines_from_ocr(pdf, outdir, a.lang, a.dpi))
    json.dump(res, open(outdir / "prepare.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    main()
