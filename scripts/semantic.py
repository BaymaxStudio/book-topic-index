#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tier 3：语义候选生成器（启发式，交给 Agent 逐条判定）。

为什么不做自动判定：语义"是否在讲这个主题"是判断，不是枚举。
一旦把判断混进字面层，就会毁掉"零漏检审计"这个可信度基石。
所以这里只负责**把候选缩小到可控规模**，判定权交回 Agent，并单独输出一个
"待确认"清单，绝不写进主索引。

候选来源两条：
  1) 信号词：出现 config.signals 里任一表述的段落（如 上层建筑/社会意识/阶级…）
  2) 邻段：与字面命中段同页相邻的段落（概念论述常成段出现）

用法:
  python3 semantic.py --lines <dir>/lines.jsonl --hits <dir>/命中明细.json \
                      --out <dir> --config book.json [--per-page 3]
"""
import argparse, importlib.util, json, os, re
from collections import defaultdict
from pathlib import Path

def load_scan():
    spec = importlib.util.spec_from_file_location(
        "bti_scan", str(Path(__file__).resolve().parent / "scan.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--hits", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    ap.add_argument("--per-page", type=int, default=3, help="每页最多保留几个候选")
    a = ap.parse_args()

    cfg = {"terms": [r"意识\s*形\s*态"], "term_label": "关键词"}
    if a.config and os.path.exists(a.config):
        cfg.update(json.load(open(a.config, encoding="utf-8")))
    noise_re = re.compile("|".join(map(re.escape, cfg.get("noise", [])))) if cfg.get("noise") else re.compile(r"(?!)")
    sig_pats = [re.compile(s) for s in cfg.get("signals", [])]

    scan = load_scan()
    pages = scan.load_lines(a.lines)
    hits = json.load(open(a.hits, encoding="utf-8"))
    hit_keys = {(h["PDF页"], h.get("段落", "")) for h in hits}
    hit_pages = defaultdict(list)
    for h in hits:
        hit_pages[h["PDF页"]].append(h.get("段落", ""))

    cands = []
    for p in pages:
        blocks = scan.segment(p, noise_re)["blocks"]
        paras = [b for b in blocks if b["kind"] == "para"]
        page_c = []
        for i, b in enumerate(paras):
            t = b["text"].strip()
            if (p["page"], t) in hit_keys:
                continue
            reasons = []
            for sp in sig_pats:
                m = sp.search(t)
                if m:
                    reasons.append("信号词:" + m.group(0))
                    break
            # 邻段：与命中段相邻
            if not reasons and hit_pages.get(p["page"]):
                for j in (i - 1, i + 1):
                    if 0 <= j < len(paras) and (p["page"], paras[j]["text"].strip()) in hit_keys:
                        reasons.append("邻段")
                        break
            if reasons:
                page_c.append({"PDF页": p["page"], "段落": t, "候选理由": "、".join(reasons),
                               "lines": b["lines"]})
        cands.extend(page_c[:a.per_page])

    os.makedirs(a.out, exist_ok=True)
    json.dump(cands, open(os.path.join(a.out, "语义候选.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    by_page = defaultdict(list)
    for c in cands:
        by_page[c["PDF页"]].append(c)
    md = ["# Tier 3 语义候选（待人工/Agent 判定）", "",
          "> 这一层是**启发式召回**，不是结论。请逐条判断是否真的在讲「%s」，" % cfg.get("term_label", "该主题"),
          "> 采纳的条目应单独列为「语义相关（待确认）」，**不得混入主索引的页码表**。", "",
          "候选总数 **%d** 条，来自 %d 页。" % (len(cands), len(by_page)), ""]
    for pg in sorted(by_page):
        md.append("## 第 %s 页" % pg)
        for c in by_page[pg]:
            md.append("- （%s）%s" % (c["候选理由"], c["段落"][:160]))
        md.append("")
    open(os.path.join(a.out, "语义候选.md"), "w", encoding="utf-8").write("\n".join(md))
    print(json.dumps({"Tier3候选数": len(cands), "覆盖页数": len(by_page),
                      "信号词数": len(sig_pats)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
