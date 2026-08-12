# Progress Logs

本目录自 Paradigma Harness `0.5.0` 起采用“一次会话一个 append-only 文件”的记录方式。

- [`summary.md`](./summary.md)：由 `pd-compact-progress.py --write` 生成的紧凑索引。
- [`0000-legacy-progress.md`](./0000-legacy-progress.md)：Paradigma 0.7 日志治理边界前的历史汇总，exact-byte baseline 冻结，不得修改。
- `YYYY-MM-DD-<task>.md`：会话源日志，不因压缩而删除或覆写。
