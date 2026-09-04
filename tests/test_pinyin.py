# -*- coding: utf-8 -*-
"""编码规则单元测试：python -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astock_ime.pinyin import initials, is_valid_key, keyword_word, strip_star  # noqa: E402
from astock_ime.phrase import build_entries  # noqa: E402


class TestInitials(unittest.TestCase):
    def test_plain_chinese(self):
        self.assertEqual(initials("平安银行"), "payh")
        self.assertEqual(initials("宁德时代"), "ndsd")

    def test_uppercase_to_lowercase(self):
        """改进点 2：名称里的大写字母转小写。"""
        self.assertEqual(initials("万科A"), "wka")
        self.assertEqual(initials("TCL科技"), "tclkj")
        self.assertNotIn("A", initials("万科A"))

    def test_star_removed(self):
        """改进点 1：去掉 *，否则词库转换会把整条丢掉。"""
        self.assertEqual(initials("*ST美丽"), "stml")
        self.assertEqual(initials("＊ST皇庭"), "stht")
        self.assertTrue(is_valid_key(initials("*ST康佳A")))

    def test_polyphone_uses_word_mode(self):
        self.assertEqual(initials("长江电力"), "cjdl")     # 长 = chang
        self.assertEqual(initials("重庆钢铁"), "cqgt")     # 重 = chong

    def test_symbols_and_digits(self):
        self.assertEqual(initials(" 万科 A "), "wka")
        self.assertEqual(initials("*ST（美丽）"), "stml")
        self.assertEqual(initials("三六零"), "sll")

    def test_empty(self):
        self.assertEqual(initials(""), "")
        self.assertEqual(initials("（）·—"), "")
        self.assertFalse(is_valid_key(""))

    def test_word_keeps_official_star_by_default(self):
        self.assertEqual(keyword_word("*ST美丽"), "*ST美丽")
        self.assertEqual(keyword_word("*ST美丽", strip_star_in_word=True), "ST美丽")
        self.assertEqual(strip_star("*ST*"), "ST")


class TestBuildEntries(unittest.TestCase):
    ROWS = [
        {"ts_code": "000001.SZ", "name": "平安银行", "industry": "银行"},
        {"ts_code": "000002.SZ", "name": "万科A", "industry": "全国地产"},
        {"ts_code": "000006.SZ", "name": "*ST美丽", "industry": "房地产开发"},
        {"ts_code": "000007.SZ", "name": "全新好", "industry": "其他商业"},
        {"ts_code": "", "name": "  ", "industry": ""},                 # 空名称
        {"ts_code": "000008.SZ", "name": "平安银行", "industry": "银行"},  # 重复词面
    ]

    def test_basic(self):
        entries = build_entries(self.ROWS)
        keys = {e.key for e in entries}
        self.assertEqual(keys, {"payh", "wka", "stml", "qxh"})
        self.assertTrue(all(is_valid_key(k) for k in keys))

    def test_exclude_st(self):
        entries = build_entries(self.ROWS, exclude_st=True)
        self.assertNotIn("stml", {e.key for e in entries})

    def test_limit(self):
        self.assertEqual(len(build_entries(self.ROWS, max_entries=2)), 2)

    def test_code_alias(self):
        entries = build_entries(self.ROWS, code_alias=True)
        self.assertIn("000001", {e.key for e in entries})

    def test_sorted_and_freq(self):
        amounts = {"000001.SZ": 1e9, "000002.SZ": 1e6}
        entries = build_entries(self.ROWS, amounts=amounts)
        payh = next(e for e in entries if e.key == "payh")
        wka = next(e for e in entries if e.key == "wka")
        self.assertGreater(payh.freq, wka.freq)
        self.assertLessEqual(payh.freq, 9999)


if __name__ == "__main__":
    unittest.main()
