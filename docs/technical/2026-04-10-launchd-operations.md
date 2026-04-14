# 2026-04-10 launchd Operations

> **日期：** 2026-04-10  
> **项目：** `JusticeThemis`  
> **目的：** 把此前“只能生成 plist 模板”的能力推进到“可直接生成安装/卸载/巡检命令”的运维辅助层。

## 1. 这次补了什么

当前 `schedule_template` CLI 不再只输出一个 plist 文件。

现在还可以同时生成：

1. `launchd operation plan json`
2. `launchd setup markdown`

这两份文件会明确写出：

1. `install_path`
2. `copy_command`
3. `load_command`
4. `unload_command`
5. `reload_command`
6. `status_command`
7. `tail_stdout_command`
8. `tail_stderr_command`

## 2. 当前 CLI

命令：

```bash
uv run justice-themis-launchd-template \
  --working-directory /Users/you/path/to/justice-themis \
  --output-path output/com.etherstrings.justice-themis-pipeline.plist \
  --plan-json-path output/launchd-plan.json \
  --plan-markdown-path output/launchd-plan.md
```

## 3. 新增参数

本次新增：

1. `--install-path`
   - 目标安装位置，默认 `~/Library/LaunchAgents/com.etherstrings.justice-themis-pipeline.plist`
2. `--plan-json-path`
   - 输出结构化运维计划
3. `--plan-markdown-path`
   - 输出人工可读的安装说明

## 4. 为什么这一步有价值

之前项目已经能：

1. 抓取新闻
2. 生成固定日报
3. 导出 prompt/MMU handoff

但运维层还差一步：

1. 你知道可以挂 `launchd`
2. 但不知道具体该复制到哪里
3. 也不知道加载、重载、状态检查、查看日志的命令是什么

这次更新后，这些命令被显式化，减少了“模板有了但不会装”的问题。

## 5. 当前边界

这次仍然只做“生成运维计划”，没有自动替你执行：

1. 没有自动 `cp` 到 `~/Library/LaunchAgents`
2. 没有自动执行 `launchctl bootstrap`
3. 没有自动卸载旧 job

原因很简单：

1. 这些操作属于主机级变更
2. 应该由你在确认路径和时区之后再执行

## 6. 推荐使用方式

建议顺序：

1. 先用 `app.schedule_template` 生成 plist 和 plan
2. 检查 plan 里的 `working_directory` 和 `install_path`
3. 再手动执行 `copy/load/status`
4. 初期先观察日志文件，再决定是否长期托管
