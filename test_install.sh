#!/bin/bash
# 安装 + 功能验收: 前端是否真的启动、主窗口是否弹出；失败则立即还原。
set -u
ZH="$(cd "$(dirname "$0")" && pwd)"
LOGDIR="$HOME/Library/Logs/com.raycast.macos"

pkill -x Raycast 2>/dev/null; sleep 2
cd "$ZH" || exit 1
python3 install.py || { echo "安装失败"; exit 1; }

open -a Raycast; sleep 16
L=$(ls -t "$LOGDIR"/raycast-x-*.log 2>/dev/null | head -1)
N=$(grep -c "frontend \[main\]" "$L" 2>/dev/null || echo 0)
echo "前端启动日志行数: $N   (日志: $(basename "${L:-none}"))"

if [ "${N:-0}" -eq 0 ]; then
  echo "❌ 前端未启动 —— 立即还原原版"
  pkill -x Raycast 2>/dev/null; sleep 2
  python3 install.py --restore
  open -a Raycast 2>/dev/null
  exit 1
fi

echo "✅ 前端已启动，触发主窗口…"
open "raycast://"; sleep 6
grep -E "Window did become key|Failed to handle deeplink" "$L" | tail -4
echo "--- 汉化状态 ---"
python3 install.py --check
