# -*- coding: utf-8 -*-
"""词条构建 + 各输入法文本格式输出。

中间产物 ``build/astock.txt``（旧流程沿用，行格式 ``编码<TAB>词频<TAB>词语``）
既能直接被深蓝词库转换吃进去，也是所有文本格式的来源。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .pinyin import initials, is_valid_key, keyword_word, strip_star, STAR_CHARS


@dataclass(frozen=True)
class Entry:
    key: str          # 拼音首字母编码（小写、无 *）
    freq: int         # 词频 / 优先级（越大越靠前；默认 1）
    word: str         # 上屏词面（股票名称）
    code: str = ""    # 股票代码，仅用于调试与 code_alias
    industry: str = ""


# 深蓝 -F 参数：1=拼音所在列 / 3=词所在列 / 2=词频所在列，其后是分隔符与列含义提示。
# 字段分隔符必须传**真实制表符**：深蓝 3.4 已不再解析 "\t" 字面转义，
# 传反斜杠会静默导入 0 条（Git-Bash 里手写命令要用 $'\t' 或 printf 生成）。
SELF_FORMAT = "132 " + chr(9) + "nyyy"


# ------------------------------------------------------------------ 构建
def build_entries(
    rows: Sequence[Dict[str, Any]],
    *,
    name_field: str = "name",
    code_field: str = "ts_code",
    industry_field: str = "industry",
    rank: int = 1,
    min_key_len: int = 2,
    strip_star_in_word: bool = False,
    exclude_st: bool = False,
    max_entries: int = 0,
    code_alias: bool = False,
    star_variants: bool = True,
    amounts: Optional[Dict[str, float]] = None,
) -> List[Entry]:
    """数据库行 → 词条列表（已去重、已按规则生成编码）。

    ``star_variants``：对 ``*ST`` 这类“词面以符号开头”的股票，额外再放一条
    剔掉前导符号的同编码词条（``stml`` → ``*ST美丽`` + ``ST美丽``）。
    因为很多输入法的批量导入会把前导符号条目整行丢弃，多一条兵分两路。
    """
    entries: List[Entry] = []
    stats = {"total": len(rows), "no_name": 0, "bad_key": 0, "excluded_st": 0,
             "dup": 0, "code_alias": 0, "star_variant": 0}
    seen = set()

    def add(entry: Entry) -> None:
        sig = (entry.key, entry.word)
        if sig in seen:
            return
        seen.add(sig)
        entries.append(entry)

    freq_map = _freq_map(amounts) if amounts else {}

    for row in rows:
        name = str(row.get(name_field) or "").strip()
        if not name:
            stats["no_name"] += 1
            continue
        if exclude_st and ("ST" in name.upper().replace("*", "")):
            stats["excluded_st"] += 1
            continue

        key = initials(name)
        if not is_valid_key(key, min_len=min_key_len):
            stats["bad_key"] += 1
            continue

        word = keyword_word(name, strip_star_in_word=strip_star_in_word)
        code = str(row.get(code_field) or "").strip()
        industry = str(row.get(industry_field) or "")
        freq = int(freq_map.get(code, rank))

        before = len(entries)
        add(Entry(key=key, freq=freq, word=word, code=code, industry=industry))
        if len(entries) == before:
            stats["dup"] += 1

        # 兵分两路：*ST美丽 之外再给一条 ST美丽
        if star_variants:
            safe = word.lstrip(_LEADING_PUNCT)
            if safe and safe != word:
                cnt = len(entries)
                add(Entry(key=key, freq=freq, word=safe, code=code, industry=industry))
                if len(entries) > cnt:
                    stats["star_variant"] += 1

        # 彩蛋：数字代码直接上屏股票名（输入 000001 → 平安银行）
        if code_alias and code:
            digits = strip_star(code.split(".")[0])
            if digits.isdigit():
                cnt = len(entries)
                add(Entry(key=digits, freq=freq, word=word, code=code, industry=""))
                stats["code_alias"] += len(entries) - cnt

    entries.sort(key=lambda e: (-e.freq, e.key, e.word))
    if max_entries:
        entries = entries[:max_entries]

    print("[build] 统计：" + json.dumps(stats, ensure_ascii=False))
    print(f"[build] 生成词条：{len(entries)} 条")
    return entries


def _freq_map(amounts: Dict[str, float]) -> Dict[str, int]:
    """把成交额换成 1~9999 的词频，让热门股在候选里排得更靠前。"""
    ordered = sorted(amounts.items(), key=lambda kv: kv[1] or 0, reverse=True)
    total = sum(1 for _, amount in ordered if amount and amount > 0)
    if not total:
        return {}
    out: Dict[str, int] = {}
    rank = 0
    for code, amount in ordered:
        if not amount or amount <= 0:
            continue
        rank += 1
        out[code] = max(1, min(9999, round(9999 * (total - rank + 1) / total)))
    return out


# 深蓝词库转换会丢弃“词面以标点开头”的条目，*ST 风险警示股全在其中
_LEADING_PUNCT = "".join(sorted(set(" \t" + STAR_CHARS + "（）()【】[]《》<>·．.,，。、-—_/\\'\"")))


def imewl_safe(entries: List[Entry]) -> List[Entry]:
    """给深蓝准备一份“词面已清洗”的副本：把开头的符号剥掉（``*ST美丽`` → ``ST美丽``）。

    我们自己写的文本词库不受影响，依旧上屏官方词面；
    但如果不做这一步，深蓝会把所有以 ``*`` 开头的股票整批静默丢弃。
    """
    safe: List[Entry] = []
    seen = set()
    adjusted = 0
    for e in entries:
        word = e.word.lstrip(_LEADING_PUNCT)
        if not word:
            continue
        if word != e.word:
            adjusted += 1
        sig = (e.key, word)
        if sig in seen:
            continue
        seen.add(sig)
        safe.append(Entry(key=e.key, freq=e.freq, word=word, code=e.code,
                          industry=e.industry))
    print(f"[build] 深蓝副本：{len(safe)} 条（{adjusted} 条被剥掉词面前导符号，*ST → ST）")
    return safe


# ------------------------------------------------------------------ 文本格式
def _write(path: Path, text: str, encoding: str, newline: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding, newline=newline) as fout:
        fout.write(text)
    size = path.stat().st_size
    print(f"[out] {path.name:<32} {size:>9,} B  ({encoding})")
    return path


def write_self_txt(path: Path, entries: Iterable[Entry]) -> Path:
    """深蓝词库转换的输入格式：``编码<TAB>词频<TAB>词语``（UTF-8 无 BOM，LF）。"""
    body = "".join(f"{e.key}\t{e.freq}\t{e.word}\n" for e in entries)
    return _write(path, body, "utf-8", "\n")


def write_words_txt(path: Path, entries: Iterable[Entry]) -> Path:
    """纯词表：一行一个股票名（UTF-8 带 BOM，CRLF）。微信输入法等「导入文本词库」用。"""
    seen = set()
    lines = []
    for e in entries:
        if e.word not in seen:
            seen.add(e.word)
            lines.append(e.word)
    return _write(path, "\r\n".join(lines) + "\r\n", "utf-8-sig", "\n")


def write_sgpy_txt(path: Path, entries: Iterable[Entry]) -> Path:
    """搜狗拼音文本词库：``'编码 词语``（GBK，CRLF）——深蓝 sgpy 格式同源。"""
    body = "".join(f"'{e.key} {e.word}\r\n" for e in entries)
    return _write(path, body, "gbk", "\n")


