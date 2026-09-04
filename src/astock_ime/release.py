# -*- coding: utf-8 -*-
"""打包 + 提交 + 发布每周 Release。

设计目标：让 Cherry Studio（或任何周定时任务）里只需要一条命令

    python build.py release

就能完成「生成词库 → 打包 zip → git 提交推送 → GitHub Release vYYYY.MM.DD」。
普通人不用装 Python、不用连数据库，去 Releases 下载那个 zip 就够了。
"""

from __future__ import annotations

import argparse
import subprocess
import zipfile
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

# 解压后第一眼看到的说明（写在 zip 根目录，普通人不需要打开仓库）
HOWTO = """A 股输入法词库 · {version}

打不开 / 没效果？先看仓库里的 docs/import-guide.md。

1) Win10/11 自带输入法（微软拼音）
   导入文件：ms_pinyin_astock.dat
   设置 → 时间和语言 → 语言和区域 → 中文 → 微软拼音 → 选项
     → 词库和自学习 → 用户自定义短语 → 管理 → 导入
   建议导入前先点一次「导出」备份你自己的短语。

2) 搜狗输入法
   导入文件：custom_phrase_astock.txt
   设置 → 输入 → 自定义短语 → 「直接编辑配置文件」
   把 custom_phrase_astock.txt 的内容整体替换进 PhraseEdit.txt，保存即生效。
   动手前先把原来的 PhraseEdit.txt 备份一份，方便回滚。

验证：随便找个输入框敲
   payh → 平安银行     ndsd → 宁德时代     byd → 比亚迪
   wka  → 万科A        stml → ST美丽      tclkj → TCL科技

词条 {entries} 条 / 覆盖 {stocks} 只在市 A 股。
词库由股票名数据库自动生成，每周三、周五各更新一次。
"""


def default_version() -> str:
    """版本号规则：vYYYY.MM.DD（一周一个 release，同天重跑覆盖附件）。"""
    return "v" + date.today().strftime("%Y.%m.%d")


def run(cmd: List[str], cwd: Path, dry_run: bool = False) -> Tuple[int, str]:
    """跑一条外部命令，返回 (退出码, 合并输出)。"""
    printable = " ".join(cmd)
    if dry_run:
        print(f"[run] (dry-run) {printable}")
        return 0, ""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True)
    blob = (proc.stdout + proc.stderr).decode("utf-8", "ignore")
    last = blob.strip().splitlines()[-1] if blob.strip() else ""
    print(f"[run] {printable}\n      rc={proc.returncode} {last[:160]}")
    return proc.returncode, blob


# ------------------------------------------------------------------ 打包
LEXICON_SUFFIXES = (".dat", ".xml", ".txt", ".yaml", ".yml", ".scel", ".bin")


def build_package(dist_dir: Path, build_dir: Path, version: str,
                  entry_count: int, stock_count: int, docs_dir: Path) -> Path:
    """把 dist/ 打成 zip：词库 + 一眼能看懂的导入说明（调试信息放 meta/）。"""
    zip_path = dist_dir / f"astock-ime-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()

    payload = [p for p in sorted(dist_dir.iterdir())
               if p.is_file() and not p.name.startswith(".")
               and p.suffix.lower() in LEXICON_SUFFIXES]
    extras = [build_dir / "manifest.json", dist_dir / "conversion_report.json",
              docs_dir / "import-guide.md"]
    extras = [p for p in extras if p.exists()]
    howto_lines = HOWTO.format(version=version, entries=f"{entry_count:,}",
                               stocks=f"{stock_count:,}").splitlines()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in payload:
            zf.write(p, arcname=f"astock-ime-{version}/{p.name}")
        zf.writestr(f"astock-ime-{version}/README-导入说明.txt",
                    "\r\n".join(howto_lines) + "\r\n")
        for p in extras:
            name = p.name if p.suffix != ".md" else "import-guide.md"
            zf.write(p, arcname=f"astock-ime-{version}/meta/{name}")

    print(f"[pkg] {zip_path.name}  {zip_path.stat().st_size:,} B  "
          f"（{len(payload)} 个词库文件 + 导入说明 + meta/{len(extras)}）")
    return zip_path


# ------------------------------------------------------------------ git / gh
def git_branch(cwd: Path) -> str:
    proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=str(cwd), capture_output=True)
    return proc.stdout.decode("utf-8", "ignore").strip() or "main"


def git_is_repo(cwd: Path) -> bool:
    return subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                          cwd=str(cwd), capture_output=True).returncode == 0


def has_remote(cwd: Path) -> bool:
    proc = subprocess.run(["git", "remote"], cwd=str(cwd), capture_output=True)
    return bool(proc.stdout.decode("utf-8", "ignore").split())


