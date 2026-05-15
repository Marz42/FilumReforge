# Docker Compose 端到端（GUI）功能验证清单

面向 **开发 Compose**（`docker-compose.yml`）：浏览器拟真操作 + **组织架构分层**（L0 管理员 → HR → 一级部门负责人 → 二级团队负责人 → 一线员工 + 侧翼部门）。  
默认入口 **`http://127.0.0.1:8080`**（须与 `FRONTEND_APP_URL` 一致，见 `docker-compose.yml`）。  
Demo 账号与部门树见仓库根目录 [README.md](../../README.md)「测试组织与 demo 账号」；结构定义见 [backend/app/services/sample_data_service.py](../../backend/app/services/sample_data_service.py)。

**统一演示密码（seed 时指定）**：与根 README 一致，建议使用 `FilumTest123!`。

### 自动化子集（截图 + report.md）

在 **Cursor Agent 模式** 或本地终端可对运行中的 `http://127.0.0.1:8080` 执行 Playwright，生成 `verification-runs/docker-gui-<时间戳>/screenshots` 与 `report.md`。  
具体命令与需落库的文件清单见 [memory-bank/handbooks/e2e-gui-verification-automation-runbook.md](../../memory-bank/handbooks/e2e-gui-verification-automation-runbook.md)。  
当前会话若处于仅 Markdown 可写限制，请按该 runbook 在 Agent 模式下补全 `frontend/playwright.docker-gui.config.ts` 与 `frontend/e2e/docker-gui-verification/*.spec.ts` 后执行。

---

## A. 环境与数据前置（env-up-seed）

