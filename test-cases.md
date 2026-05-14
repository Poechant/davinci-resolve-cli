# davinci-resolve-cli 测试用例

基于 M1 里程碑的 18 条验收标准展开。

约定：
- `unit/` 用 `FakeResolve` fixture，断言命令对桥接层的调用与对 stdout 的输出
- `integration/` 标记 `@pytest.mark.integration`，依赖本机运行中的 Resolve 18+
- 所有 JSON 输出用 jsonschema 校验契约

---

## 环境与发布（T1 / T7）

### AC1 — pipx 安装即用
- [ ] **U1.1**: `pyproject.toml` 声明 `console_scripts: dvr = dvr.cli:app`
- [ ] **U1.2**: `pyproject.toml` 仅依赖 `typer`, `rich`, `pyyaml`, `jsonschema`，不强依赖 `DaVinciResolveScript`（运行时探测）
- [ ] **I1.1**: 在干净 venv 中 `pip install .` 后 `dvr --version` 能输出版本号
- [ ] **I1.2**: 未设置 `RESOLVE_SCRIPT_API` / `PYTHONPATH` 时 `dvr doctor` 也能跑出诊断（bootstrap 自动探测）

### AC2 — doctor 诊断报告
- [ ] **U2.1**: `dvr doctor` 输出含字段 `{resolve_running, version, edition, api_path, bridge_status, issues[]}`
- [ ] **U2.2**: `--format json` 时输出严格符合 doctor schema
- [ ] **U2.3**: 各 issue 项必带 `code` 与 `hint`
- [ ] **I2.1**: Resolve 已运行时 `bridge_status == "ok"`、`version` 非空

### AC3 — 统一错误码 / 无 stack trace
- [ ] **U3.1**: 模拟 `bootstrap` 抛 `ResolveNotRunning` → 命令以 exit code 2 退出，stderr 输出 `{"errorCode":"resolve_not_running",...}`
- [ ] **U3.2**: 模拟 API 不可达 → `api_unavailable` + exit code 2
- [ ] **U3.3**: 模拟版本 <18 → `version_unsupported` + hint 含升级提示 + exit code 1
- [ ] **U3.4**: 所有命令在异常路径下不输出 Python traceback（除非 `DVR_DEBUG=1`）

---

## Project 命令族（T2）

### AC4 — project list/open/new/close/save/export/import
- [ ] **U4.1**: `project list` 调用 `ProjectManager.GetProjectsInCurrentFolder()`，输出 `[{name, modifiedAt}]`
- [ ] **U4.2**: `project open <name>` 调用 `LoadProject(name)`，失败时 `not_found` 错误
- [ ] **U4.3**: `project new <name>` 调用 `CreateProject(name)`；重名时 `validation_error`
- [ ] **U4.4**: `project close` 调用 `CloseProject(currentProject)`，无打开项目时 `validation_error`
- [ ] **U4.5**: `project save` 调用 `Project.SaveProject()`，返回 `{saved: true, path}`
- [ ] **U4.6**: `project export <path>` 调用 `ExportProject(name, path)`
- [ ] **U4.7**: `project import <path>` 调用 `ImportProject(path)`
- [ ] **U4.8**: 所有子命令支持 `--format json`

### AC5 — project current 元信息
- [ ] **U5.1**: `project current` 输出 `{name, timelineCount, framerate, resolution: {width,height}}`
- [ ] **U5.2**: 无项目时 `validation_error: no_project_open`

---

## Media 命令族（T3）

### AC6 — media import 批量导入
- [ ] **U6.1**: `media import <path>` 调用 `MediaPool.ImportMedia([path])`，返回 `{imported:[clipId...], failed:[{path,reason}]}`
- [ ] **U6.2**: `--bin <name>` 时先 `GetCurrentFolder()` 切换到目标 bin，不存在则 `validation_error`
- [ ] **U6.3**: `--recursive` 时枚举目录下所有支持的扩展名（mov/mp4/wav/r3d/braw/...）
- [ ] **U6.4**: 部分失败时 exit code = 0（视为部分成功），失败明细在 stdout `failed[]`

### AC7 — media list
- [ ] **U7.1**: `media list` 输出 `[{id,name,resolution,duration,codec,tags[]}]`
- [ ] **U7.2**: `--bin <name>` 过滤 bin；`--filter` 支持 codec/resolution 简单过滤

### AC8 — media tag 批量打标签
- [ ] **U8.1**: `media tag <clipId>... --add <tag>` 调用 `MediaPoolItem.AddFlag(color)`（或自定义元数据字段）
- [ ] **U8.2**: 部分失败时输出失败 `[{clipId, reason}]`，成功项不回滚
- [ ] **U8.3**: 多个 clipId 时事务性逐项执行

---

## Render 命令族（T4）

### AC9 — render presets
- [ ] **U9.1**: `render presets` 调用 `Project.GetRenderPresetList()`，输出 `[name...]`

