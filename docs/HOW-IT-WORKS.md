# 工作原理与事故复盘

## 一、问题定义

Raycast 的界面文案是**编译进 App 资源文件的字符串字面量**（`Contents/Resources/…bundle/Contents/Resources/{frontend,backend,api}` 下的
`frontend/*.js`（Vite 打包 chunk）与 `backend/index.mjs`）。没有语言包、没有 i18n 目录，
所以“汉化”只能是**替换这些字面量**。

难点在于：上游汉化包是针对**某个具体版本**（如 2.6.0.0）制作的，而使用者装的是**另一个版本**（如 2.6.2.0）：

- chunk 文件名带内容哈希，**逐字不同**（`about-settings-view-CZ-8JbGu.js` vs `about-settings-view-C_N4tLpD.js`）；
- 代码有增删，字面量位置会漂移；
- 上游译文是**人工复核**的，不能丢，也不能自己机翻替代。

## 二、移植流水线

### 1) 用 acorn 提字面量，输出字节偏移

`tools/lits.mjs` 解析 JS（`sourceType: module`，`ecmaVersion: latest`），收集：

- `Literal` 且 `typeof value === "string"`（排除正则）；
- **静态** `TemplateLiteral`（`expressions.length === 0`）。

并且**不输出 UTF-16 索引，而输出 UTF-8 字节偏移**。原因：Node 的字符串索引是 UTF-16 码元，
Python 的是码点；只要文件里有一个 emoji 或非 BMP 字符，两侧偏移就会错位，
替换就会落到错误的字节区间上。字节偏移让 Python 直接按 `bytes[start:end]` 切片，永远对齐。

### 2) 骨架对齐

把每个字面量替换成占位符后得到“代码骨架”。**骨架逐字节一致的位置，就是同一处 UI 文案**。
两种互补策略取并集：

| 策略 | 做法 | 特点 |
| --- | --- | --- |
| 锚点（patience diff） | 取两侧都唯一的公共代码片段作为锚点，对锚点做最长递增子序列，再递归 | 精确，但压缩代码里重复片段多时命中偏少 |
| 上下文唯一匹配 | 字面量左右各 96 字符完全相同，且在上游侧唯一 | 覆盖率高，能命中锚点找不到的位置 |

> 注：早期版本用 `difflib.SequenceMatcher(autojunk=False)`，在 3 万+重复片段的序列上会**病态变慢**
> （单文件数分钟不返回），因此改成上面的线性/分治方案。

### 3) 只替换安全类别

`tools/lits.mjs` 给每个字面量打**风险标签**，`localize.py` 只替换 `plain`：

| 类别 | 含义 | 例子 | 处理 |
| --- | --- | --- | --- |
| `spec` | 模块说明符：`import/export from`、动态 `import()`、`require()` 参数 | `"./menu.namespace-ZF2QMukV.js"` | **绝不替换** |
| `key` | 对象属性名、计算成员访问 `obj["x"]`、`switch case` 字面量 | `{"main": …}` | 跳过 |
| `uuid` | UUID 形态 | Sentry `debugIds` 的值 | 跳过 |
| `plain` | 其余字符串（UI 文案） | `"Empty Trash"` | 可替换 |

此外还有两条护栏：

- **插值数量必须一致**（`${` 计数），避免把动态模板替换成静态字符串导致变量丢失；
- **解码值必须真的变化**（避免只改引号风格的无意义改动）。

### 4) 语法保护式替换

替换后立刻用 acorn 复检。若整批替换导致语法错误，则**二分定位出肇事的单条替换并丢弃**，
循环直到语法通过（正常情况下一次就通过）。

### 5) 独立验收（`verify.py`）

| 检查 | 含义 |
| --- | --- |
| 骨架不变式 | 剔除字面量后，汉化文件与原文件**逐字节一致** ⇒ 逻辑、导入、变量名都没被碰 |
| 字面量数量一致 | 替换不增删 token |
| 语法零回归 | 原文件可解析 ⇒ 汉化文件仍可解析 |
| 模块说明符零改动 | `spec` 列表必须与原文件完全相同 |
| 相对说明符可解析 | 汉化文件中的相对 `import` 目标必须真实存在 |

### 6) 功能验收（`test_install.sh`）

静态检查不够，因为**语义性破坏**（例如某个字符串被当作查表键使用）语法上是合法的。
所以最终验收必须实机做：

1. 安装 → 重启 Raycast；
2. 读取 `~/Library/Logs/com.raycast.macos/raycast-x-*.log`，要求出现 `frontend [main]` 启动日志；
3. 触发 `raycast://`，要求出现 `Window did become key`、且无 `Failed to handle deeplink`；
4. **任何一步失败 → 自动 `install.py --restore` 还原**，绝不留半坏状态。

## 三、事故复盘：一行 `import` 让整个前端崩溃

**现象**：安装后 Raycast 进程在跑，但窗口不出现；日志里 `frontend [main]` 行数为 **0**
（正常 58+ 行），`raycast.showMainWindow` 全部超时。

**定位**：`bisect.sh` 二分（判定标准 = `frontend [main]` 行数是否 > 0）缩到**单个文件**：

```
frontend/action-menu-*.js     → frontend 行数=0（坏）
其他所有文件组合              → frontend 行数=58（好）
```

**根因**：该文件里的一条替换是——

```diff
- import { ... } from "./menu.namespace-ZF2QMukV.js"    // 本机 2.6.2.0 自己的 chunk
+ import { ... } from "./menu.namespace-BoSQSTKP.js"    // 上游 2.6.0.0 的 chunk（本机不存在）
```

`import` 语句的代码骨架完全一致，于是“上下文唯一匹配”把**本机 chunk 名**和**上游 chunk 名**当成
同一处文案配了对；两侧的值不同（哈希不同），就被当成“需要替换的字面量”。
模块解析失败 → 该 chunk 加载失败 → 整个前端引导中断。

**修复**：

1. 新增 `spec / key / uuid` 结构性防护（见上表），从源头禁止这类替换；
2. `verify.py` 增加「说明符零改动 + 相对路径必须存在」检查，让同类问题在静态阶段就被拦住；
3. 新增 `test_install.sh` 功能验收与 `bisect.sh` 定位脚本，把“实机可用”变成流水线的硬性关卡。

**教训**：字符串字面量替换的风险不只在“翻错词”，更在**把结构性字符串当成文案**。
所以任何语言移植工具，都必须先做**字面量分类**，再做替换。
