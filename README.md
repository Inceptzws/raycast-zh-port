# Raycast 简体中文汉化移植工具（macOS）

把社区汉化包 [zwjtano/raycast-macos-zh-CN](https://github.com/zwjtano/raycast-macos-zh-CN) 的**已人工复核译文**，
移植到**你本机安装的 Raycast 版本**上（上游通常只适配某个具体旧版本，例如 2.6.0.0）。

> 本仓库**不含**任何 Raycast 资源文件，也**不含**上游汉化包的译文，
> 只包含移植工具链与教程。译文由 `fetch-upstream.sh` 从上游仓库下载（见 [合规说明](THIRD-PARTY-NOTICES.md)）。

---

## 一、先澄清两件事

1. **这不是插件（extension）。** Raycast 扩展只能新增命令，**无法修改 App 自身的界面文案**；官方也没有语言设置项。
   所以“汉化插件”在原理上不存在。
2. **这不是机翻，也不是 100% 全量汉化。** 译文来自上游人工复核成果；覆盖范围是 **Raycast 本体界面**，
   扩展自身的命令名、商店文案等动态内容仍为英文（原因见「局限」一节）。

## 二、效果与覆盖范围

已在 **Raycast 2.6.2.0 (arm64) / macOS 26.x** 上实测：

| 项目 | 结果 |
| --- | --- |
| 生成并安装的汉化文件 | 187 个 |
| 替换字符串 | 7412 条（其中含中文 6893 条） |
| 静态验收 | 骨架不变式 187/187、语法零回归、模块说明符零改动 |
| 功能验收 | 前端正常启动、主窗口弹出、搜索框显示「搜索应用和命令…」 |

覆盖：主窗口、设置、欢迎页、AI 相关界面、动作面板、空状态、笔记、代码片段、剪贴板、更新日志等。

不覆盖：扩展自身的命令名/描述、扩展商店文案、扩展偏好里的动态文字、菜单栏原生菜单、
以及上游尚未复核的文案。

## 三、前置要求

| 依赖 | 要求 | 说明 |
| --- | --- | --- |
| macOS | Apple Silicon（arm64） | 上游 payload 仅提供 arm64 |
| Raycast | 已安装（任意 2.6.x 均可尝试） | 脚本会自动对齐当前安装版本 |
| Python | 3.9+ | 移植与验收脚本 |
| Node.js | 18+ | 用 acorn 精确解析 JS 字面量 |
| curl / unzip | 系统自带 | 下载并解压上游汉化包 |

## 四、快速开始

```bash
# 0) 取得本仓库
git clone <你的仓库地址> && cd raycast-zh-port

# 1) 安装依赖（只需一次；acorn 用于解析 JS）
./setup.sh

# 2) 下载上游汉化包（默认最新版；也可指定 tag，如 v2.6.0.0）
./fetch-upstream.sh

# 3) 生成汉化文件（只写 build/patched/，不动 /Applications）
python3 localize.py

# 4) 静态验收：骨架不变式 / 语法 / 模块说明符 / 抽样对照
python3 verify.py

# 5) 完全退出 Raycast（菜单栏图标 → Quit Raycast），然后安装 + 功能验收
bash test_install.sh
```

`test_install.sh` 会：备份原文件 → 覆写汉化文件 → 重启 Raycast →
检查前端是否真的启动、主窗口是否弹出；**一旦失败立即自动还原**，不会把你的 Raycast 留成半坏状态。

安装完成后按你的 Raycast 热键（或点菜单栏图标）即可看到中文界面。

## 五、命令一览

| 命令 | 作用 |
| --- | --- |
| `./setup.sh` | 检查 python3/node，安装 acorn |
| `./fetch-upstream.sh [tag]` | 下载上游汉化包到 `patch/`（默认最新 release） |
| `python3 localize.py` | 生成汉化文件到 `build/patched/`，输出替换明细 |
| `python3 verify.py` | 静态验收（含「模块说明符必须原样且真实存在」检查） |
| `python3 install.py --check` | 查看当前是否已汉化、备份情况 |
| `python3 install.py` | 安装（需先完全退出 Raycast） |
| `python3 install.py --restore` | **一键还原原版** |
| `bash test_install.sh` | 安装 + 重启 + 功能验收（失败自动还原） |
| `bash bisect.sh` | 出问题时二分定位是哪个文件导致前端失效 |

## 六、工作原理（简述）

1. 用 **acorn** 解析上游 payload 与本机 Raycast 的 JS，提取所有字符串字面量的
   **UTF-8 字节偏移**（避免 JS UTF-16 与 Python 码点错位）。
2. 把字面量挖空后比较「代码骨架」：骨架逐字节一致的位置，就是同一处 UI 文案。
   对齐使用两种互补策略取并集：代码片段锚点（patience diff）+ 左右 96 字符上下文唯一匹配。
3. 只替换**安全类别**的字面量，以下结构性位置一律跳过，避免把逻辑改坏：
   - `spec`：`import/export from`、动态 `import()`、`require()` 的模块说明符
   - `key`：对象属性名、计算成员访问的键、`switch case` 字面量
   - `uuid`：Sentry debug id 之类
4. 替换后必须通过 acorn 语法复检；若某条替换破坏语法，二分定位并丢弃该条。
5. 独立验收：骨架不变式、字面量数量一致、语法零回归、模块说明符零改动且相对路径真实存在。

细节与一次真实事故复盘见 [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)。

## 七、Raycast 升级之后

Raycast 一更新，被替换的资源会被覆盖，界面回到英文——**这是预期行为**。重跑即可：

```bash
python3 install.py --restore    # 可选：升级前先还原（推荐）
./fetch-upstream.sh             # 若上游发布了新版本汉化包
python3 localize.py && python3 verify.py && bash test_install.sh
```

本工具链**与版本无关**：它总是拿上游 payload 去对齐你**当前安装**的版本，覆盖率会打印出来。
如果 Raycast 大版本改动很大，命中率会下降，但仍只会替换能确定对齐的文案，不会乱替换。

## 八、局限

- **扩展内容仍是英文**：上游对商店文案使用「运行时词典注入」机制
  （向 `@raycast/api` 注入约 1.3 万条英中词典 + 在若干前端 chunk 的渲染点包一层查表函数）。
  本工具只做字面量替换，未移植该运行时机制。
- **签名失效**：修改资源后 App 的完整签名校验必然失败，可能出现“已损坏”提示。
  本工具**不重新签名、不关闭系统安全保护**；如被拦截请立刻 `install.py --restore`。
- **上游未覆盖的新文案**会保持英文。

## 九、常见问题

见 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)：Raycast 打不开 / 窗口不出现 / 提示已损坏 /
不知道汉化了多少 / 想彻底还原官方版本 / `Permission denied` 等。

