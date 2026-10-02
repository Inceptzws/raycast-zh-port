# 常见问题与故障处理

## 0. 一条命令回到原版

```bash
python3 install.py --restore     # 先完全退出 Raycast
```

备份在 `build/backup-original/<Raycast版本>/`，包含安装前所有被替换文件的原始内容与 SHA-256。

---

## 1. 装完 Raycast 打不开 / 窗口不出现（最严重）

**表现**：进程在跑，但热键唤不出窗口；`raycast://` 无反应。

**判定**（日志是最可靠的判据）：

```bash
L=$(ls -t ~/Library/Logs/com.raycast.macos/raycast-x-*.log | head -1)
grep -c "frontend \[main\]" "$L"        # 0 = 前端没启动（有问题）；58+ = 正常
grep -c "Failed to handle deeplink" "$L" # 应尽量为 0
```

**处理**：

```bash
python3 install.py --restore     # 立刻还原
bash bisect.sh                   # 二分定位是哪个文件导致的（结束后会自动还原）
```

定位到文件后，检查该文件里是否存在 `import/require` 路径、对象键等结构性字面量被替换
（正常情况下 `verify.py` 会拦住，如仍出现请提 issue 并附上 `build/report.json`）。

## 2. 提示“已损坏，无法打开”/ 被 Gatekeeper 拦

修改资源会让 App 的完整签名失效，个别机器会被拦。

```bash
python3 install.py --restore
```

还原后如仍异常，用官方安装包覆盖安装一次即可（**不要**关闭系统安全设置、不要重置数据库）。
本工具**不重新签名、不移除隔离标记**，这是刻意的取舍。

## 3. Raycast 更新后变回英文了

预期行为：更新会覆盖被替换的资源。重跑：

```bash
python3 install.py --restore      # 建议先还原，避免旧补丁的恢复工具污染新版本
./fetch-upstream.sh               # 若上游有更新版汉化包
python3 localize.py && python3 verify.py && bash test_install.sh
```

## 4. 提示版本不匹配 / “目标文件不存在”

`localize.py` 会按**当前安装版本**重新对齐；若它报“目标文件不存在”，通常是
Raycast 结构变化较大，或 `build/report.json` 是旧版本生成的。

```bash
rm -rf build/report.json build/patched build/map.tsv
python3 localize.py && python3 verify.py
```

## 5. 汉化不完整，某些地方还是英文

正常，属于已知范围：

- **扩展自身的命令名、商店描述、扩展偏好里的动态文字**：上游对这部分使用「运行时词典注入」机制
  （向 `@raycast/api` 注入约 1.3 万条词典 + 在若干前端 chunk 渲染点包一层查表函数），
  本工具只做字面量替换，未移植该机制；
- **菜单栏原生菜单**：上游也保留英文；
- **上游未复核 / 本机版本新增的文案**：保持英文。

`python3 localize.py` 会打印每个文件的替换条数与命中率，可据此判断覆盖程度。

## 6. 少数地方出现空白 / 布局怪

个别短词被替换后长度变化可能影响排版。请记录出现的界面位置并提 issue；
临时可只还原个别文件：

```bash
cp "build/backup-original/2.6.2.0/<相对路径>" "/Applications/Raycast.app/Contents/Resources/macos-app_RaycastDesktopApp.bundle/Contents/Resources/<相对路径>"
```

## 7. `Permission denied` / 无法写入 `/Applications`

- 确认 Raycast 已**完全退出**（菜单栏图标 → Quit Raycast）；
- 确认 `/Applications/Raycast.app` 属于当前用户（`ls -l /Applications/Raycast.app`）；
- 如果 App 在别的位置，用 `python3 localize.py --app /path/to/Raycast.app` 与
  `python3 install.py --app /path/to/Raycast.app`；
- 如果开了“应用管理”类隐私保护、或用的是受管 Mac，系统可能拒绝修改其他 App，请改用管理员终端执行。

## 8. 如何判断“当前到底汉化了多少”

```bash
python3 install.py --check                              # 已汉化文件数 / 备份情况
python3 -c "import json;d=json.load(open('build/report.json'));m=d['meta'];print(m['patched_files'],'个文件,',m['total_edits'],'条替换, 其中中文',m['cjk_edits'],'条')"
```

## 9. 如何彻底回到官方状态

```bash
python3 install.py --restore
codesign --verify --deep /Applications/Raycast.app && echo "官方签名已恢复"
```

若签名校验仍失败，说明有文件不是原版：用官方安装包重装 Raycast（用户配置与数据库不受影响）。

## 10. 上游汉化包下载失败

`fetch-upstream.sh` 通过 GitHub API 解析最新 release。失败时：

- 检查网络/代理；
- 指定具体 tag：`./fetch-upstream.sh v2.6.0.0`；
- 或手动去 [上游 Releases](https://github.com/zwjtano/raycast-macos-zh-CN/releases)
  下载 zip，解压后把包含 `payload/` 的那层目录放进本仓库的 `patch/`。
