// 用 acorn 精确提取字符串字面量, 输出【UTF-8 字节偏移】+【风险类别】。
// kind:
//   spec  — 模块说明符(import/export from、动态 import、require 参数): 绝不能改
//   key   — 对象属性名 / 计算成员访问的键 / switch case 字面量: 改了会破坏查表
//   uuid  — UUID 形态(如 Sentry debug id): 无意义替换, 跳过
//   plain — 其余普通字符串(UI 文案), 允许替换
// 用法: node lits.mjs <files.json> <out.json>
import * as acorn from "acorn";
import fs from "node:fs";

const [inFile, outFile] = process.argv.slice(2);
const files = JSON.parse(fs.readFileSync(inFile, "utf8"));
const out = {};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function collect(src) {
  const ast = acorn.parse(src, {
    ecmaVersion: "latest",
    sourceType: "module",
    allowHashBang: true,
    allowReturnOutsideFunction: true,
    allowAwaitOutsideFunction: true,
    allowImportExportEverywhere: true,
  });

  const risky = new Map(); // "start:end" -> kind
  const mark = (node, kind) => {
    if (node && node.type === "Literal" && typeof node.value === "string") {
      risky.set(node.start + ":" + node.end, kind);
    }
  };

  const found = [];
  const walk = (node) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) return node.forEach(walk);
    if (typeof node.type === "string") {
      switch (node.type) {
        case "ImportDeclaration":
        case "ExportNamedDeclaration":
        case "ExportAllDeclaration":
        case "ImportExpression":
          mark(node.source, "spec");
          break;
        case "CallExpression":
          if (node.callee && node.callee.type === "Identifier"
              && node.callee.name === "require" && node.arguments.length) {
            mark(node.arguments[0], "spec");
          }
          break;
        case "Property":
          if (!node.computed) mark(node.key, "key");
          break;
        case "MemberExpression":
          if (node.computed) mark(node.property, "key");
          break;
        case "SwitchCase":
          mark(node.test, "key");
          break;
        default:
          break;
      }
      if (node.type === "Literal" && typeof node.value === "string" && !node.regex) {
        found.push([node.start, node.end, src[node.start]]);
      } else if (node.type === "TemplateLiteral" && node.expressions.length === 0) {
        found.push([node.start, node.end, "`"]);
      }
    }
    for (const k of Object.keys(node)) {
      if (k === "start" || k === "end" || k === "loc" || k === "range") continue;
      walk(node[k]);
    }
  };
  walk(ast);
  found.sort((a, b) => a[0] - b[0]);

  const lits = [];
  let prevEnd = 0;
  let prevBytes = 0;
  for (const [s, e, q] of found) {
    const bs = prevBytes + Buffer.byteLength(src.slice(prevEnd, s), "utf8");
    const be = bs + Buffer.byteLength(src.slice(s, e), "utf8");
    let kind = risky.get(s + ":" + e) || "plain";
    if (kind === "plain") {
      const inner = src.slice(s + 1, e - 1);
      if (UUID.test(inner)) kind = "uuid";
    }
    lits.push([bs, be, q, kind]);
    prevEnd = e;
    prevBytes = be;
  }
  return lits;
}

for (const f of files) {
  try {
    const buf = fs.readFileSync(f);
    const src = buf.toString("utf8");
    const byteExact = Buffer.byteLength(src, "utf8") === buf.length;
    out[f] = { ok: true, byteExact, lits: collect(src) };
  } catch (e) {
    out[f] = { ok: false, error: String(e && e.message ? e.message : e).slice(0, 200) };
  }
}
fs.writeFileSync(outFile, JSON.stringify(out));
const vals = Object.values(out);
const total = vals.filter((v) => v.ok).reduce((n, v) => n + v.lits.length, 0);
const riskyN = vals.filter((v) => v.ok).reduce((n, v) => n + v.lits.filter((l) => l[3] !== "plain").length, 0);
console.log(`parsed ${files.length} files, ok=${vals.filter((v) => v.ok).length}, fail=${vals.filter((v) => !v.ok).length}, literals=${total}, risky_skipped=${riskyN}`);