def write_custom_phrase_txt(path: Path, entries: Iterable[Entry], style: str = "ms") -> Path:
    """「用户自定义短语」文本（UTF-8 带 BOM，CRLF）。

    ``style="ms"`` → ``编码,词频=词语``；``style="sq"`` → ``编码;词频,词语``。
    不同输入法（甚至同一输入法的新旧版本）只认其中一种，所以两份都备好。
    """
    if style == "sq":
        body = "".join(f"{e.key};{e.freq},{e.word}\r\n" for e in entries)
    else:
        body = "".join(f"{e.key},{e.freq}={e.word}\r\n" for e in entries)
    return _write(path, body, "utf-8-sig", "\n")


def write_code_word_txt(path: Path, entries: Iterable[Entry]) -> Path:
    """带编码文本词库：``词语<TAB>编码<TAB>词频``（UTF-8 带 BOM，LF）——LibIME/通用。"""
    body = "".join(f"{e.word}\t{e.key}\t{e.freq}\n" for e in entries)
    return _write(path, body, "utf-8-sig", "\n")


def write_rime_yaml(path: Path, entries: Iterable[Entry], version: str) -> Path:
    """Rime（小狼毫 / 鼠须管）table_translator 词库，附赠格式。"""
    head = (
        "---\n"
        "name: astock\n"
        f"version: \"{version}\"\n"
        "sort: by_weight\n"
        "use_preset_vocabulary: false\n"
        "columns:\n"
        "  - text\n"
        "  - code\n"
        "  - weight\n"
        "...\n"
    )
    body = "".join(f"{e.word}\t{e.key}\t{e.freq}\n" for e in entries)
    return _write(path, head + body, "utf-8", "\n")


def write_manifest(path: Path, entries: Sequence[Entry], meta: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(meta)
    meta.setdefault("entries", len(entries))
    meta.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
    with open(path, "w", encoding="utf-8") as fout:
        json.dump(meta, fout, ensure_ascii=False, indent=2)
    print(f"[out] {path.name:<32} {'meta':>9}   (json)")
    return path


def timestamp_version() -> str:
    return datetime.now().strftime("%Y.%m%d.%H%M")
