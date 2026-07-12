# Project Filum 测试覆盖评估

**日期**: 2026-07-10
**代码基线**: `main` @ `42df37b`（工作区含本轮文档/测试修复）
**说明**: 当前仓库没有行覆盖率/分支覆盖率工具配置；本报告评估的是测试资产、可执行基线与关键场景覆盖。

## 1. 结论

测试资产数量较多，核心任务/图引擎/视频流程已有服务、API、Vitest 与 Playwright 多层覆盖；但目前不能给出可信的百分比覆盖率，也没有 CI 强制质量门。当前本机依赖状态还阻止了后端全量 pytest和前端全量 Vitest/E2E 的绿色复现。

**总体判断**: 场景覆盖中等偏高，覆盖治理成熟度偏低。进入 S-01 前应先恢复可复现测试环境，并为 0.92.0 后新增能力补直接回归。

## 2. 测试资产

| 层级 | 当前资产 | 本轮结果 |
|---|---|---|
| Backend pytest | 42 个 `test_*.py`，约 290 个声明测试函数 | 未执行：`.venv` 绑定到已不存在的 Python 3.11 路径 |
| Frontend Vitest | 52 个测试文件（45 `tests/*.spec.ts` + 7 `src/*.test.ts`） | 全量发现 103 用例：43 文件/102 用例通过；8 文件因缺依赖未加载；1 个旧断言失败后已修复并定向 2/2 通过 |
| Playwright default mock | 35 tests / 9 files | `--list` 成功；未执行，当前 `node_modules` 缺 `mammoth`/`marked`/`xlsx` |
| Playwright task-center | 39 tests / 6 files | `--list` 成功，未执行 |
| Playwright all | 77 tests / 14 files | `--list` 成功，未执行 |
| Playwright live | 8 tests / 2 files | `--list` 成功，未执行（需 Docker/backend） |
| Workflow-video UAT | 24 tests / 4 files | `--list` 成功，未执行 |

## 3. 覆盖治理缺口

1. **无覆盖率工具**
   - `backend/pyproject.toml` 未声明 `pytest-cov` / `coverage.py`。
   - `frontend/package.json` 未声明 `@vitest/coverage-v8`，也没有 coverage script/threshold。
2. **无 CI**
   - 仓库没有 `.github/workflows/`，pytest、Vitest、type-check、build、Playwright 均未被远端自动阻断。
3. **发布检查可跳过后端测试**
   - `scripts/check-release.sh` 在运行环境缺 pytest 时仅 WARN，生产 runtime 环境可以在没有执行 backend tests 的情况下通过其余检查。
4. **本地依赖不可复现**
   - `backend/.venv/pyvenv.cfg` 指向不存在的 Python 3.11。
   - `frontend/package-lock.json` 包含 `mammoth`/`marked`/`xlsx`，但当前 `node_modules` 未安装它们；应以干净 `npm ci` 恢复，而不是改业务代码规避。

## 4. 近期变更的直接覆盖缺口

以下 0.92.0 后变更未找到针对其关键行为的直接测试锚点：

| 变更 | 缺失测试 |
|---|---|
| 图模板 `scope_department_ids` | 非 Admin 列表过滤、实例化越权拒绝、空数组兼容、seed scope 推导 |
| 图模板删除 | Admin 删除无 Run 模板、有 Run 冲突、非 Admin 越权、前端按钮禁用/确认 |
| 附件 MIME 推断 | 空/`application/octet-stream` 的 `.md`/`.docx` 推断、未知扩展保持安全 |
| 上游交付物附件继承 | 显式 SQL 查询避免 lazy-load、去重创建 `AttachmentLink`、无附件/多上游边界 |
| 关闭采集 Task 投影同步 | 被终止采集 Task 置 Done、`latest_capture_state=closed_by_manager`、重复关闭幂等 |
| `PublishTaskDialog` / `CapturePanel` | 缺直接组件单测；目前主要依赖页面/E2E 间接覆盖 |

已有覆盖较明确的领域包括：B-12 API 404、图条件/Context/Wait-Any/深度打回、任务中心 stats 基础 summary/workload、跨部门路由、模板链、F-24 调度、F-29 归档，以及视频 W0–W10 主干。

## 5. S-01 前置测试建议

S-01 不应只补 UI happy path，至少应先设计以下测试矩阵：

- 周期边界：日/周/月、跨月/跨年、Asia/Shanghai 与 UTC、闭区间规则。
- 权限：个人、部门经理、HR/Admin、无权部门、跨部门任务。
- 统计口径：完成率、逾期率、取消/归档、延期、无截止时间、重复/重开任务。
- rollup：实时查询与持久化聚合一致性、迟到更新、回填、幂等重算。
- 绩效入口：指标仅作辅助证据，不直接将系统统计等同于最终绩效结论。
- 前端：空数据、加载/失败、筛选、趋势对比、深链与导出（若立项包含）。

## 6. 建议顺序

1. 重建 backend dev venv，执行全量 pytest；前端执行干净 `npm ci` 后重跑 Vitest/default Playwright。
2. 补上述 0.92.0 后六组直接回归，优先 scope/delete/MIME/附件继承。
3. 引入 `pytest-cov` 与 `@vitest/coverage-v8`，先记录 baseline，再由团队确认阈值；不建议未经基线直接拍高阈值。
4. 新增 CI：backend tests、frontend unit/type-check/build 为必选；Playwright mock 可作为必选或独立 job；live/docker 作为定时或发布闸门。
5. 再开始 S-01 产品口径和测试先行实现。

## 7. 后续实施结果（2026-07-10 23:06）

- backend `.venv` 已用 Python 3.12.13 重建，`pip install -e ".[dev]"` 成功。
- frontend 已执行干净 `npm ci`；发现 11 个 npm audit 漏洞与 Vite/devtools peer warning，未自动改锁文件。
- 修复后全量基线：backend **293 collected / 282 passed / 11 skipped**；Vitest **54 文件 / 143 用例**；Playwright default mock **35/35**；type-check/build PASS。
- 已补直接回归：`scope_department_ids`、图模板删除、MIME 推断、上游附件继承、关闭采集 Task 投影、PublishTaskDialog、CapturePanel。
- 额外修复：附件模块导入 NameError、Wait-Any 完成态、手动图实例完成态、seed 原地同步判断、watcher 缓存与 PostgreSQL constraint 名称长度。
- 尚未实施：pytest/Vitest 覆盖率百分比工具、CI、Playwright live/docker-gui、npm audit 风险处置。