## 十、贡献者

| 贡献者 | 角色 |
| --- | --- |
| [@Inceptzws](https://github.com/Inceptzws) | 需求、实机验证、发布维护 |
| **DeepSeek**（AI 编程助手，deepseek-flash 模型） | 工具链设计与实现：acorn 字面量提取、字节级骨架对齐、结构性安全防护、静态验收、功能验收与二分定位脚本，以及本文档 |

协作方式：由 @Inceptzws 提出目标与验收标准，DeepSeek 负责设计并实现全部脚本，
所有产物都在真机上通过「前端启动 + 窗口弹出」的功能验收后才落地。

## 十一、免责声明与致谢

- 本仓库仅包含**原创工具链**，采用 [MIT 许可证](LICENSE)。
- 译文版权归上游作者 [@zwjtano](https://github.com/zwjtano) 所有，本仓库**不分发**其成果。
- Raycast 及其应用资源的权利归 Raycast Systems 所有；本工具修改的是**你本机已安装的副本**，请自行评估风险，勿再分发修改后的 App 资源。
- 详细条款见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。

---

## English summary

A **version-agnostic porter** that applies the reviewed translations of the community
Simplified-Chinese patch for Raycast to *your currently installed* Raycast build.

- It is **not** a Raycast extension: extensions cannot localize Raycast's own UI.
- It extracts string literals with **acorn** (UTF-8 byte offsets), aligns code skeletons
  (patience anchors + unique 96-char context), and only rewrites **safe** literals —
  module specifiers, object keys, computed keys, `switch case` literals and UUIDs are never touched.
- Every build is validated statically (skeleton invariant, zero syntax regressions,
  module specifiers unchanged and resolvable) and **functionally** (`test_install.sh` checks the
  frontend really boots and auto-restores on failure).
- This repo ships **no** Raycast resources and **no** upstream translations;
  `fetch-upstream.sh` downloads the upstream payload from its original repository.

`./setup.sh && ./fetch-upstream.sh && python3 localize.py && python3 verify.py && bash test_install.sh`
