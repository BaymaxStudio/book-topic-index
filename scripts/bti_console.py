#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""让中文在 Windows 控制台也能正常打印。

Windows 默认标准输出编码是 cp936 / cp1252，直接 print 中文会抛
UnicodeEncodeError。所有入口脚本在 main() 开头调用 force_utf8()，
把 stdout/stderr 切到 UTF-8（失败也不影响主流程）。
"""
import sys


def force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
