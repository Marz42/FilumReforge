# Progress Logs

本目录自 Paradigma Harness `0.5.0` 起采用“一次会话一个 append-only 文件”的记录方式。

- [`summary.md`](./summary.md)：由 `pd-compact-progress.py --write` 生成的紧凑索引。
- [`progress.md`](./progress.md)：升级前历史汇总，只读保留，不再追加。
- `YYYY-MM-DD-<task>.md`：会话源日志，不因压缩而删除或覆写。

