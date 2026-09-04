# -*- coding: utf-8 -*-
"""股票名称数据获取层。

数据源从「直接调用 Tushare 接口」改为「读本地数据库」：
  · 库里 stock_basic_cache 表由同步任务每周三 / 周五全量刷新；
  · 本工具只 SELECT，不写库，也不碰任何外部接口，可以随便跑。

两种访问方式：
  direct —— psycopg2 直连 127.0.0.1:5432
  docker —— docker exec 进容器里跑 psql（宿主机端口没映射/连不上时的兜底）
  auto   —— 先 direct，失败再 docker
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

NAME_COL = "name"


class DataSourceError(RuntimeError):
    pass


# ---------------------------------------------------------------- SQL 构造
def build_sql(db: Dict[str, Any]) -> str:
    """根据配置拼出取名称的 SELECT（可用 sql/names.sql 模板做参考/覆盖）。"""
    table = db["table"]
    cols = [db.get("code_column", "ts_code"), db.get(NAME_COL, "name")]
    industry = db.get("industry_column")
    if industry:
        cols.append(industry)

    where: List[str] = [f"{cols[1]} IS NOT NULL", f"btrim({cols[1]}) <> ''"]
    delisted = db.get("delisted_column")
    if delisted and db.get("exclude_delisted", True):
        where.append(f"COALESCE({delisted}, 0) = 0")
    extra = (db.get("where") or "").strip()
    if extra:
        where.append(extra)

    sql = f"SELECT {', '.join(cols)} FROM {table}"
    sql += "\nWHERE " + "\n  AND ".join(where)
    if db.get("order_by"):
        sql += f"\nORDER BY {db['order_by']}"
    return sql


def build_hot_sql(db: Dict[str, Any], days: int = 20) -> str:
    """近 N 个交易日成交额（用于给热门股更高的词频/排序）。"""
    hot = db.get("hot") or {}
    table = hot.get("table", "a_share_daily")
    code_col = hot.get("code_column", "code")
    amount_col = hot.get("amount_column", "amount")
    date_col = hot.get("date_column", "date")
    return f"""
WITH recent AS (
  SELECT {code_col} AS code, sum({amount_col}) AS amount
  FROM {table}
  WHERE {date_col} >= (
      SELECT max({date_col}) - ({days} * 2) FROM {table}
  )
  GROUP BY {code_col}
)
SELECT code, amount FROM recent ORDER BY amount DESC NULLS LAST
""".strip()


# ---------------------------------------------------------------- direct 模式
def fetch_direct(db: Dict[str, Any], sql: str, columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    import psycopg2  # 延迟导入：只做 CSV 模式时不需要装驱动

    conn = psycopg2.connect(
        host=str(db.get("host", "127.0.0.1")),
        port=int(db.get("port", 5432)),
        dbname=db.get("dbname", "stock"),
        user=db.get("user", "postgres"),
        password=db.get("password", "") or None,
        connect_timeout=int(db.get("connect_timeout", 5)),
    )
    try:
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


# ---------------------------------------------------------------- docker 模式
def fetch_docker(db: Dict[str, Any], sql: str,
                 columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """docker exec + psql 取数（psql -t -A -F<TAB> 输出，列名由调用方告知）。"""
    container = db.get("docker_container") or "my-postgres"
    if not shutil.which("docker"):
        raise DataSourceError("未找到 docker 命令，无法使用 docker 模式")

    cmd = [
        "docker", "exec", "-i", container,
        "psql", "-v", "ON_ERROR_STOP=1", "-t", "-A", "-F", "\t", "--pset", "footer=off",
        "-U", str(db.get("user", "postgres")),
        "-d", str(db.get("dbname", "stock")),
        "-c", sql,
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise DataSourceError(
            "docker psql 执行失败：" + proc.stderr.decode("utf-8", "ignore").strip()[:300]
        )
    text = proc.stdout.decode("utf-8", "replace")
    cols = list(columns or []) or [db.get("code_column", "ts_code"), NAME_COL]
    if not columns and db.get("industry_column"):
        cols.append(db["industry_column"])
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        rows.append(dict(zip(cols, (p.strip() for p in parts))))
    return rows


# ---------------------------------------------------------------- 对外接口
def fetch_names(db_cfg: Dict[str, Any], verbose: bool = True) -> List[Dict[str, Any]]:
    """返回 [{'ts_code':..., 'name':..., 'industry':...}, ...]"""
    sql = build_sql(db_cfg)
    columns = [db_cfg.get("code_column", "ts_code"), db_cfg.get(NAME_COL, "name")]
    if db_cfg.get("industry_column"):
        columns.append(db_cfg["industry_column"])
    mode = (db_cfg.get("access") or "auto").lower()
    if verbose:
        print("[db] 访问方式:", mode)
        print("[db] SQL:\n" + "\n".join("      " + l for l in sql.splitlines()))

    errors: List[str] = []
    for engine in _engines(mode):
        try:
            rows = engine(db_cfg, sql, columns)
            if not rows:
                raise DataSourceError("查询结果为空")
            if verbose:
                print(f"[db] 取到 {len(rows)} 条股票名称")
            return rows
        except Exception as exc:  # noqa: BLE001 - 需要把所有失败原因汇总给用户
            errors.append(f"{type(exc).__name__}: {exc}")
            if verbose:
                print(f"[db] 该方式失败：{errors[-1]}")
    raise DataSourceError(
        "无法从数据库获取股票名称，请检查 config.json 或数据库服务：\n  - "
        + "\n  - ".join(errors)
    )


def _engines(mode: str):
    if mode == "direct":
        return [fetch_direct]
    if mode == "docker":
        return [fetch_docker]
    return [fetch_direct, fetch_docker]          # auto


def fetch_hot_amounts(db_cfg: Dict[str, Any], days: int = 20) -> Optional[Dict[str, float]]:
    """取近 N 日成交额排名；表不存在/失败时返回 None（不影响主流程）。"""
    sql = build_hot_sql(db_cfg, days=days)
    for engine in _engines((db_cfg.get("access") or "auto").lower()):
        try:
            rows = engine(db_cfg, sql, ["code", "amount"])
            if rows and "code" in rows[0]:
                return {str(r["code"]): float(r.get("amount") or 0) for r in rows}
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------------------------------------------------------- CSV 通道
def read_csv_rows(path: str | Path) -> List[Dict[str, Any]]:
    """离线模式 / CI：从 CSV（ts_code,name,industry）读同样的数据。"""
    p = Path(path)
    if not p.exists():
        raise DataSourceError(f"CSV 不存在：{p}")
    with open(p, "r", encoding="utf-8-sig", newline="") as fin:
        rows = []
        for row in csv.DictReader(fin):
            name = (row.get(NAME_COL) or "").strip()
            if name:
                rows.append({
                    "ts_code": (row.get("ts_code") or "").strip(),
                    NAME_COL: name,
                    "industry": (row.get("industry") or "").strip(),
                })
        return rows


def write_csv_rows(path: str | Path, rows: List[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["ts_code", NAME_COL, "industry"]
    with open(p, "w", encoding="utf-8-sig", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    print(f"[db] 已导出快照：{p}（{len(rows)} 行）")
