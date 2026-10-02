// acorn 语法验收: 只报告"原文件能解析、汉化后不能解析"的回归。
// 用法: node parse_check.mjs <pairs.json> <out.json>
//   pairs.json: [[rel, originalPath, patchedPath], ...]
import * as acorn from "acorn";
import fs from "node:fs";

const [inFile, outFile] = process.argv.slice(2);
const pairs = JSON.parse(fs.readFileSync(inFile, "utf8"));

function ok(p) {
  try {
    const src = fs.readFileSync(p, "utf8");
    acorn.parse(src, {
      ecmaVersion: "latest", sourceType: "module", allowHashBang: true,
      allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true,
      allowImportExportEverywhere: true,
    });
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e).slice(0, 160) };
  }
}

const results = [];
for (const [rel, orig, patched] of pairs) {
  const o = ok(orig), p = ok(patched);
  results.push({ rel, original_ok: o.ok, patched_ok: p.ok, regression: o.ok && !p.ok, error: p.error || "" });
}
fs.writeFileSync(outFile, JSON.stringify(results, null, 1));
const reg = results.filter((r) => r.regression);
console.log(`checked ${results.length}, originals ok=${results.filter((r) => r.original_ok).length}, regressions=${reg.length}`);
for (const r of reg.slice(0, 10)) console.log(`  REGRESSION ${r.rel}: ${r.error}`);
