# -*- coding: utf-8 -*-
"""配置加载：config.json + 环境变量覆盖（数据库密码不进仓库）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG: Dict[str, Any] = {
    "database": {
        "access": "auto",                 # auto | direct | docker
        "host": "127.0.0.1",
        "port": 5432,
        "dbname": "stock",
        "user": "postgres",
        "password": "",                   # 建议留空，用环境变量 PGPASSWORD
        "docker_container": "my-postgres",
        "table": "stock_basic_cache",
        "name_column": "name",
        "code_column": "ts_code",
        "industry_column": "industry",
        "delisted_column": "dead_tag",
        "exclude_delisted": True,
        "order_by": "ts_code",
    },
    "build": {
        "phrase_rank": 1,                 # astock.txt 第二列（词频/优先级）
        "strip_star_in_word": False,      # 词面是否也去掉 *
        "exclude_st": False,              # 是否整条剔除 *ST 风险警示股
        "min_key_len": 2,
        "max_entries": 0,                 # 0 = 不限制
        "code_alias": False,              # 追加「股票代码 → 股票名称」短语
    },
    "tools": {
        "imewl_converter": "",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    """读取配置：默认 config.json，可用 --config 指定；环境变量优先级最高。"""
    cfg = DEFAULT_CONFIG
    candidate = Path(path) if path else REPO_ROOT / "config.json"
    if candidate.exists():
        with open(candidate, "r", encoding="utf-8") as fin:
            cfg = _deep_merge(cfg, json.load(fin))

    db = dict(cfg["database"])
    env_map = {
        "host": ("ASTOCK_DB_HOST", "PGHOST"),
        "port": ("ASTOCK_DB_PORT", "PGPORT"),
        "dbname": ("ASTOCK_DB_NAME", "PGDATABASE"),
        "user": ("ASTOCK_DB_USER", "PGUSER"),
        "password": ("ASTOCK_DB_PASSWORD", "PGPASSWORD"),
        "docker_container": ("ASTOCK_DB_CONTAINER",),
        "table": ("ASTOCK_DB_TABLE",),
    }
    for field, names in env_map.items():
        for name in names:
            val = os.environ.get(name)
            if val:
                db[field] = int(val) if field == "port" else val
                break
    cfg["database"] = db
    cfg["_config_path"] = str(candidate)
    cfg["_config_loaded"] = candidate.exists()
    return cfg
