#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lines.jsonl → 命中明细（页码 + 原文 + 行坐标）。

这是整条流水线的核心：把 OCR/文本抽取出来的行，切回段落，
校准页码偏移，再按配置的检索词命中。

用法:
  python3 scan.py --lines <dir>/lines.jsonl --out <dir> --config book.json
"""
import argparse, json, os, re, csv, statistics as st
from collections import Counter, OrderedDict

DEFAULT_NOISE = ["欢迎关注", "关注公众号", "扫码", "微信", "学习理论"]
DEFAULT_TERMS = [r"意识\s*形\s*态"]

PAGENUM = re.compile(r"^[\s\.,，。·\-—]*(\d{1,4})[\s\.,，。·\-—]*$")
CHAP = re.compile(r"^第[一二三四五六七八九十百零\d]+章")
SEC  = re.compile(r"^第[一二三四五六七八九十百零\d]+节")
NUMHEAD = re.compile(r"^\d{1,2}\s*[、.．]\s*\S")   # 限 1–2 位，避免把 "2023." 这类小数当标题
CNHEAD = re.compile(r"^[一二三四五六七八九十]+\s*[、.．]\s*\S")
PARENHEAD = re.compile(r"^[（(][一二三四五六七八九十\d]+[）)]")
LEADER = re.compile(r"[.·•…\s]{2,}(\d{1,4})\s*$")

def load_cfg(path):
    cfg = {"title": "未命名", "edition": "", "author": "", "term_label": "",
           "terms": DEFAULT_TERMS, "noise": DEFAULT_NOISE}
    if path and os.path.exists(path):
        cfg.update(json.load(open(path, encoding="utf-8")))
    return cfg

def load_lines(path):
    pages = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                pages.append(json.loads(ln))
    return pages

def is_heading(t, h, mh):
    t = t.strip()
    if CHAP.match(t) or SEC.match(t) or NUMHEAD.match(t) or PARENHEAD.match(t):
        return True
    if CNHEAD.match(t) and len(t) <= 20:
        return True
    # 靠行高判标题要保守：带引号/着重号的正文行 bbox 会偏高，长度 30 以内就会被
    # 误判成标题，从而切断段落、造成跨行关键词漏检。标题通常很短且不以句读收尾。
    if h > mh * 1.25 and len(t) <= 16 and not t.endswith(("。", "，", "、", "；", "：", "）")):
        return True
    return False

def segment(page, noise_re):
    lines = [l for l in page["lines"]
             if l["t"].strip() and not noise_re.search(l["t"]) and l["c"] >= 0.3]
    if not lines:
        return {"blocks": [], "printed": None, "header": "", "toc": False,
                "nums": [], "nlines": 0}
    mh = st.median([l["h"] for l in lines])
    body = [l for l in lines if 0.085 <= l["y"] <= 0.955] or lines

    def pnum(t):
        m = PAGENUM.match(t.strip())
        if m and 1 <= int(m.group(1)) <= 9999:
            return int(m.group(1))
        return None

    # 目录页判定。OCR 常把「目录」页眉拆成「目」「录」两行或识成「日.录」，
    # 而且页码未必贴在右边缘、点线也可能只剩单个「•」——所以不能只认页眉文字或
    # 右对齐页码，得看整页的版面特征：满页短条目 + 独立数字行 + 点线。
    nums = [(l["y"], pnum(l["t"])) for l in lines if l["x"] > 0.78 and pnum(l["t"])]
    n_num   = sum(1 for l in lines if pnum(l["t"]))
    n_dot   = sum(1 for l in lines if re.search(r"[.·•…]", l["t"]))
    n_short = sum(1 for l in lines if len(l["t"].strip()) <= 25)
    head = "".join(l["t"] for l in lines[:3])
    named = any(k in head for k in ("目录", "录目", "目録", "日录"))
    toc = named or (n_num >= 5 and n_dot >= 3)
    toc_like = toc or (n_num >= 4 and n_dot >= 2 and n_short >= 8)

    printed = None
    if not toc:
        for l in lines[:3] + lines[-3:]:
            v = pnum(l["t"])
            if v:
                printed = v; break

    header = ""
    for l in lines:
        if l["y"] + l["h"] < 0.085 and (SEC.search(l["t"]) or CHAP.search(l["t"])):
            header = l["t"].strip(); break
        if l["y"] < 0.085 and l["x"] > 0.30 and len(l["t"].strip()) <= 40 \
           and not PAGENUM.match(l["t"].strip()):
            header = l["t"].strip(); break

    # 左边界用众数而不是最小值。一条脚注标记或杂线（x 远小于正文）会把 min
    # 拉到最左，于是整页正文行都被判成"首行缩进"，段落全被打散、跨行关键词接不回来。
    xs = [round(l["x"], 2) for l in body]
    pageLeft = Counter(xs).most_common(1)[0][0] if xs else 0.08
    gaps = [b["y"] - (a["y"] + a["h"]) for a, b in zip(body, body[1:])
            if b["y"] - (a["y"] + a["h"]) > 0]
    paraGap = max((st.median(gaps) if gaps else 0.0045) * 1.7, 0.0075)

    blocks, cur = [], []
    def flush():
        if cur:
            blocks.append({"kind": "para",
                           "text": "".join(x["t"] for x in cur),
                           "lines": [dict(x) for x in cur]})
            cur.clear()
    for l in body:
        txt = l["t"].strip()
        if PAGENUM.match(txt) and (l["y"] < 0.12 or l["y"] > 0.9):
            continue
        if is_heading(txt, l["h"], mh):
            flush()
            blocks.append({"kind": "head", "text": txt, "lines": [dict(l)]})
            continue
        if not cur:
            cur.append(l); continue
        prev = cur[-1]
        gap = l["y"] - (prev["y"] + prev["h"])
        indented = (l["x"] - pageLeft) > 0.026
        # 上一行本身就偏出正文栏（OCR 给错 bbox，或页边的眉注），不要把它当段落开头
        displaced = abs(prev["x"] - pageLeft) > 0.14
        if gap > paraGap or indented or displaced:
            flush()
        cur.append(l)
    flush()
    return {"blocks": blocks, "printed": printed, "header": header,
            "toc": toc, "toc_like": toc_like, "nums": nums, "nlines": len(lines)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    noise_re = re.compile("|".join(map(re.escape, cfg["noise"]))) if cfg["noise"] else None
    if noise_re is None:
        noise_re = re.compile(r"(?!)")
    pats = [(t, re.compile(t)) for t in cfg["terms"]]
    # Tier 2：同义/派生表述（不含字面词的相关说法），单独一层、单独标注
    rel_pats = [(t, re.compile(t)) for t in cfg.get("related", [])]
    pages = load_lines(a.lines)
    os.makedirs(a.out, exist_ok=True)

    parsed, offs = [], Counter()
    for p in pages:
        s = segment(p, noise_re); s["page"] = p["page"]; parsed.append(s)
        if s["printed"] and not s["toc"]:
            offs[s["page"] - s["printed"]] += 1
    offset = offs.most_common(1)[0][0] if offs else 0

    # 目录页是成片的。万一个别页因 OCR 碎片漏判，就向相邻的同构页扩张——
    # 漏判的后果很严重：目录条目会被当作正文标题，把章节上下文污染到正文里去。
    for _ in range(2):
        for i, s in enumerate(parsed):
            if s["toc"]:
                continue
            nb = [parsed[j] for j in (i - 1, i + 1) if 0 <= j < len(parsed)]
            if any(x["toc"] for x in nb) and s.get("toc_like"):
                s["toc"] = True

    CHAPTOK = re.compile(r"第[一二三四五六七八九十百零\d]+章")
    SECTOK  = re.compile(r"第[一二三四五六七八九十百零\d]+节")
    ctx = {"tok": "", "ch": "", "sec": ""}

    def upd(t):
        t = re.sub(r"^\s*\d+\s*", "", t.strip())
        t = re.sub(r"\s+\d{1,4}\s*$", "", t).strip()
        mt, ms = CHAPTOK.search(t), SECTOK.search(t)
        if mt:
            if ctx["tok"] and mt.group(0) != ctx["tok"]:
                ctx["sec"] = ""          # 换章即清空上一章的节，避免串页
            ctx["tok"] = mt.group(0); ctx["ch"] = t
        if ms:
            ctx["sec"] = t
        return mt, ms

    rows = []
    for s in parsed:
        if s["header"] and not s["toc"]:
            upd(s["header"])
        for blk in s["blocks"]:
            t = blk["text"]
            head = blk["kind"] == "head"
            if head and not s["toc"]:
                upd(t)
            cur_chapter, cur_section = ctx["ch"], ctx["sec"]
            lit = [(m.group(0), m.start()) for _, pat in pats for m in pat.finditer(t)]
            rel = [(m.group(0), m.start()) for _, pat in rel_pats for m in pat.finditer(t)]
            if not lit and not rel:
                continue
            # 字面命中优先：同一段里两种都有时，按字面层记录，避免一稿两投
            # 计数只数本层：把两层混加会让字面层数字对不上审计。
            tier, found = ("字面", lit) if lit else ("相关", rel)
            pg = None if s["toc"] else s["printed"]
            if pg is None and not s["toc"]:
                cand = s["page"] - offset
                pg = cand if cand > 0 else None
            pos, st0, sent = 0, found[0][1], t
            for sn in re.split(r"(?<=[。；！？])", t):
                if pos <= st0 < pos + len(sn):
                    sent = sn; break
                pos += len(sn)
            ref = None
            if s["toc"] and s["nums"]:
                yy = blk["lines"][0]["y"]
                best = min(s["nums"], key=lambda p: abs(p[0] - yy))
                if abs(best[0] - yy) < 0.012:
                    ref = best[1]
            rows.append({
                "类型": "目录" if s["toc"] else ("标题" if head else "正文"),
                "书内页码": pg, "PDF页": s["page"], "指向页码": ref,
                "章": cur_chapter, "节": cur_section,
                "命中次数": len(found),
                "层级": tier,
                "命中词": "、".join(sorted({f[0].replace(" ", "").replace("\u3000", "")
                                             for f in found})),   # 存实际命中文本，而非正则模式
                "定位句": sent.strip(), "段落": t.strip(),
                "lines": blk["lines"],
            })

    seen, dedup = set(), []
    for r in rows:
        key = (r["PDF页"], r["段落"])
        if key in seen: continue
        seen.add(key); dedup.append(r)
    for i, r in enumerate(dedup, 1):
        r["序号"] = i

    cols = ["序号", "类型", "层级", "书内页码", "PDF页", "指向页码", "章", "节",
            "命中次数", "命中词", "定位句", "段落"]
    with open(os.path.join(a.out, "命中明细.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in dedup:
            w.writerow({k: r.get(k, "") for k in cols})
    json.dump(dedup, open(os.path.join(a.out, "命中明细.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump([{"page": r["PDF页"],
                "rects": [[l["x"], l["y"], l["w"], l["h"]] for l in r["lines"]],
                "label": "%s p.%s" % (r["类型"], r["书内页码"])} for r in dedup],
              open(os.path.join(a.out, "annotations.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    body = [r for r in dedup if r["类型"] != "目录"]
    toc  = [r for r in dedup if r["类型"] == "目录"]
    total_occ = sum(r["命中次数"] for r in dedup if r.get("层级") == "字面")
    total_rel = sum(r["命中次数"] for r in dedup if r.get("层级") == "相关")
    by_page = OrderedDict()
    for r in body:
        by_page.setdefault(r["书内页码"], []).append(r)

    def mark(x):
        out = x
        for n, pat in pats:
            out = pat.sub(lambda m: "**" + m.group(0).replace(" ", "") + "**", out)
        return out

    title = cfg["title"] + ("（%s）" % cfg["edition"] if cfg["edition"] else "")
    md = ["# 《%s》" % title, "## 「%s」相关内容索引\n" % cfg["term_label"],
          "- 命中 **%d** 段，分布于 **%d** 页；全书出现 **%d** 处；目录条目 %d 条"
          % (len(body), len(by_page), total_occ, len(toc)),
          "- 页码为书内印刷页码，⟨PDF N⟩ 为电子文件物理页",
          "- 校准偏移：PDF页 − 书内页码 = %d\n" % offset, "---\n"]
    for pg, rs in by_page.items():
        r0 = rs[0]
        md.append("### 第 %s 页 ⟨PDF %s⟩" % (pg, r0["PDF页"]))
        md.append("> %s %s\n" % (r0["章"], r0["节"]) if (r0["章"] or r0["节"]) else "")
        for r in rs:
            md.append(("（标题）" if r["类型"] == "标题" else "") + mark(r["段落"]) + "\n")
    if toc:
        md.append("---\n\n## 目录中的相关条目\n")
        md.append("| 目录条目 | 指向页码 | 位置(PDF) |"); md.append("|---|---|---|")
        for r in toc:
            clean = LEADER.sub("", r["段落"]).strip()
            md.append("| %s | %s | p.%s |" % (mark(clean), r["指向页码"] or "—", r["PDF页"]))
    open(os.path.join(a.out, "报告.md"), "w", encoding="utf-8").write("\n".join(md))

    votes = offs.most_common(3)
    n_lit = len([r for r in body if r.get("层级") == "字面"])
    n_rel = len([r for r in body if r.get("层级") == "相关"])
    stats = {"title": title, "author": cfg["author"], "term_label": cfg["term_label"],
             "字面命中段落": n_lit, "相关词命中段落": n_rel,
             "相关词出现": total_rel,
             "offset": offset, "正文段落": len(body),
             "正文页数": len([k for k in by_page if k is not None]),
             "无页码条目": len(by_page.get(None, [])),
             "目录条目": len(toc), "全书出现": total_occ,
             "正文页列表": sorted(k for k in by_page if k),
             "偏移投票": votes,
             "校准证据": ("无" if not votes else
                          ("众数 %d，%d/%d 页一致" % (offset, votes[0][1], sum(v for _, v in votes))))}
    json.dump(stats, open(os.path.join(a.out, "统计.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))

if __name__ == "__main__":
    main()
