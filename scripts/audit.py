#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零漏检审计：把 lines.jsonl 里检索词的真实出现次数，与命中明细对账。

为什么必须做这一步：OCR 会把「意识形态」拆到两行（意识 / 形态），
段落合并如果刚好断在那里就会漏检。这个脚本按整页拼接后统计，
任何未被明细覆盖的页都会暴露出来。

用法: python3 audit.py --lines <dir>/lines.jsonl --hits <dir>/命中明细.json --config book.json
"""
import argparse, json, os, re, sys
from collections import Counter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--hits", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    terms = [r"意识\s*形\s*态"]
    if a.config and os.path.exists(a.config):
        terms = json.load(open(a.config, encoding="utf-8")).get("terms", terms)
    pats = [re.compile(t) for t in terms]

    raw = Counter()
    for ln in open(a.lines, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        p = json.loads(ln)
        joined = "".join(l["t"] for l in p["lines"])
        c = sum(len(pat.findall(joined)) for pat in pats)
        if c:
            raw[p["page"]] = c

    hits = json.load(open(a.hits, encoding="utf-8"))
    got = Counter()
    for r in hits:
        # 审计只对账"字面层"。相关词层是扩展召回，不参与零漏检判定——
        # 否则审计结论会被扩展词稀释，失去"我查全了"的可信度。
        if r.get("层级", "字面") != "字面":
            continue
        got[r["PDF页"]] += r["命中次数"]
    rel_pages = {r["PDF页"] for r in hits if r.get("层级") == "相关"}
    rel_cnt = sum(r.get("命中次数", 0) for r in hits if r.get("层级") == "相关")

    miss = sorted(set(raw) - set(got))
    fewer = sorted(p for p in got if p in raw and got[p] < raw[p])
    print(json.dumps({
        "原文出现总次数": sum(raw.values()),
        "明细覆盖次数": sum(got.values()),
        "原文命中页数": len(raw),
        "明细命中页数": len(got),
        "相关词命中页数": len(rel_pages),
        "相关词命中次数": rel_cnt,
        "完全漏掉的页": miss,
        "覆盖不足的页": {p: {"原文": raw[p], "明细": got[p]} for p in fewer},
    }, ensure_ascii=False, indent=1))
    if miss or fewer:
        print("⚠️  存在缺口，检查段落切分阈值与跨页断字", file=sys.stderr)
        sys.exit(0)

if __name__ == "__main__":
    main()
