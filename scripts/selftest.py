#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""程序化验收：跑一次完整流水线，并对关键数字断言（可复现，不靠肉眼）。

用法:
    python3 scripts/selftest.py --pdf <pdf> --config <book.json> --out <dir> \
        [--ocr auto|vision|rapid] [--dpi 300] \
        [--expect-offset -40] [--expect-pages 42,53,54,55,69,73] \
        [--expect-segments 12] [--expect-occurrences 33]

不传 --expect-* 时只跑流水线并打印 统计.json 摘要。
退出码非 0 表示有断言未通过——可直接接进 CI。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ocr", default="auto", choices=["auto", "vision", "rapid"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--expect-offset", type=int)
    ap.add_argument("--expect-pages")
    ap.add_argument("--expect-segments", type=int)
    ap.add_argument("--expect-occurrences", type=int)
    a = ap.parse_args()

    subprocess.run([sys.executable, str(HERE / "run_pipeline.py"), a.pdf, a.config, a.out,
                    "--ocr", a.ocr, "--dpi", str(a.dpi)], check=True)

    out = Path(a.out)
    stats = json.load(open(out / "统计.json", encoding="utf-8"))
    hits = json.load(open(out / "命中明细.json", encoding="utf-8"))
    segs = len(hits)
    occ = sum(int(r.get("命中次数") or 1) for r in hits)
    pages = sorted({int(r["书内页码"]) for r in hits if r.get("书内页码") is not None})

    checks = []

    def check(name, ok, evidence):
        checks.append((name, bool(ok), evidence))

    if a.expect_offset is not None:
        check("页码偏移 == %d" % a.expect_offset, stats.get("offset") == a.expect_offset,
              "offset=%s" % stats.get("offset"))
    if a.expect_pages:
        want = [int(x) for x in a.expect_pages.split(",") if x.strip()]
        check("命中页集合 == %s" % want, pages == want, "pages=%s" % pages)
    if a.expect_segments is not None:
        check("命中段落 == %d" % a.expect_segments, segs == a.expect_segments, "segments=%d" % segs)
    if a.expect_occurrences is not None:
        check("全书出现 == %d" % a.expect_occurrences, occ == a.expect_occurrences,
              "occurrences=%d" % occ)
    for f in ("交付/索引.docx", "交付/标注版.pdf"):
        check("产出 %s" % f, (out / f).exists(), str(out / f))

    print("\n=== selftest (%s) ===" % a.ocr)
    for name, ok, ev in checks:
        print("%s  %s  (%s)" % ("PASS" if ok else "FAIL", name, ev))
    passed = sum(1 for _, ok, _ in checks if ok)
    print("summary: %d/%d passed" % (passed, len(checks)))
    if checks and passed != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
