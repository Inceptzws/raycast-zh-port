# 第三方内容与合规说明

本仓库是一个**移植工具**。为了规避版权风险，仓库中**不包含**任何第三方内容：

| 内容 | 是否包含在本仓库 | 权利归属 | 说明 |
| --- | --- | --- | --- |
| 本工具链脚本与文档 | ✅ 包含 | 本仓库作者（MIT） | `localize.py` / `verify.py` / `install.py` / `*.sh` / `tools/*` / `docs/*` |
| 上游汉化包译文 | ❌ 不包含 | [@zwjtano](https://github.com/zwjtano) | 由 `fetch-upstream.sh` 从上游仓库下载到本地 `patch/` |
| Raycast 应用资源 | ❌ 不包含 | Raycast Systems | 只在你本机已安装的 Raycast 上做本地修改 |
| acorn | ❌ 不包含（npm 安装） | Marijn Haverbeke 等，MIT | 通过 `setup.sh` 用 npm 安装 |

## 关于上游汉化包

上游仓库 [zwjtano/raycast-macos-zh-CN](https://github.com/zwjtano/raycast-macos-zh-CN)
**未声明开源许可证**（GitHub API 返回 `license: null`）。按照默认著作权规则，这意味着
**保留所有权利**：未经作者许可，不得再分发其译文或打包成果。

因此：

- `fetch-upstream.sh` 只是**代表你从原始发布页下载**，等价于你自己去 GitHub Releases 下载；
- 本仓库**不镜像、不打包、不再分发**上游译文；
- 如果你想做一个**包含译文的一体化补丁包**并公开分发，请先联系上游作者取得授权，
  或改为「向上游提交 PR，把适配新版本的改动贡献回去」——这是更推荐也更省事的做法。

## 关于 Raycast

Raycast 及其应用资源（界面文案、代码、图标）的权利归 Raycast Systems 所有。
本工具修改的是**你本机已安装副本**的资源文件，属于个人本地化使用：

- 修改后 App 的完整代码签名会失效，可能被 macOS 拦截，风险自负；
- 请**不要**再分发修改后的 App 或其资源文件；
- 若 Raycast 官方或上游作者提出异议，请立即停止使用并还原原版。

## 商标

Raycast 是 Raycast Systems 的商标。本项目与 Raycast Systems 无任何隶属或背书关系。
