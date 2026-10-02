#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 build/patched/ 做静态验收:
  1. 骨架不变式: acorn 提取字面量后, 剔除字面量的代码骨架必须与原文件逐字节一致
     (证明只替换了字面量 token, 未触碰逻辑/导入路径/变量名)。
  2. 字面量数量一致 (替换不应增删 token)。
  3. 语法回归: 只有"原文件能解析、汉化后不能解析"才算失败。
  4. 统计 + 抽样展示 en -> zh。
用法: python3 verify.py
"""

import json
import subprocess
import sys
from pathlib import Path

from localize import BUILD, OUT, ROOT, Index, decode, has_cjk, norm_skeleton, unescape

PARSE_CHECK = ROOT / "tools" / "parse_check.mjs"


def main():
    data = json.loads((BUILD / "report.json").read_text(encoding="utf-8"))
    files = data["files"]
    if not files:
        print("❌ build/report.json 里没有任何汉化文件 —— 说明目标可能已经是汉化状态，"
              "或对齐失败。请先 install.py --restore 还原官方版本后重跑 localize.py。")
        return 1
    pairs = [[e["file"], e["target"], str(OUT / e["file"])] for e in files]
    (BUILD / "tmp").mkdir(parents=True, exist_ok=True)
    pairs_json = BUILD / "tmp" / "pairs.json"
    pairs_json.write_text(json.dumps(pairs), encoding="utf-8")

    all_paths = [Path(p[1]) for p in pairs] + [Path(p[2]) for p in pairs]
    print(f"acorn 校验 {len(all_paths)} 个文件 ...", flush=True)
    idx = Index(all_paths)

    bad, tokens, cjk_tokens, samples = [], 0, 0, []
    spec_bad, spec_missing = [], []
    for rel, orig, patched in pairs:
        o, n = Path(orig), Path(patched)
        olits, nlits = idx.get(o), idx.get(n)
        if olits is None or nlits is None:
            bad.append((rel, "parse failed in verifier"))
            continue
        odata, ndata = o.read_bytes(), n.read_bytes()
        if norm_skeleton(odata, olits) != norm_skeleton(ndata, nlits):
            bad.append((rel, "code skeleton changed"))
            continue
        if len(olits) != len(nlits):
            bad.append((rel, f"literal count {len(olits)} -> {len(nlits)}"))
            continue
        # 模块说明符必须原样保留, 且相对路径必须真实存在
        ospec = [l[2] for l in olits if l[5] == "spec"]
        nspec = [l[2] for l in nlits if l[5] == "spec"]
        if ospec != nspec:
            spec_bad.append(rel)
        for raw in nspec:
            s = raw[1:-1].decode("utf-8", "surrogateescape")
            if s.startswith("."):
                if not (o.parent / s).exists():   # 按原文件所在目录(真实 App)解析
                    spec_missing.append((rel, s))
        ch = [(a, b) for a, b in zip(olits, nlits) if a[2] != b[2]]
        tokens += len(ch)
        cjk_tokens += sum(1 for a, b in ch if has_cjk(b[3]))
        if len(samples) < 40:
            ex = [(a[3], b[3]) for a, b in ch if has_cjk(b[3])][:3]
            if ex:
                samples.append((rel, ex))

    out_json = BUILD / "parse_check.json"
    r = subprocess.run(["node", str(PARSE_CHECK), str(pairs_json), str(out_json)],
                       capture_output=True, text=True)
    print("  " + r.stdout.strip())
    regs = [x for x in json.loads(out_json.read_text(encoding="utf-8")) if x["regression"]]

    print(f"\n骨架不变式 + token 数一致: {len(pairs) - len(bad)} / {len(pairs)}")
    print(f"改动字面量 token: {tokens}  (含中文 {cjk_tokens})")
    print(f"语法回归          : {len(regs)}")
    print(f"模块说明符被改动  : {len(spec_bad)}  (必须为 0)")
    print(f"相对说明符无法解析: {len(spec_missing)}  (必须为 0)")
    for rel, why in bad[:10]:
        print(f"   ✗ {rel}: {why}")
    for rel in spec_bad[:10]:
        print(f"   ✗ 说明符被改: {rel}")
    for rel, sp in spec_missing[:10]:
        print(f"   ✗ 说明符指向不存在的文件: {rel} -> {sp}")
    for x in regs[:10]:
        print(f"   ✗ {x['rel']}: {x['error']}")

    print("\n抽样 (英文 -> 中文):")
    for rel, ex in samples[:8]:
        print(f"  {rel}")
        for en, zh in ex:
            print(f"      {en[:56]!r} -> {zh[:56]!r}")

    verdict = not bad and not regs and not spec_bad and not spec_missing
    print("\n结论:", "全部通过 ✅" if verdict else "存在问题 ❌")
    (BUILD / "verify.json").write_text(json.dumps(dict(
        files=len(pairs), invariant_fail=bad, syntax_regressions=regs, spec_changed=spec_bad, spec_missing=spec_missing,
        tokens=tokens, cjk_tokens=cjk_tokens, verdict=verdict), ensure_ascii=False, indent=1))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
