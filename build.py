#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""astock-ime 顶层入口：python build.py [export|build|convert|all] [参数]

为了让仓库开箱即用，这里直接把 src/ 加进 sys.path，
不需要 pip install -e，也不需要设置 PYTHONPATH。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):                       # Windows 控制台中文
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001 - 重配置失败不影响主流程
            pass

from astock_ime.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
