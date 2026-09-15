#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验中间产物 schema：lines.jsonl 与 annotations.json（供 CI / 人工自检）。

    python3 scripts/check_schema.py <outdir>
"""
import json
import sys
from pathlib import Path

from bti_console import force_utf8

REQ_LINE = {"t", "x", "y", "w", "h", "c"}


def main():
    force_utf8()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    lines_file = out / "lines.jsonl"
    annot_file = out / "annotations.json"
    errors = []

    n_pages = n_lines = 0
    if not lines_file.exists():
        errors.append("缺少 %s" % lines_file)
    else:
        for i, raw in enumerate(lines_file.read_text(encoding="utf-8").splitlines(), 1):
            raw = raw.strip()
            if not raw:
                continue
            p = json.loads(raw)
            for k in ("page", "w", "h", "lines"):
                if k not in p:
                    errors.append("lines.jsonl 第 %d 行缺字段 %s" % (i, k))
            n_pages += 1
            for ln in p.get("lines", []):
                n_lines += 1
                missing = REQ_LINE - set(ln)
                if missing:
                    errors.append("lines.jsonl 第 %d 行 line 缺字段 %s" % (i, missing))
                for k in ("x", "y", "w", "h", "c"):
                    v = ln.get(k)
                    if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.5):
                        errors.append("lines.jsonl 第 %d 行 %s 越界：%r" % (i, k, v))
                        break

    if not annot_file.exists():
        errors.append("缺少 %s" % annot_file)
    else:
        anns = json.loads(annot_file.read_text(encoding="utf-8"))
        if not isinstance(anns, list):
            errors.append("annotations.json 不是数组")
        else:
            for a in anns:
                if "page" not in a or "rects" not in a:
                    errors.append("annotations.json 条目缺 page/rects")

    print("lines.jsonl: %d 页 / %d 行" % (n_pages, n_lines))
    if errors:
        print("SCHEMA FAIL:")
        for e in errors[:20]:
            print("  -", e)
        sys.exit(1)
    print("SCHEMA OK")


if __name__ == "__main__":
    main()
