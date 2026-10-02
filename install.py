#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 build/patched/ 里的汉化资源安装进 Raycast.app, 或还原回原版。

  python3 install.py --check      # 查看当前状态(已汉化/未汉化、备份情况)
  python3 install.py              # 备份原文件后安装汉化(幂等)
  python3 install.py --restore    # 用备份还原原版

要点:
  * 安装/还原前必须完全退出 Raycast(脚本会检测并拒绝在运行时写入)。
  * 原文件按 Raycast 版本备份到 build/backup-original/<版本>/, 记录 SHA-256。
  * 采用"原地覆写"(保留 inode / 属主 / 权限 / xattr), 不重新签名、不改可执行文件。
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
OUT = BUILD / "patched"
BACKUP_ROOT = BUILD / "backup-original"
REPORT = BUILD / "report.json"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raycast_running() -> bool:
    r = subprocess.run(["pgrep", "-x", "Raycast"], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def load():
    if not REPORT.is_file():
        sys.exit("缺少 build/report.json，请先运行 localize.py 生成汉化文件")
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    return data["meta"], data["files"]


def backup_dir(version: str) -> Path:
    return BACKUP_ROOT / version


def read_manifest(version: str):
    p = backup_dir(version) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def cmd_check():
    meta, files = load()
    print(f"汉化产物对应 Raycast: {meta['app_version']}，文件数 {len(files)}")
    patched = sum(1 for e in files if Path(e["target"]).is_file()
                  and sha256(Path(e["target"])) == sha256(OUT / e["file"]))
    print(f"当前已汉化文件: {patched} / {len(files)}"
          + ("  → 已汉化" if patched == len(files) else "  → 未汉化或部分汉化"))
    m = read_manifest(meta["app_version"])
    print("原版备份:", f"存在({len(m['files'])} 个文件)" if m else "无")
    print("Raycast 进程:", "运行中" if raycast_running() else "未运行")


def cmd_install():
    meta, files = load()
    version = meta["app_version"]
    missing = [e["file"] for e in files if not (OUT / e["file"]).is_file()]
    if missing:
        sys.exit(f"汉化文件缺失 {len(missing)} 个，请先重新运行 localize.py")
    if raycast_running():
        sys.exit("Raycast 正在运行。请先完全退出 Raycast（菜单栏图标 → Quit Raycast）后重试。")

    bdir = backup_dir(version)
    bdir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(version) or {"app_version": version, "files": {}}

    backed = already = skipped_patched = 0
    for e in files:
        tgt, src = Path(e["target"]), OUT / e["file"]
        if not tgt.is_file():
            sys.exit(f"目标文件不存在: {tgt}（Raycast 版本已变化，请重新运行 localize.py）")
        if sha256(tgt) == sha256(src):
            skipped_patched += 1          # 目标已是汉化内容，不需要备份
            continue
        bak = bdir / e["file"]
        prev = manifest["files"].get(e["file"])
        if prev and bak.is_file() and sha256(bak) == prev.get("sha256"):
            already += 1
            continue
        bak.parent.mkdir(parents=True, exist_ok=True)
        bak.write_bytes(tgt.read_bytes())
        manifest["files"][e["file"]] = {"path": str(tgt), "sha256": sha256(bak)}
        backed += 1
    (bdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print(f"备份: 新备份 {backed} 个，沿用已有 {already} 个，已是汉化无需备份 {skipped_patched} 个 → {bdir}")

    changed = 0
    for e in files:
        tgt, src = Path(e["target"]), OUT / e["file"]
        blob = src.read_bytes()
        if sha256(tgt) == hashlib.sha256(blob).hexdigest():
            continue
        with tgt.open("wb") as fh:   # 原地覆写
            fh.write(blob)
        changed += 1
    print(f"已安装汉化: 覆写 {changed} 个文件")
    ok = sum(1 for e in files if sha256(Path(e["target"])) == sha256(OUT / e["file"]))
    print(f"校验: {ok}/{len(files)} 个文件与汉化产物一致")
    if ok != len(files):
        sys.exit("⚠ 校验未通过，请执行 install.py --restore 还原")


def cmd_restore():
    meta, files = load()
    version = meta["app_version"]
    manifest = read_manifest(version)
    if not manifest:
        sys.exit(f"找不到 {version} 的原版备份，无法还原")
    if raycast_running():
        sys.exit("Raycast 正在运行。请先完全退出 Raycast 后重试。")
    restored = 0
    for rel, info in manifest["files"].items():
        bak, tgt = backup_dir(version) / rel, Path(info["path"])
        if not bak.is_file():
            print(f"  ⚠ 备份缺失: {rel}")
            continue
        with tgt.open("wb") as fh:
            fh.write(bak.read_bytes())
        restored += 1
    bad = [rel for rel, info in manifest["files"].items()
           if Path(info["path"]).is_file() and sha256(Path(info["path"])) != info["sha256"]]
    print(f"已还原 {restored} 个文件；校验: " + ("全部与原版一致 ✅" if not bad else f"⚠ {len(bad)} 个不一致"))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    (cmd_check if args.check else cmd_restore if args.restore else cmd_install)()


if __name__ == "__main__":
    main()