### AC10 — render submit 异步
- [ ] **U10.1**: `render submit --preset <p> --timeline <id> --output <path>` 调用 `Project.LoadRenderPreset(p)` + `Project.SetRenderSettings({TargetDir,TargetFileName})` + `Project.AddRenderJob()`
- [ ] **U10.2**: 立即返回 `{jobId, status:"queued", submittedAt}`，不阻塞
- [ ] **U10.3**: 同步写入 `~/.dvr/jobs.json`，schema 含 `{jobId, project, timeline, preset, output, submittedAt, status}`
- [ ] **U10.4**: `--start` flag 时额外调用 `Project.StartRendering([jobId])`（非阻塞）

### AC11 — render status/list/wait/cancel
- [ ] **U11.1**: `render status <id>` 输出 `{jobId, status, progress, estimatedTimeRemaining}`
- [ ] **U11.2**: `render list` 列本地 `~/.dvr/jobs.json` 中所有任务 + 当前 Resolve 中 `GetRenderJobList()`，合并展示
- [ ] **U11.3**: `render wait <id>` 轮询至终态（completed/failed/cancelled），默认间隔 1s，可 `--interval`
- [ ] **U11.4**: `render wait` 实时进度到 stderr（不污染 stdout）
- [ ] **U11.5**: `render cancel <id>` 调用 `Project.StopRendering()`（若运行中）+ `DeleteRenderJob(id)`，落库标记 cancelled
- [ ] **U11.6**: 未知 jobId → `not_found` + exit code 1

---

## Timeline 命令族（T5）

### AC12 — timeline list/current/open/new
- [ ] **U12.1**: `timeline list` → `Project.GetTimelineCount()` + 循环 `GetTimelineByIndex`，输出 `[{id,name,fps,resolution}]`
- [ ] **U12.2**: `timeline current` → `Project.GetCurrentTimeline()`
- [ ] **U12.3**: `timeline open <name>` → 遍历定位 + `SetCurrentTimeline`
- [ ] **U12.4**: `timeline new <name> --fps <fps>` → `MediaPool.CreateEmptyTimeline(name)`（fps 通过 Project SetSetting）

### AC13 — timeline clips
- [ ] **U13.1**: `timeline clips <id>` 遍历每条轨道（video/audio/subtitle）+ `GetItemListInTrack()`，输出 `[{trackType,trackIndex,start,end,source:{clipId,name}}]`
- [ ] **U13.2**: timecode 输出统一 `HH:MM:SS:FF` 字符串 + `frames` 整数双字段

### AC14 — timeline cut/move/marker add
- [ ] **U14.1**: `timeline cut --at <TC>` 调用 `Timeline.AddMarker` 或 razor-cut 等价 API（封装在 resolve.py），所有命令幂等
- [ ] **U14.2**: `timeline move --clip <id> --to <TC>` 移动 clip 起始位置
- [ ] **U14.3**: `timeline marker add --at <TC> --note <text>` 调用 `Timeline.AddMarker(frame, color, name, note, duration)`

### AC15 — dry-run
- [ ] **U15.1**: 所有写操作（cut/move/marker add/import/tag/render submit）支持 `--dry-run`
- [ ] **U15.2**: `--dry-run` 时输出 `{planned:[{action, args}]}` 但不调用任何 Resolve API（FakeResolve 上断言无 mutating call）

---

## 输出与 Agent 友好（T1 横切）

### AC16 — --format & DVR_OUTPUT
- [ ] **U16.1**: 默认 TTY 时 `--format table`，重定向 / 非 TTY 时 `--format json`
- [ ] **U16.2**: `DVR_OUTPUT=yaml` 覆盖默认
- [ ] **U16.3**: 显式 `--format` 优先级最高
- [ ] **U16.4**: table 渲染走 rich，yaml 走 PyYAML safe_dump，json 走 stdlib `json.dumps(ensure_ascii=False, indent=2)`

### AC17 — SKILL.md（T6）
- [ ] **U17.1**: 仓库根含 `SKILL.md`，frontmatter 含 `name`、`description`、`commands`
- [ ] **U17.2**: 包含 5 个范例：「渲染当前时间线为 mp4」「列出今天导入的素材」「批量给一个 bin 的素材打 review tag」「等待指定 jobId 完成并打印结果」「检查 Resolve 是否就绪」
- [ ] **U17.3**: 安装后 `dvr skill install` 可拷贝到 `~/.config/dvr/skill/`（可选）

### AC18 — 结构化错误 + sysexits
- [ ] **U18.1**: 所有错误 stderr 输出 `{"errorCode","message","hint"}` JSON
- [ ] **U18.2**: 退出码映射：0/1/2/3 + sysexits.EX_USAGE
- [ ] **U18.3**: schema 测试：任何错误输出都符合 error.schema.json

---

## 跨横切

- [ ] **X1**: 所有命令的 `--help` 文本含一行 example
- [ ] **X2**: `dvr completion <shell>` 输出 bash/zsh 补全脚本（typer 自带，仅需暴露）
- [ ] **X3**: 所有 JSON 输出经 jsonschema 验证（每命令一个 schema）
- [ ] **X4**: `tests/conftest.py` 提供的 FakeResolve fixture 在 unit 测试中保证 0 真实 Resolve 调用
