# -*- coding: utf-8 -*-
"""astock-ime 命令行入口。

    python build.py all                # 数据库 → 中间 txt → 各输入法词库
    python build.py release            # 上面全部 + 打包 zip + 推送 + 建 GitHub Release
    python build.py export             # 只导数据快照
    python build.py build              # 只生成文本词库
    python build.py convert            # 只调深蓝转原生格式
    python build.py build --source csv --csv examples/stock_names.sample.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .config import REPO_ROOT, load_config
from .db import (apply_stocks, fetch_hot_amounts, fetch_names, read_csv_rows,
                 write_csv_rows)
from .imewl import TARGETS, convert as imewl_convert, find_converter, resolve_targets, verify
from .release import create_repo_if_needed, default_version
from .release import release as do_release
from .phrase import (
    Entry,
    build_entries,
    imewl_safe,
    timestamp_version,
    write_custom_phrase_txt,
    write_manifest,
    write_rime_yaml,
    write_self_txt,
    write_sgpy_txt,
    write_words_txt,
)

DEFAULT_DATA = REPO_ROOT / "data"
DEFAULT_BUILD = REPO_ROOT / "build"
DEFAULT_DIST = REPO_ROOT / "dist"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="astock-ime",
        description="A 股股票名 → 输入法自定义短语词库（微软拼音 / 搜狗）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("command", choices=["export", "build", "convert", "all", "release"],
                    nargs="?", default="all",
                    help="要执行的步骤；release = 生成 + 打包 zip + git 推送 + 建 GitHub Release")
    ap.add_argument("--config", default=None, help="配置文件路径（默认 ./config.json）")
    ap.add_argument("--source", choices=["db", "csv"], default="db", help="名称数据来源")
    ap.add_argument("--csv", default=str(DEFAULT_DATA / "stock_names.csv"),
                    help="--source csv 时读取的 CSV（ts_code,name,industry）")
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA), help="数据库快照 CSV 目录")
    ap.add_argument("--build-dir", default=str(DEFAULT_BUILD), help="中间产物（astock.txt）目录")
    ap.add_argument("--dist-dir", default=str(DEFAULT_DIST), help="最终词库目录")

    g = ap.add_argument_group("词条规则")
    g.add_argument("--rank", type=int, default=None, help="词频/优先级，默认取配置 phrase_rank")
    g.add_argument("--freq", choices=["flat", "hot"], default="flat",
                   help="flat=全部同权重；hot=按近 N 日成交额给热门股更高权重（需要行情表）")
    g.add_argument("--hot-days", type=int, default=20, help="--freq hot 的统计交易日数")
    g.add_argument("--exclude-st", action="store_true", help="整条剔除 *ST / ST 风险警示股")
    g.add_argument("--strip-star-word", action="store_true",
                   help="上屏词面也去掉 *（词面变成 ST美丽；默认保留官方名称）")
    g.add_argument("--min-key-len", type=int, default=None, help="编码最短长度，默认 2")
    g.add_argument("--limit", type=int, default=None, help="只输出前 N 条（0/不填 = 全部）")
    g.add_argument("--code-alias", action="store_true",
                   help="追加「6位股票代码 → 股票名」短语，输代码也能出名字")
    g.add_argument("--stocks", default="",
                   help="只导自选股：逗号分隔的股票名/代码，或 @清单文件（按你写的顺序输出）")
    g.add_argument("--no-star-variants", action="store_true",
                   help="不为 *ST 股票额外生成一条去掉星号的同编码词条")

    c = ap.add_argument_group("深蓝词库转换")
    c.add_argument("--no-imewl", action="store_true", help="不调深蓝，只产出文本格式")
    c.add_argument("--imewl", default=None, help="ImeWlConverterCmd 路径（覆盖配置）")
    c.add_argument("--targets", default="",
                   help="要导出的深蓝格式（逗号分隔，不填则只导默认安全的那几个），"
                        "候选：" + "、".join(str(t["format"]) for t in TARGETS))

    r = ap.add_argument_group("发布（release 子命令）")
    r.add_argument("--version", default="",
                   help="版本号，默认按今天日期生成 vYYYY.MM.DD（同天重跑则覆盖附件）")
    r.add_argument("--create-repo", action="store_true",
                   help="首次发布：没有 remote 时用 gh repo create 建仓并加 origin")
    r.add_argument("--repo-name", default="astock-ime", help="--create-repo 使用的仓库名")
    r.add_argument("--private", action="store_true", help="--create-repo 时建私有仓")
    r.add_argument("--skip-git", action="store_true", help="只生成 + 打包，不提交不推送")
    r.add_argument("--skip-gh", action="store_true", help="不创建 GitHub Release")
    r.add_argument("--dry-run", action="store_true", help="只打印将要执行的 git / gh 命令")
    return ap


# ------------------------------------------------------------------ 步骤
def load_rows(args: argparse.Namespace, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    if args.source == "csv":
        rows = read_csv_rows(args.csv)
        print(f"[db] 从 CSV 读取 {len(rows)} 条：{args.csv}")
        return rows
    rows = fetch_names(cfg["database"])
    snapshot = Path(args.data_dir) / "stock_names.csv"
    write_csv_rows(snapshot, rows)
    return rows


def do_build(args: argparse.Namespace, cfg: Dict[str, Any]) -> List[Entry]:
    rows = load_rows(args, cfg)
    if args.stocks:
        rows, missing = apply_stocks(
            rows, args.stocks, code_field=cfg["database"].get("code_column", "ts_code"))
        if not rows:
            sys.exit("[错误] 自选股清单一只都没匹配上，检查名字/代码写法")
    db_cfg = cfg["database"]
    amounts = None
    if args.freq == "hot":
        if args.source == "csv":
            print("[warn] --freq hot 仅支持数据库来源，已忽略")
        else:
            amounts = fetch_hot_amounts(db_cfg, days=args.hot_days)
            if amounts is None:
                print("[warn] 行情表不可用，退回 flat 权重")

    entries = build_entries(
        rows,
        rank=args.rank if args.rank is not None else int(cfg["build"].get("phrase_rank", 1)),
        min_key_len=args.min_key_len if args.min_key_len is not None
        else int(cfg["build"].get("min_key_len", 2)),
        strip_star_in_word=args.strip_star_word
        or bool(cfg["build"].get("strip_star_in_word", False)),
        exclude_st=args.exclude_st or bool(cfg["build"].get("exclude_st", False)),
        max_entries=args.limit if args.limit is not None
        else int(cfg["build"].get("max_entries", 0) or 0),
        code_alias=args.code_alias or bool(cfg["build"].get("code_alias", False)),
        star_variants=not args.no_star_variants,
        preserve_order=bool(args.stocks),
        amounts=amounts,
    )
    if not entries:
        sys.exit("[错误] 一条词条都没生成，检查数据源/编码规则")

    self_txt = Path(args.build_dir) / "astock.txt"
    write_self_txt(self_txt, entries)
    # 深蓝会丢弃以 * 开头的词面，单独给它一份清洗过的副本
    imewl_txt = Path(args.build_dir) / "astock_imewl.txt"
    write_self_txt(imewl_txt, imewl_safe(entries))

    dist = Path(args.dist_dir)
    version = timestamp_version()
    write_sgpy_txt(dist / "sogou_astock.txt", entries)                      # 搜狗文本词库
    write_words_txt(dist / "astock_words.txt", entries)                      # 纯词表（抄写清单）
    write_custom_phrase_txt(dist / "custom_phrase_astock.txt", entries)      # 自定义短语 ms 式
    write_custom_phrase_txt(dist / "custom_phrase_astock_alt.txt", entries, style="sq")
    write_rime_yaml(dist / "astock_rime.yaml", entries, version)            # Rime（附赠）

    report(entries)
    write_manifest(Path(args.build_dir) / "manifest.json", entries, {
        "source": args.source,
        "csv": str(args.csv) if args.source == "csv" else None,
        "freq_mode": args.freq,
        "exclude_st": args.exclude_st,
        "strip_star_word": args.strip_star_word,
        "code_alias": args.code_alias,
        "star_variants": not args.no_star_variants,
        "stocks": args.stocks or None,
        "version": version,
        "files": sorted(p.name for p in dist.glob("*") if p.is_file()),
    })
    return entries


def do_convert(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    src = Path(args.build_dir) / "astock_imewl.txt"
    if not src.exists():                                    # 允许单独跑 convert
        src = Path(args.build_dir) / "astock.txt"
        print("[warn] 没找到 astock_imewl.txt，改用 astock.txt（*ST 词条会被丢弃）")
    if not src.exists():
        sys.exit(f"[错误] 缺少 {src}，请先执行 build")

    if args.no_imewl:
        print("[imewl] 已按 --no-imewl 跳过原生格式转换（文本词库已生成）")
        return
    exe = find_converter(args.imewl or cfg["tools"].get("imewl_converter", ""))
    if not exe:
        print("[warn] 没找到「深蓝词库转换」，跳过 .dat/.scel 生成。")
        print("       下载：https://github.com/studyzy/imewlconverter/releases")
        print("       然后在 config.json 的 tools.imewl_converter 里填上路径，或加 --imewl <路径>")
        return
    print(f"[imewl] 使用 {exe}")
    targets = resolve_targets(args.targets)
    if not targets:
        print("[imewl] 没有要导出的目标格式，跳过")
        return
    results = imewl_convert(src, Path(args.dist_dir), exe, targets)
    verify(Path(args.dist_dir), exe, results)
    report_path = Path(args.dist_dir) / "conversion_report.json"
    with open(report_path, "w", encoding="utf-8") as fout:
        json.dump({"converter": str(exe), "source": str(src), "targets": results},
                  fout, ensure_ascii=False, indent=2)
    print(f"[imewl] 转换详情已写入 {report_path}")


def report(entries: List[Entry]) -> None:
    keys = Counter(e.key for e in entries)
    stars = [e for e in entries if e.word.startswith("*")]
    hottest = sorted(keys.items(), key=lambda kv: -kv[1])[:5]
    print(
        "[report] 词条 {n} / 唯一编码 {k} / 最长编码 {m}\n"
        "         含 * 的风险警示股词条：{s} 条（旧流程会被词库转换整批丢弃）\n"
        "         撞码最多的编码：{top}".format(
            n=len(entries), k=len(keys), m=max(len(k) for k in keys),
            s=len(stars),
            top="、".join(f"{k}×{c}" for k, c in hottest),
        )
    )
    shown = (stars + entries)[:3]
    for e in shown:
        print(f"[report] 示例：{e.key} → {e.word}  ({e.code})")


def main(argv: List[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    cfg = load_config(args.config)
    if not cfg.get("_config_loaded"):
        print(f"[cfg] 未找到 {cfg['_config_path']}，使用内置默认值"
              f"（可复制 config.example.json 为 config.json）")
    else:
        print(f"[cfg] {cfg['_config_path']}")

    command = args.command
    if command in ("export",):
        rows = load_rows(args, cfg)
        print(f"[done] {len(rows)} 条名称已就绪")
        return
    if command == "convert":
        do_convert(args, cfg)
        return

    entries = do_build(args, cfg)
    if command == "all":
        do_convert(args, cfg)
        print("\n下一步：把 dist/ 里的文件导入输入法，见 docs/import-guide.md")
        return

    # release：供 Cherry Studio 周定时任务直接调的一条命令
    do_convert(args, cfg)
    stocks = len({e.code for e in entries if e.code})
    version = args.version or default_version()
    if args.create_repo:
        create_repo_if_needed(REPO_ROOT, args.repo_name, args.private, args.dry_run)
    do_release(args, REPO_ROOT, version, len(entries), stocks,
               Path(args.dist_dir), Path(args.build_dir), REPO_ROOT / "docs")
    print(f"\n[release] {version} 完成。普通用户只要去 Releases 下 zip，"
          f"不用装 Python、不用连数据库")


if __name__ == "__main__":  # pragma: no cover
    main()
