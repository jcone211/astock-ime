# -*- coding: utf-8 -*-
"""
股票名称 → 拼音首字母编码。

编码规则（本项目相对旧脚本的改进点）：
  1. 去掉名称中的星号 ``*``（含全角 ＊），例如 ``*ST美丽`` → 参与编码的字符里不再有 ``*``；
     —— 词库转换器（深蓝）会把带 ``*`` 的编码判为非法并**静默丢弃**该条目，
        旧流程里所有 *ST 风险警示股都进不了词库。
  2. 名称中的大写字母统一转小写，例如 ``万科A`` → ``wka``、``*ST美丽`` → ``stml``；
     —— 避免同一只股票出现 ``wkA`` / ``wka`` 两种码，也符合输入法默认小写输入习惯。
  3. 汉字取「拼音首字母」，以整词方式注音（交给 pypinyin 的词组模式处理多音字，
     比逐字注音更贴近真实读法）。
  4. 数字原样保留（``三六零`` → ``slz``；``N次`` 之类的 ``N`` 也保留）。
  5. 其它符号（括号、空格、间隔号 ``·``、标点等）忽略，不进入编码。
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

from pypinyin import Style, pinyin

# 需要丢弃的星号类字符
STAR_CHARS: str = "*＊∗✱✳❋"

# 编码中允许出现的字符：a-z 与 0-9
_VALID_KEY_RE = re.compile(r"[a-z0-9]*$")

# 常见的全角/半角符号（不影响词面，只是不进编码）
_IGNORE_IN_KEY = set(
    " \t\r\n"
    "（）()【】〔〕[]{}《》〈〉<>「」『』"
    "、。，．·・,.;；:：!！?？~～-—–_|/\\'\"“”‘’`^&*+=@#$%￥"
)


def is_cjk(ch: str) -> bool:
    """是否为常用汉字区（含扩展 A 区）内的字符。"""
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF          # CJK 统一汉字
        or 0x3400 <= code <= 0x4DBF       # CJK 扩展 A
        or 0xF900 <= code <= 0xFAFF       # CJK 兼容汉字
    )


def strip_star(text: str) -> str:
    """去掉各种星号字符。"""
    for ch in STAR_CHARS:
        text = text.replace(ch, "")
    return text


def normalize_key_chars(name: str, keep_digits: bool = True) -> str:
    """把股票名称裁剪成「只可能产生编码」的字符序列（汉字/字母/数字）。"""
    kept: List[str] = []
    for ch in strip_star(name).strip():
        if is_cjk(ch):
            kept.append(ch)
        elif ch.isascii() and ch.isalpha():
            kept.append(ch)                      # 字母稍后统一小写
        elif ch.isdigit() and keep_digits:
            kept.append(ch)
        elif ch in _IGNORE_IN_KEY:
            continue
        # 其它罕见符号直接忽略
    return "".join(kept)


def initials(name: str, keep_digits: bool = True, heteronym: bool = False) -> str:
    """股票名称 → 拼音首字母编码（小写，无 ``*``）。

    >>> initials("*ST美丽")
    'stml'
    >>> initials("万科A")
    'wka'
    >>> initials("平安银行")
    'payh'
    """
    target = normalize_key_chars(name, keep_digits=keep_digits)
    if not target:
        return ""

    # 整词注音，交给 pypinyin 处理多音字（heteronym=False 取最可能读音）
    raw = pinyin(target, style=Style.FIRST_LETTER, heteronym=heteronym)

    out: List[str] = []
    for item in raw:
        for ch in item[0]:
            if is_cjk(ch):
                continue                       # pypinyin 未收录的汉字，跳过
            if ch.isalpha():
                out.append(ch.lower())          # 改进点 2：大写 → 小写
            elif ch.isdigit():
                out.append(ch)
    return "".join(out)


def keyword_word(name: str, strip_star_in_word: bool = False) -> str:
    """上屏词面。默认保留官方名称（含 ``*ST`` 前缀），可选项去掉星号。"""
    word = name.strip()
    return strip_star(word) if strip_star_in_word else word


def is_valid_key(key: str, min_len: int = 2, max_len: int = 16) -> bool:
    """编码是否可用（纯小写字母/数字，长度合理）。"""
    if not key or not (min_len <= len(key) <= max_len):
        return False
    return bool(_VALID_KEY_RE.match(key))


def dedupe(entries: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """按 (编码, 词面) 去重，保持输入顺序。"""
    seen = set()
    result: List[Dict[str, str]] = []
    for e in entries:
        sig = (e["key"], e["word"])
        if sig in seen:
            continue
        seen.add(sig)
        result.append(e)
    return result