def commit_and_push(cwd: Path, version: str, entries: int, dry_run: bool) -> bool:
    """提交源码改动并推送。返回是否真的推送过（无改动也推，保证远端最新）。"""
    if not git_is_repo(cwd):
        print("[git] 这里不是 git 仓库，跳过提交（先 git init / gh repo create）")
        return False
    run(["git", "add", "-A"], cwd, dry_run)
    # dry-run 时 git add 没真跑，这里直接当作有改动，把 commit 命令也打印出来
    dirty = True if dry_run else (
        subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(cwd)).returncode != 0)
    message = (f"chore(lexicon): {version} 全量重建（{entries} 条词条）" if dirty
               else f"chore(release): {version}")
    if dirty:
        rc, _ = run(["git", "commit", "-m", message], cwd, dry_run)
        if rc:
            return False
    else:
        print("[git] 工作区无改动，直接推送当前提交")
    rc, _ = run(["git", "push", "origin", git_branch(cwd)], cwd, dry_run)
    return rc == 0


def gh_available() -> bool:
    return subprocess.run(["gh", "--version"], capture_output=True).returncode == 0


def create_release(cwd: Path, version: str, zip_path: Path, notes: str,
                   dry_run: bool) -> bool:
    """建 release；tag 已存在就覆盖 zip（同一天重跑安全）。"""
    if not gh_available():
        print("[gh] 没装 GitHub CLI，跳过发布。手动上传：仓库 → Releases → Draft new release")
        print(f"     tag={version}  附件={zip_path.name}")
        return False
    if not has_remote(cwd):
        print("[gh] 没有配置 git remote，跳过发布。首次用：python build.py release --create-repo")
        return False

    notes_file = zip_path.parent / "release_notes.md"
    notes_file.write_text(notes, encoding="utf-8", newline="\n")

    exists = subprocess.run(["gh", "release", "view", version],
                            cwd=str(cwd), capture_output=True).returncode == 0
    if exists:
        # 同一周重跑：覆盖附件，并把标题/正文也刷新（改了文案不会被旧 release 正文冻住）
        rc, _ = run(["gh", "release", "upload", version, str(zip_path), "--clobber"],
                    cwd, dry_run)
        run(["gh", "release", "edit", version,
             "--title", f"A股输入法词库 {version}",
             "--notes-file", str(notes_file)], cwd, dry_run)
    else:
        rc, _ = run(["gh", "release", "create", version, str(zip_path),
                     "--title", f"A股输入法词库 {version}",
                     "--notes-file", str(notes_file)], cwd, dry_run)
    if rc == 0:
        print(f"[gh] release {version} 已就绪，附件：{zip_path.name}")
    notes_file.unlink(missing_ok=True)
    return rc == 0


def create_repo_if_needed(cwd: Path, repo_name: str, private: bool, dry_run: bool) -> bool:
    """一次性建远端仓库（gh repo create），已有 remote 就跳过。"""
    if has_remote(cwd):
        return True
    if not gh_available():
        print("[gh] 没装 gh，无法自动建仓。请手动 git remote add origin <地址>")
        return False
    vis = "--private" if private else "--public"
    rc, _ = run(["gh", "repo", "create", repo_name, "--source", ".", "--remote", "origin",
                 vis, "--push"], cwd, dry_run)
    return rc == 0


def release(args: argparse.Namespace, cwd: Path, version: str,
            entries: int, stocks: int, dist_dir: Path, build_dir: Path,
            docs_dir: Path) -> Optional[Path]:
    zip_path = build_package(dist_dir, build_dir, version, entries, stocks, docs_dir)
    notes = (f"## A 股输入法词库 {version}\n\n"
             f"* 词条 **{entries:,}** 条，覆盖 **{stocks:,}** 只在市 A 股\n"
             "* 微软拼音：导入 `ms_pinyin_astock.dat`；"
             "搜狗：用 `custom_phrase_astock.txt` 替换 PhraseEdit.txt\n"
             "* 另附旧版微软拼音 `.xml` 词库与 Rime 词库\n"
             "* 解压后先看 zip 里的 `README-导入说明.txt`\n"
             "* 编码规则：拼音首字母、去掉 `*`、大写字母转小写（`*ST美丽` → `stml`，`万科A` → `wka`）\n"
             "* 本包由周定时任务自动生成，导入步骤见 docs/import-guide.md\n")

    if not args.skip_git:
        pushed = commit_and_push(cwd, version, entries, args.dry_run)
        if not pushed and not args.skip_gh:
            print("[release] 推送未成功，暂不发布 release（避免 tag 指向旧提交）")
            return zip_path
    if not args.skip_gh:
        create_release(cwd, version, zip_path, notes, args.dry_run)
    return zip_path
