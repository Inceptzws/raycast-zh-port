#!/bin/bash
# 依赖检查与安装（只需运行一次）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR"

echo "== 环境检查 =="
command -v python3 >/dev/null || { echo "✗ 缺少 python3"; exit 1; }
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
echo "✓ python3 $PYV"
command -v node >/dev/null || { echo "✗ 缺少 node（需要 18+）"; exit 1; }
echo "✓ node $(node -v)"

NODE_MAJOR=$(node -e 'console.log(process.versions.node.split(".")[0])')
[ "$NODE_MAJOR" -ge 18 ] || { echo "✗ node 版本过低（需要 18+）"; exit 1; }

if node -e "require.resolve('acorn')" >/dev/null 2>&1; then
  echo "✓ acorn 已安装"
else
  echo "== 安装 acorn =="
  if command -v npm >/dev/null; then
    npm install --no-fund --no-audit --cache "${TMPDIR:-/tmp}/raycast-zh-npm-cache" \
        --logs-dir "${TMPDIR:-/tmp}/raycast-zh-npm-logs"
  else
    echo "✗ 缺少 npm，无法自动安装 acorn；请手动执行: npm i acorn"; exit 1
  fi
  node -e "require.resolve('acorn')" >/dev/null 2>&1 && echo "✓ acorn 安装完成" || { echo "✗ acorn 安装失败"; exit 1; }
fi

echo
echo "下一步: ./fetch-upstream.sh   （下载上游汉化包到 patch/）"
