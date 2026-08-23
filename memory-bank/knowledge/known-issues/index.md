# Known-Issues Index

<!-- BEGIN PARADIGMA AUTO-INDEX -->
<!-- checksum: 32c0b1fe78d527b8 -->
<!-- generated_by: pd-index.py -->

| Path | Type | Title | Hints | Symbols | Relations |
|------|------|-------|-------|---------|-----------|
| [ki-001-environment-toolchain.md](ki-001-environment-toolchain.md) | `paradigma-known-issue` | KI-001: 环境与工具链问题 | 环境问题<br>工具链<br>Windows ... | - | - |
| [ki-002-architecture-boundaries.md](ki-002-architecture-boundaries.md) | `paradigma-known-issue` | KI-002: 架构边界（易误判非 Bug） | 架构边界<br>Legacy E<br>图引擎 ... | - | - |
| [ki-003-test-baseline-drift.md](ki-003-test-baseline-drift.md) | `paradigma-known-issue` | KI-003: 测试基线漂移 | 测试基线<br>pytest<br>Playwright ... | - | - |
| [ki-004-production-deployment.md](ki-004-production-deployment.md) | `paradigma-known-issue` | KI-004: 生产与部署注意事项 | 生产部署<br>环境变量<br>回滚 ... | - | - |
| [ki-005-graph-engine-issues.md](ki-005-graph-engine-issues.md) | `paradigma-known-issue` | KI-005: 图引擎已知问题 | 图引擎<br>ORM 懒加载<br>max_iterations | - | - |
| [ki-006-report-center-history.md](ki-006-report-center-history.md) | `paradigma-known-issue` | KI-006: 汇报中心历史问题 | 汇报中心<br>PostgreSQL enum<br>ORM | - | - |
| [ki-007-windows-playwright-excluded-port.md](ki-007-windows-playwright-excluded-port.md) | `paradigma-known-issue` | KI-007: Windows 保留端口导致 Playwright webServer EACCES | Playwright EACCES<br>4173 端口<br>Windows 保留端口 ... | - | - |
| [ki-008-docker-frontend-dependency-volume.md](ki-008-docker-frontend-dependency-volume.md) | `paradigma-known-issue` | KI-008: Docker 前端依赖命名卷可能滞后于 lockfile | Vite import-analysis<br>Docker 缺少依赖<br>node_modules 命名卷 ... | - | - |
| [ki-009-standalone-action-dual-track.md](ki-009-standalone-action-dual-track.md) | `paradigma-known-issue` | KI-009: Standalone Work Item 动作授权双轨 | standalone<br>开始处理<br>创建人 ... | - | - |
| [ki-010-activity-timeline-redesign.md](ki-010-activity-timeline-redesign.md) | `paradigma-known-issue` | KI-010: 活动时间线需重做为更有指向性的留痕 | 活动时间线<br>折叠<br>留痕 ... | - | - |
| [ki-011-system-admin-business-boundary.md](ki-011-system-admin-business-boundary.md) | `paradigma-known-issue` | KI-011: 系统管理员与业务参与权限尚未解耦 | 管理员业务边界<br>系统管理员<br>管理员不参与业务 ... | - | - |
| [ki-012-security-scan-release-blockers.md](ki-012-security-scan-release-blockers.md) | `paradigma-known-issue` | KI-012: 2026-08-09 安全扫描发现与上线阻断项 | 安全扫描<br>上线阻断<br>IDOR ... | - | - |
| [ki-013-paradigma-product-version-collision.md](ki-013-paradigma-product-version-collision.md) | `paradigma-known-issue` | KI-013: Paradigma 与 Filum 根 VERSION 语义冲突 | Paradigma 版本冲突<br>产品 VERSION<br>升级 Profile ... | - | caused_by:../decisions/adr-007-paradigma-alignment.md<br>related_to:../decisions/adr-021-paradigma-070-cli-runtime.md |
| [ki-014-postgresql-alembic-schema-drift.md](ki-014-postgresql-alembic-schema-drift.md) | `paradigma-known-issue` | KI-014: PostgreSQL Alembic autogenerate schema drift | Alembic check<br>schema drift<br>PostgreSQL 漂移 ... | - | - |
| [ki-015-strict-projection-missing-telemetry.md](ki-015-strict-projection-missing-telemetry.md) | `paradigma-known-issue` | KI-015: Strict 投影缺口缺少请求侧显式遥测 | strict 投影缺失<br>fail-closed<br>任务隐藏 ... | - | related_to:../contracts/projection-contract.md<br>depends_on:../plans/2026-08-12-iteration5d-operations-observability-plan.md |
| [ki-016-logout-inflight-request-401-noise.md](ki-016-logout-inflight-request-401-noise.md) | `paradigma-known-issue` | KI-016: 登出与多账号切换存在在途请求 401 噪声 | 登出 401<br>多账号切换<br>Axios 未处理拒绝 ... | - | related_to:../domains/architecture/frontend-architecture.md<br>related_to:ki-003-test-baseline-drift.md |
| [ki-017-frontend-entry-chunk-size.md](ki-017-frontend-entry-chunk-size.md) | `paradigma-known-issue` | KI-017: 前端入口 Chunk 仍超过 500 KiB | Vite chunk 过大<br>前端包体积<br>入口 JS ... | - | related_to:../domains/architecture/frontend-architecture.md |
| [known-issues.md](known-issues.md) | `paradigma-known-issue` | 已知问题合辑 (已拆分) | 已知问题<br>合辑<br>known issue | - | - |

<!-- END PARADIGMA AUTO-INDEX -->

## Resolved Audit Issues

| Batch | Status | Resolution |
|-------|--------|------------|
| Task Center P0 (`cba64aa`) | ✅ Resolved | Missing row locks/CAS and template priority validation |
| Task Center P1 batch 1 (`3002275`) | ✅ Resolved | Pagination tiebreaker, atomic attachment commit, datetime normalization |
| Task Center P1-10 (`4398439`) | ✅ Resolved | Self-review prevention with fallback reviewer chain and audited admin reassignment |
| Task Center P2-11/P2-13 (`0.92.1`) | ✅ Resolved | Graph source-type collision guard and historical permission-branch documentation |

## Verification pending — Standalone action dual-track

| ID | Status | Note |
|----|--------|------|
| [KI-009](ki-009-standalone-action-dual-track.md) | 🟢 Engineering fixed / retest pending | standalone 前端与状态命令已统一按 `available_actions`；待创建者/执行人/验收人多账号人工复测 |

## Open — Activity timeline UX

| ID | Status | Note |
|----|--------|------|
| [KI-010](ki-010-activity-timeline-redesign.md) | 🟡 Deferred | 默认折叠已落地；后续重做更有指向性的活动留痕 |

## Open — System admin business boundary

| ID | Status | Note |
|----|--------|------|
| [KI-011](ki-011-system-admin-business-boundary.md) | 🟡 Deferred | Admin 产品定义为纯系统维护角色；当前业务候选/override 兼容行为在 I4 后单独治理 |
