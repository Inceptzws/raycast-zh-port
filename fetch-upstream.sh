#!/bin/bash
# 从上游仓库下载汉化包并解压到 patch/（本仓库不分发译文，由使用者自行获取）
# 用法: ./fetch-upstream.sh [tag]     例: ./fetch-upstream.sh v2.6.0.0
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR"
REPO="${UPSTREAM_REPO:-zwjtano/raycast-macos-zh-CN}"
TAG="${1:-latest}"

if [ "$TAG" = "latest" ]; then
  API="https://api.github.com/repos/$REPO/releases/latest"
else
  API="https://api.github.com/repos/$REPO/releases/tags/$TAG"
fi

echo "查询上游 release: $REPO ($TAG)"
URL=$(curl -fsSL "$API" | python3 -c '
import json,sys
d=json.load(sys.stdin)
zips=[a for a in d.get("assets",[]) if a["name"].endswith(".zip")]
if not zips:
    sys.exit("上游该 release 没有 zip 资源")
print(zips[0]["browser_download_url"])
')
echo "下载: $URL"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fL --progress-bar -o "$TMP/upstream.zip" "$URL"
echo "SHA-256: $(shasum -a 256 "$TMP/upstream.zip" | awk '{print $1}')"

rm -rf patch; mkdir -p patch
unzip -q -o "$TMP/upstream.zip" -d patch
echo "已解压到 patch/:"
ls patch
echo
echo "提示: 上游仓库未声明开源许可证(保留所有权利)。请仅作个人本地使用，不要再分发其译文。"
