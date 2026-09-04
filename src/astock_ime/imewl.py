# -*- coding: utf-8 -*-
"""调用「深蓝词库转换」生成各输入法原生词库（.dat / .scel 等二进制格式）。

文本类格式（自定义短语、Rime）本仓库自己就能产出，
深蓝只负责它擅长的原生二进制格式；找不到深蓝时全部跳过并给出提示，不影响主流程。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .phrase import SELF_FORMAT

# 深蓝输出格式 -> 产物（default=False 的须用 --targets 显式指定）
TARGETS: Tuple[Dict[str, object], ...] = (
    {"format": "win10mspy", "file": "ms_pinyin_astock.dat", "default": True,
     "desc": "Win10/11 微软拼音 · 用户自定义短语（导入即用）"},
    {"format": "mspy", "file": "ms_pinyin_astock.xml", "default": True,
     "desc": "旧版微软拼音 / 必应拼音的词库 XML"},
    {"format": "scel", "file": "astock.scel", "default": False,
     "desc": "细胞词库——实测深蓝 3.4 只写表头（5552 条回读只有 2 条），且搜狗走自定义短语就够，默认不导"},
    {"format": "win10mspyss", "file": "ms_pinyin_astock_ss.dat", "default": False,
     "desc": "微软拼音自学习词库（会污染你的上屏习惯，慎用）"},
)


def resolve_targets(spec: str = "") -> List[Tuple[str, str]]:
    """把 --targets 字符串解析成 (format, filename) 列表；空串 = 默认集合。"""
    wanted = {t.strip() for t in (spec or "").split(",") if t.strip()}
    out: List[Tuple[str, str]] = []
    for item in TARGETS:
        fmt = str(item["format"])
        if wanted:
            if fmt in wanted:
                out.append((fmt, str(item["file"])))
        elif item["default"]:
            out.append((fmt, str(item["file"])))
    unknown = wanted - {str(i["format"]) for i in TARGETS}
    if unknown:
        print("[imewl] 未知格式已忽略：" + ", ".join(sorted(unknown)))
    return out

_SEARCH_NAMES = ("ImeWlConverterCmd.exe", "imewlconverter", "深蓝词库转换.exe")

_RESULT_RE = re.compile(r"转换完成[:：]\s*导入\s*(\d+)\s*条[,，]\s*过滤\s*(\d+)\s*条[,，]\s*导出\s*(\d+)\s*条")


class ConverterNotFound(RuntimeError):
    pass


def find_converter(configured: str = "") -> Optional[Path]:
    """定位深蓝命令行程序：配置 > 环境变量 > PATH > 常见安装目录。"""
    for candidate in (configured, os.environ.get("ASTOCK_IMEWL_CONVERTER"),
                      os.environ.get("IMEWLCMD")):
        if candidate:
            p = Path(candidate).expanduser()
            if p.exists():
                return p
            if p.parent.exists():                       # 目录也行，里面找 exe
                found = _scan(p)
                if found:
                    return found

    for name in _SEARCH_NAMES:
        which = shutil.which(name)
        if which:
            return Path(which)

    for root in ("D:/tools", "C:/tools", str(Path.home() / "Downloads"),
                 str(Path.home() / "Desktop")):
        base = Path(root)
        if not base.exists():
            continue
        for depth in ("*/cli", "*", "*/*/cli"):
            for hit in base.glob(depth):
                found = _scan(hit)
                if found:
                    return found
    return None


def _scan(directory: Path) -> Optional[Path]:
    for name in ("ImeWlConverterCmd.exe", "imewlconverter"):
        p = directory / name
        if p.exists():
            return p
    return None


def convert(src_txt: Path, out_dir: Path, exe: Path,
            targets: Optional[Sequence[Tuple[str, str]]] = None,
            extra_filter: str = "") -> List[Dict[str, object]]:
    """把 build/astock_imewl.txt 转成各输入法原生词库，返回每个目标的执行结果。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, object]] = []
    targets = list(targets) if targets is not None else resolve_targets("")

    for fmt, filename in targets:
        dst = out_dir / filename
        cmd = [str(exe), str(src_txt), "-i", "self", "-o", fmt,
               "-O", str(dst), "-F", SELF_FORMAT]
        if extra_filter:
            cmd += ["-f", extra_filter]

        # 必须用参数数组传参，且 -F 里的分隔符要是真实制表符（深蓝 3.4 不解析 "\t" 转义）
        proc = subprocess.run(cmd, capture_output=True)
        blob = (proc.stdout + proc.stderr).decode("gbk", "ignore")
        match = _RESULT_RE.search(blob)
        imported, filtered, exported = (
            (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if match else (0, 0, 0)
        )
        ok = proc.returncode == 0 and dst.exists() and exported > 0
        print(f"[imewl] {fmt:<12} -> {filename:<26} "
              f"{'OK ' if ok else 'FAIL'} 导入 {imported} / 过滤 {filtered} / 导出 {exported}")
        if not ok and blob.strip():
            print("        " + blob.strip().splitlines()[-1])
        results.append({"format": fmt, "file": filename, "ok": ok,
                        "imported": imported, "filtered": filtered, "exported": exported})
    return results


def verify(out_dir: Path, exe: Path, results: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """把导出的词库再读一遍，用回读条数验证“有没有静默丢词”。

    这一步是为了当年那个坑：旧流程里 95 条 *ST 股被静默过滤，
    只看“转换完成”根本发现不了。
    """
    tmp = out_dir / ".verify.txt"
    for item in results:
        if not item.get("ok"):
            continue
        fmt, filename = str(item["format"]), str(item["file"])
        proc = subprocess.run([str(exe), str(out_dir / filename), "-i", fmt,
                               "-o", "rime", "-O", str(tmp)], capture_output=True)
        blob = (proc.stdout + proc.stderr).decode("gbk", "ignore")
        match = _RESULT_RE.search(blob)
        back = int(match.group(3)) if match else 0
        expected = int(item["exported"])
        item["readback"] = back
        flag = "OK" if back >= expected else "LOSS"
        print(f"[verify] {filename:<26} 回读 {back}/{expected} {flag}")
        if back < expected:
            print("        回读条数少于导出条数：该格式在当前深蓝版本下不可靠，"
                  "建议改用文本词库 / 自定义短语导入")
    if tmp.exists():
        tmp.unlink()
    return results
