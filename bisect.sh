#!/bin/bash
# 二分定位"哪一批汉化文件导致 Raycast 前端无法启动"。
# 判定标准: 新日志中是否出现 "frontend [main]" 启动行(>0 = 前端正常启动)。
set -u
ZH="$(cd "$(dirname "$0")" && pwd)"
PATCH="$ZH/build/patched"
BACK=$(ls -d "$ZH"/build/backup-original/*/ 2>/dev/null | head -1)
LOGDIR="$HOME/Library/Logs/com.raycast.macos"
OUT="$ZH/build/bisect.log"
: > "$OUT"
[ -z "$BACK" ] && { echo "没有原版备份，无法二分（请先安装一次以便生成备份）"; exit 1; }

declare -a RELS TARGETS
while IFS=$'\t' read -r rel tgt _edits; do
  [ -z "${rel:-}" ] && continue
  RELS+=("$rel"); TARGETS+=("$tgt")
done < "$ZH/build/map.tsv"
N=${#RELS[@]}
echo "待测文件数: $N" | tee -a "$OUT"

restore_all() { for i in "${!RELS[@]}"; do cp -f "$BACK/${RELS[$i]}" "${TARGETS[$i]}"; done; }
apply_only() { cp -f "$PATCH/${RELS[$1]}" "${TARGETS[$1]}"; }
apply_upto() { local k=$1 i; for ((i=0;i<=k;i++)); do cp -f "$PATCH/${RELS[$i]}" "${TARGETS[$i]}"; done; }
frontend_lines() {
  local L n; L=$(ls -t "$LOGDIR"/raycast-x-*.log 2>/dev/null | head -1)
  n=$(grep -c "frontend \[main\]" "$L" 2>/dev/null || true); echo "${n:-0}"
}
test_upto() {
  local k=$1; pkill -x Raycast 2>/dev/null; sleep 2; restore_all
  [ "$k" -ge 0 ] && apply_upto "$k"
  open -a Raycast; sleep 15
  local n; n=$(frontend_lines)
  echo "  [测试] 前 $((k+1)) 个文件 -> frontend 行数=$n" | tee -a "$OUT"
  [ "$n" -gt 0 ]
}
test_single() {
  local k=$1; pkill -x Raycast 2>/dev/null; sleep 2; restore_all; apply_only "$k"
  open -a Raycast; sleep 15
  local n; n=$(frontend_lines)
  echo "  [单文件] ${RELS[$k]} -> frontend 行数=$n" | tee -a "$OUT"
  [ "$n" -gt 0 ]
}

echo "== 1) 全量汉化复现问题 ==" | tee -a "$OUT"
if test_upto $((N-1)); then
  echo "全量汉化也正常（问题可能来自环境/时序）" | tee -a "$OUT"
  restore_all; pkill -x Raycast 2>/dev/null; sleep 2; open -a Raycast; exit 0
fi
echo "== 2) 二分 ==" | tee -a "$OUT"
lo=0; hi=$((N-1))
while [ "$lo" -lt "$hi" ]; do
  mid=$(( (lo+hi)/2 ))
  if test_upto "$mid"; then lo=$((mid+1)); else hi=$mid; fi
done
echo "== 3) 定位结果: ${RELS[$lo]} ==" | tee -a "$OUT"
echo "== 4) 单独验证 ==" | tee -a "$OUT"
test_single "$lo" && echo "需多文件组合，请人工继续排查" | tee -a "$OUT" \
                 || echo "确认单个文件即可复现" | tee -a "$OUT"
echo "== 5) 还原并重启 ==" | tee -a "$OUT"
pkill -x Raycast 2>/dev/null; sleep 2; restore_all; open -a Raycast; sleep 10
echo "已还原，frontend 行数=$(frontend_lines)" | tee -a "$OUT"
