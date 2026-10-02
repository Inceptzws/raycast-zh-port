// 单文件 acorn 语法检查, exit 0 = OK。
import * as acorn from "acorn";
import fs from "node:fs";
try {
  const src = fs.readFileSync(process.argv[2], "utf8");
  acorn.parse(src, {
    ecmaVersion: "latest", sourceType: "module", allowHashBang: true,
    allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true,
    allowImportExportEverywhere: true,
  });
  console.log("OK");
} catch (e) {
  console.log(String(e && e.message ? e.message : e).slice(0, 160));
  process.exit(1);
}
