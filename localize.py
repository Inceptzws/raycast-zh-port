#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raycast 汉化移植工具 (macOS, arm64)

流程:
  1. 取 zwjtano/raycast-macos-zh-CN 2.6.0.0 汉化包 payload (人工复核的译文 JS)。
  2. acorn 精确提取"本机当前版本/架构"与 payload 的字符串字面量, 输出 UTF-8 字节偏移;
     全程按字节操作, 避免 JS UTF-16 与 Python 码点的偏移错位。
  3. 对齐(两种互补策略, 取并集):
       a) 代码片段锚点(patience) 完全一致的位置;
       b) 字面量左右各 96 字符上下文完全相同且唯一的位置。
     命中即认为同一处 UI 文案, 用 payload 的译文 token 精确替换本机 token。
  4. 每个产物用 acorn 复检语法; 若被某条替换破坏, 二分定位并丢弃该条直到通过。
  5. 输出到 build/patched/, 全程不改动 /Applications。

用法: python3 localize.py [--app /Applications/Raycast.app]
"""

import argparse
import bisect
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
OUT = BUILD / "patched"
TMP = BUILD / "tmp"
PAYLOAD_GLOB = "patch/*/payload"
LITS = ROOT / "tools" / "lits.mjs"
PARSE_ONE = ROOT / "tools" / "parse_one.mjs"
CTX = 96


# ---------------------------------------------------------------- 工具

def unescape(raw: str) -> str:
    out, i, n = [], 0, len(raw)
    simple = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
              "0": "\0", "\\": "\\", "'": "'", '"': '"', "`": "`", "/": "/"}
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            out.append("\\")
            break
        e = raw[i + 1]
        if e in simple:
            out.append(simple[e])
            i += 2
        elif e == "u":
            if i + 2 < n and raw[i + 2] == "{":
                j = raw.find("}", i + 3)
                try:
                    out.append(chr(int(raw[i + 3:j], 16)))
                except Exception:
                    out.append(raw[i:j + 1])
                i = j + 1
            else:
                try:
                    out.append(chr(int(raw[i + 2:i + 6], 16)))
                except Exception:
                    out.append(raw[i:i + 6])
                i += 6
        elif e == "x":
            try:
                out.append(chr(int(raw[i + 2:i + 4], 16)))
            except Exception:
                out.append(raw[i:i + 4])
            i += 4
        else:
            out.append(e)
            i += 2
    return "".join(out)


def decode(b: bytes) -> str:
    return b.decode("utf-8", errors="surrogateescape")


def has_cjk(s: str) -> bool:
    return any("\u3400" <= ch <= "\u9fff" for ch in s)


class Index:
    """acorn 解析索引: path -> [(byteStart, byteEnd, raw:bytes, value:str, quote:str)]"""

    def __init__(self, paths):
        TMP.mkdir(parents=True, exist_ok=True)
        files_json, out_json = TMP / "files.json", TMP / "lits.json"
        files_json.write_text(json.dumps([str(p) for p in paths]), encoding="utf-8")
        r = subprocess.run(["node", str(LITS), str(files_json), str(out_json)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"acorn 提取失败: {r.stderr[:400]}")
        print("  " + r.stdout.strip(), flush=True)
        raw = json.loads(out_json.read_text(encoding="utf-8"))
        self.cache, self.failed = {}, {}
        for path, info in raw.items():
            p = Path(path)
            if not info.get("ok") or not info.get("byteExact", True):
                self.cache[p] = None
                self.failed[p] = info.get("error", "non-utf8 or parse error")
                continue
            data = p.read_bytes()
            lits = []
            for (s, e, q, kind) in info["lits"]:
                rawtok = data[s:e]
                lits.append((s, e, rawtok, unescape(decode(rawtok[1:-1])), q, kind))
            self.cache[p] = lits

    def get(self, path):
        return self.cache.get(Path(path))


def parts_of(data: bytes, lits):
    parts, pos = [], 0
    for (s, e, *_r) in lits:
        parts.append(data[pos:s])
        pos = e
    parts.append(data[pos:])
    return parts


def norm_skeleton(data: bytes, lits) -> bytes:
    return b"".join(parts_of(data, lits))


# ---------------------------------------------------------------- 文件映射

HASH_RE = re.compile(r"-[A-Za-z0-9_-]{8}\.(js|mjs|css)$")


def key_of(name):
    return HASH_RE.sub(r".\1", name)


def find_target(res: Path, rel: Path):
    direct = res / rel
    if direct.is_file():
        return direct
    if rel.suffix in (".js", ".mjs") and rel.parent.name == "frontend":
        want = key_of(rel.name)
        cands = sorted(p for p in (res / rel.parent).glob("*.js") if key_of(p.name) == want)
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            return ("AMBIGUOUS", cands)
    return None


def pick_candidate(idx, pay_path, pay_text, cands):
    """2.6.2.0 把同名 chunk 拆成多个时, 用左右上下文重合度打分选最像的那个。"""
    plits = idx.get(pay_path)
    if plits is None:
        return None, 0.0
    pparts = parts_of(pay_text, plits)
    pset = set(pparts)
    best, score = None, 0.0
    for c in cands:
        clits = idx.get(c)
        if clits is None:
            continue
        cparts = parts_of(c.read_bytes(), clits)
        hit = sum(1 for p in cparts if p in pset)
        r = hit / max(1, len(cparts))
        if r > score:
            best, score = c, r
    return (best, score) if score >= 0.5 else (None, score)


# ---------------------------------------------------------------- 对齐

def equal_runs(A, B, i0=0, i1=None, j0=0, j1=None, depth=0):
    """A[i0:i1] 与 B[j0:j1] 之间完全相等的连续片段 [(a0,a1,b0), ...], patience 风格。"""
    if i1 is None:
        i1 = len(A)
    if j1 is None:
        j1 = len(B)
    if i0 >= i1 or j0 >= j1:
        return []
    if (i1 - i0) == (j1 - j0) and A[i0:i1] == B[j0:j1]:
        return [(i0, i1, j0)]
    if depth > 60:
        return []
    ca, cb = Counter(A[i0:i1]), Counter(B[j0:j1])
    pos_b = {}
    for k in range(j0, j1):
        pos_b.setdefault(B[k], []).append(k)
    cand = [(i, pos_b[A[i]][0]) for i in range(i0, i1)
            if ca[A[i]] == 1 and cb.get(A[i], 0) == 1]
    if not cand:
        return []
    tails, tails_idx, prev = [], [], [-1] * len(cand)
    for k, (_i, j) in enumerate(cand):
        p = bisect.bisect_left(tails, j)
        if p == len(tails):
            tails.append(j)
            tails_idx.append(k)
        else:
            tails[p] = j
            tails_idx[p] = k
        prev[k] = tails_idx[p - 1] if p > 0 else -1
    anchors, k = [], tails_idx[-1]
    while k >= 0:
        anchors.append(cand[k])
        k = prev[k]
    anchors.reverse()

    runs, ai, aj = [], i0, j0
    for (i, j) in anchors:
        if i > ai and j > aj:
            runs.extend(equal_runs(A, B, ai, i, aj, j, depth + 1))
        runs.append((i, i + 1, j))
        ai, aj = i + 1, j + 1
    if i1 > ai and j1 > aj:
        runs.extend(equal_runs(A, B, ai, i1, aj, j1, depth + 1))
    return runs


def context_pairs(en_parts, en_lits, zh_parts, zh_lits, ctx=CTX):
    """字面量左右上下文完全相同且 zh 侧唯一 => 配对。"""
    def key(parts, i):
        return (parts[i][-ctx:], parts[i + 1][:ctx])
    zmap = {}
    for j in range(len(zh_lits)):
        zmap.setdefault(key(zh_parts, j), []).append(j)
    out = []
    for i in range(len(en_lits)):
        c = zmap.get(key(en_parts, i))
        if c and len(c) == 1:
            out.append((en_lits[i], zh_lits[c[0]]))
    return out


def align_full(en_lits, en_parts, zh_lits, zh_parts):
    """锚点对齐 + 上下文对齐并集, 以 en 字节位置去重。"""
    by_pos = {}
    for (a0, a1, b0) in equal_runs(en_parts, zh_parts):
        for k in range(max(0, (a1 - a0) - 1)):
            a, b = en_lits[a0 + k], zh_lits[b0 + k]
            by_pos.setdefault(a[0], (a, b))
    for (a, b) in context_pairs(en_parts, en_lits, zh_parts, zh_lits):
        by_pos.setdefault(a[0], (a, b))
    return [by_pos[k] for k in sorted(by_pos)]


def build_edits(target_data, en_lits, pay_data, zh_lits):
    pairs = align_full(en_lits, parts_of(target_data, en_lits),
                       zh_lits, parts_of(pay_data, zh_lits))
    edits, stats = [], dict(pairs=len(pairs), candidates=0, same_value=0, unsafe=0, cjk=0,
                            skip_spec=0, skip_key=0, skip_uuid=0, skip_risky_rhs=0)
    for a, b in pairs:
        if a[2] == b[2]:
            continue
        stats["candidates"] += 1
        # 结构性防护: 模块说明符/对象键/计算键/switch case/UUID 一律不动
        if a[5] != "plain":
            stats["skip_" + a[5] if a[5] in ("spec", "key", "uuid") else "skip_risky_rhs"] += 1
            continue
        if b[5] != "plain":
            stats["skip_risky_rhs"] += 1
            continue
        if a[3] == b[3]:
            stats["same_value"] += 1
            continue
        if a[2].count(b"${") != b[2].count(b"${"):
            stats["unsafe"] += 1
            continue
        if has_cjk(b[3]):
            stats["cjk"] += 1
        edits.append((a[0], a[1], b[2]))
    return edits, stats


def apply_edits(data: bytes, edits) -> bytes:
    for s, e, raw in sorted(edits, key=lambda x: -x[0]):
        data = data[:s] + raw + data[e:]
    return data


def parses(data: bytes):
    TMP.mkdir(parents=True, exist_ok=True)
    f = TMP / "_probe.mjs"
    f.write_bytes(data)
    r = subprocess.run(["node", str(PARSE_ONE), str(f)], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip()


def repair(data: bytes, edits, log):
    """若整批替换破坏语法, 二分定位并丢弃肇事的单条替换, 直到通过。"""
    dropped = []
    for _ in range(40):
        ok, err = parses(apply_edits(data, edits))
        if ok:
            return edits, dropped
        lo, hi = 1, len(edits)
        while lo < hi:
            mid = (lo + hi) // 2
            okp, _ = parses(apply_edits(data, edits[:mid]))
            if okp:
                lo = mid + 1
            else:
                hi = mid
        culprit = edits[lo - 1]
        log.append((culprit[0], decode(culprit[2][:60]), err))
        edits = [e for e in edits if e is not culprit]
        dropped.append(culprit)
        if not edits:
            return [], dropped
    return None, dropped


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="/Applications/Raycast.app")
    args = ap.parse_args()

    res = Path(args.app) / "Contents/Resources/macos-app_RaycastDesktopApp.bundle/Contents/Resources"
    if not res.is_dir():
        sys.exit(f"找不到 Raycast 资源目录: {res}")
    pay_roots = list(ROOT.glob(PAYLOAD_GLOB))
    if not pay_roots:
        sys.exit("找不到 payload。请先运行 ./fetch-upstream.sh （或手动把上游汉化包解压到 patch/ 目录）")
    pay_root = pay_roots[0] / "Contents/Resources/macos-app_RaycastDesktopApp.bundle/Contents/Resources"

    ver = subprocess.run(["defaults", "read", str(Path(args.app) / "Contents/Info.plist"),
                          "CFBundleShortVersionString"], capture_output=True, text=True).stdout.strip() or "?"

    pay_files = sorted(p for p in pay_root.rglob("*") if p.is_file())
    resolvable, needed = {}, set(pay_files)
    for pf in pay_files:
        rel = pf.relative_to(pay_root)
        tgt = find_target(res, rel)
        resolvable[pf] = (rel, tgt)
        if tgt is None:
            continue
        needed.update(tgt[1] if isinstance(tgt, tuple) else [tgt])
    print(f"acorn 解析 {len(needed)} 个 JS 文件 ...", flush=True)
    idx = Index(sorted(needed))
    if idx.failed:
        print(f"  ⚠ 跳过 {len(idx.failed)} 个(无法解析或非 UTF-8):")
        for p, e in list(idx.failed.items())[:5]:
            print(f"     {p.name}: {e}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    report, skipped, dropped_log = [], [], []
    total_edits = total_cjk = 0
    for n_done, pf in enumerate(pay_files, 1):
        if n_done % 25 == 0 or n_done == 1:
            print(f"  [{n_done}/{len(pay_files)}] {pf.name[:52]}", flush=True)
        rel, tgt = resolvable[pf]
        pay_data = pf.read_bytes()
        if isinstance(tgt, tuple):
            tgt, score = pick_candidate(idx, pf, pay_data, tgt[1])
            if tgt is None:
                skipped.append((rel.as_posix(), f"unresolved score={score:.2f}"))
                continue
        elif tgt is None:
            skipped.append((rel.as_posix(), "no-target"))
            continue
        target_data = tgt.read_bytes()
        en_lits, zh_lits = idx.get(tgt), idx.get(pf)
        if en_lits is None or zh_lits is None:
            skipped.append((rel.as_posix(), "parse-failed"))
            continue
        edits, stats = build_edits(target_data, en_lits, pay_data, zh_lits)
        if not edits:
            skipped.append((rel.as_posix(), f"no-edits pairs={stats['pairs']}"))
            continue
        dropped = []
        edits, dropped = repair(target_data, edits, dropped)
        if edits is None:
            skipped.append((rel.as_posix(), "repair-failed"))
            continue
        if dropped:
            dropped_log.append((rel.as_posix(), dropped))
        new_data = apply_edits(target_data, edits)
        out = OUT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(new_data)
        total_edits += len(edits)
        total_cjk += sum(1 for e in edits if has_cjk(unescape(decode(e[2][1:-1]))))
        report.append(dict(file=rel.as_posix(), target=str(tgt), target_name=tgt.name,
                           edits=len(edits), dropped=len(dropped), **stats))

    with (BUILD / "map.tsv").open("w", encoding="utf-8") as fh:
        for r in report:
            fh.write(f"{r['file']}\t{r['target']}\t{r['edits']}\n")
    meta = dict(app_version=ver, app=str(args.app), payload_files=len(pay_files),
                patched_files=len(report), total_edits=total_edits, cjk_edits=total_cjk,
                skipped=skipped, repair_dropped=dropped_log)
    (BUILD / "report.json").write_text(json.dumps(dict(meta=meta, files=report),
                                                  ensure_ascii=False, indent=1))
    print(f"\nRaycast 版本      : {ver}")
    print(f"payload 文件      : {len(pay_files)}")
    print(f"生成汉化文件      : {len(report)}")
    print(f"替换字面量 token  : {total_edits} (含中文 {total_cjk})")
    print(f"跳过              : {len(skipped)}")
    for rel, why in skipped[:12]:
        print(f"   - {rel} [{why}]")
    if dropped_log:
        print(f"语法保护丢弃 {sum(len(d) for _, d in dropped_log)} 条, 涉及 {len(dropped_log)} 文件")
    if not report:
        print("\n⚠ 没有生成任何汉化文件。最常见原因: 目标 Raycast 已经被汉化过"
              "(请先 `python3 install.py --restore` 还原官方版本再运行)。")
    print(f"\n输出目录: {OUT}")


if __name__ == "__main__":
    main()