| # | 步骤 | 操作 / 命令 | 通过 |
|---|------|-------------|------|
| A1 | 准备 env | `cd infra/docker` → `cp .env.example .env` → 填写 `JWT_SECRET_KEY`（≥32 字符） | [ ] |
| A2 | 确认邀请 URL 基址 | 经 **8080** 演练时保持 `FRONTEND_APP_URL=http://127.0.0.1:8080`（或与 compose 默认值一致）；仅直连 Vite **5173** 时改为 `http://127.0.0.1:5173` | [ ] |
| A3 | 启动栈 | `docker compose -f docker-compose.yml up --build -d` | [ ] |
| A4 | 服务健康 | `docker compose -f docker-compose.yml ps` → `backend`、`worker`、`postgres`、`redis` 为 healthy（nginx/frontend 依项目定义） | [ ] |
| A5 | API 经网关 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/api/v1/health` 期望 `200`（`/api/` 反代到 backend；`/healthz` 在 FastAPI 根路径未挂在 `/api/` 下，经 Nginx 8080 不会命中 backend） | [ ] |
| A6 | 迁移 + 演示数据 | `docker compose -f docker-compose.yml exec backend python -m app.scripts.seed_sample_data --password 'FilumTest123!'` | [ ] |
| A7 | 首次无管理员 | 若脚本输出已初始化管理员，用 `admin@example.com` + 你设置的密码登录；否则先走 `/login` 完成 bootstrap 后再 seed | [ ] |

---

## B. 分层权限矩阵（matrix-l0-l4）

在浏览器 **无痕/多配置文件** 中分别登录，勾选 **菜单可见性** 与 **越权访问**（直接访问 URL 应被拒或重定向）。

| 层级 | 账号 | 密码 | `/departments` | `/people` | `/task-center` 建立任务 | `/reports` | `/messages` |
|------|------|------|----------------|-----------|-------------------------|------------|-------------|
| L0 | `admin@example.com` | seed / 自设 | 可见且可维护 | 可见 | 跨部门可发（视能力） | 可见 | 可见 |
| L1-HR | `demo.hr@example.com` | `FilumTest123!` | **不可见**或拒访 | 可见 | 依 HR 范围 | 可见 | 可见 |
| L1-HR | `demo.hrbp@example.com` | 同上 | 同上 | 可见 | 同上 | 可见 | 可见 |
| L2 | `demo.tech.director@example.com` | 同上 | 同上 | 依策略 | 技术中心范围内 | 可见 | 可见 |
| L3 | `demo.platform.lead@example.com` | 同上 | 同上 | 依策略 | 组内/范围 | 可见 | 可见 |
| L4 | `demo.engineer.a@example.com` | 同上 | **不可** | **不可** | 仅协作侧 | 可见 | 可见 |
| 侧翼 | `demo.success@example.com` | 同上 | **不可** | **不可** | 本人相关 | 可见 | 可见 |

| # | 步骤 | 通过 |
|---|------|------|
| B1 | L4 访问 `/departments`、`/people` 应无菜单或 403/重定向 | [ ] |
| B2 | L1 访问 `/departments` 应拒访 | [ ] |
| B3 | L0 在 `/departments` 可查看部门树（总部 → 人力运营中心 / 技术中心 / 客户成功部 / 财务行政部；技术中心 → 平台研发组） | [ ] |

---

## C. 业务闭环：任务 + 汇报 + 消息（flow-task-report-msg）

记录每条：**操作账号、时间、任务/汇报标题关键字**，便于在 `/messages` 中按来源回跳核对。

### C1 任务中心（跨层级）

| # | 步骤 | 操作要点 | 通过 |
|---|------|----------|------|
| C1.1 | 指派 | **L2** 或 **L3** 登录 → `/task-center` → 页头「建立任务」→ 指派给 **L4**（`demo.engineer.a@example.com`），设截止时间与标题前缀如 `[E2E-T1]` | [ ] |
| C1.2 | 待办 | **L4** 登录 →「待处理」出现该任务 | [ ] |
| C1.3 | 握手 / 流转 | 若存在接单流程：L4 **接单** → **进行中** → 提交交付 / 验收路径（依界面）；否则完成至 **Done** 或等价状态 | [ ] |
| C1.4 | 转派 | **L3** 将任务转给 **另一工程师**（`demo.engineer.b@example.com`）；双方「跟踪」与创建人视图一致 | [ ] |
| C1.5 | 跨部门 | **L2** 向 `demo.success@example.com` 建任务 `[E2E-XDEPT]`；客户成功账号仅在自己待办出现 | [ ] |
| C1.6 | 消息 | **L4**、**L2** 打开 `/messages` → 来源筛选 → **回到来源** 跳转任务中心/任务详情 | [ ] |

### C2 汇报中心（汇报线）

| # | 步骤 | 操作要点 | 通过 |
|---|------|----------|------|
| C2.1 | 向上汇报 | **L4** → `/reports` → 向上汇报 → 目标选 **L3**（方舟）或 **L2**（高原），标题前缀 `[E2E-RUP]` | [ ] |
| C2.2 | 逐级处理 | **L3** 待处理 → 转发/处理；必要时 **L2** 直至归档或退回 | [ ] |
| C2.3 | 向下传达 | **L2** → 向下传达 → 目标含 **L4**；L4 在待处理收到 | [ ] |
| C2.4 | 消息回跳 | 相关账号 `/messages` 回跳到 `/reports?...` 高亮正确 | [ ] |

### C3 异常记录

| # | 步骤 | 通过 |
|---|------|------|
| C3.1 | 若失败：Network 面板记录 HTTP 状态、`request_id`（JSON 体或响应头） | [ ] |

---

## D. 可选：知识库、AI、Push（optional-kb-ai-push）

| # | 步骤 | 通过 |
|---|------|------|
| D1 | **L0** 或 **L1**：`/knowledge-base` 发布/编辑一篇文档；**L4** 可见性与检索符合预期 | [ ] |
| D2 | 命令栏 `@系统` 或 `/`：有 `OPENAI_API_KEY` 时验证一次工具调用；无 key 时验证降级提示 | [ ] |
| D3 | `.env` 已配 `WEB_PUSH_*`：`/messages` 或设置完成订阅 → 重复 **C1.1** 指派 → 浏览器通知（`worker` 须运行） | [ ] |
| D4 | 未配 Web Push：跳过 D3，注明 N/A | [ ] |

---

## E. 总览与其它（与方案 §3.2、§3.1 对齐）

| # | 步骤 | 通过 |
|---|------|------|
| E1 | **L4** `/overview`：看板/公告/待办与本人相关；从消息「回到来源」带 query 进入任务区行为正常 | [ ] |
| E2 | **L0** `/people`：邀请新用户 → 无痕窗口打开 `.../login?invite=...` → 设密激活 → L0 确认账号状态 / 测撤销邀请（若界面提供） | [ ] |
| E3 | **L2/L3**：若有公告/看板发布权限，验证发布后 **L4** 在总览可见范围 | [ ] |

---

## F. 整体验收勾选（出口）

| 标准 | 通过 |
|------|------|
| 环境：`docker compose ps` 关键服务 healthy；8080 网关 `GET /api/v1/health` 为 200 | [ ] |
| 分层权限：L0/L1/L2/L3/L4 部门管理、人员、任务发布范围符合上表 | [ ] |
| 至少一条 **任务指派 → 执行/流转 → 消息回跳** 闭环 | [ ] |
| 至少一条 **向上汇报 → 多级处理**（含可选向下传达）闭环 | [ ] |
| 跨部门任务 **E2E-XDEPT**：非执行人部门视角隔离正确 | [ ] |

---

## G. 生产形态（可选）

改用 `docker-compose.prod.yml` + `.env.prod` 时，GUI 步骤与本清单相同；注意 `FRONTEND_APP_URL` 必须为真实公网或内网门户 URL（见 `backend/app/core/config.py` production 校验）。

---

## H. 自动化对照（非必选）

仓库 Playwright **live** 基线见 `frontend/playwright.live.config.ts` 与根 README；用于回归时可补充本清单未覆盖的脚本化路径，**不替代**分层权限的人工判断。
