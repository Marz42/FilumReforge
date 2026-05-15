# E2E GUI 验证：自动化运行说明（含报告目录约定）

当前环境若处于 **仅允许编辑 Markdown** 的限制下，无法在对话内直接生成 PNG 截图或执行 Playwright。请在本机 **Agent 模式** 或本地终端执行下列步骤，即可在仓库内生成 **`verification-runs/docker-gui-<时间戳>/`**（含 `screenshots/` 与 `report.md`）。

## 一键命令（在 `frontend` 目录）

需已安装依赖：`cd frontend && npm ci`（或 `npm install`），并已安装浏览器：`npx playwright install chromium`。

```bash
cd frontend
set GUI_BASE_URL=http://127.0.0.1:8080
set GUI_ADMIN_EMAIL=admin@example.com
set GUI_ADMIN_PASSWORD=FilumTest123!
set GUI_DEMO_PASSWORD=FilumTest123!
npx playwright test -c playwright.docker-gui.config.ts
```

> Linux/macOS 使用 `export GUI_BASE_URL=...` 代替 `set`。

## 需新增的文件（由 Agent 模式一次性写入仓库）

1. **`frontend/playwright.docker-gui.config.ts`**  
   - `use.baseURL` = `process.env.GUI_BASE_URL ?? 'http://127.0.0.1:8080'`  
   - **无** `webServer`（使用你已启动的 Docker Nginx）  
   - `testDir`: `./e2e/docker-gui-verification`  
   - 在配置加载时设置 `process.env.VERIFY_RUN_DIR` 指向 `verification-runs/docker-gui-<时间戳>`。

2. **`frontend/e2e/docker-gui-verification/docker-gui-verification.spec.ts`**  
   建议覆盖与 [infra/docker/E2E-GUI-VERIFICATION.md](../infra/docker/E2E-GUI-VERIFICATION.md) 对齐的**可自动化子集**：  
   - **A5**：`request.get(baseURL + '/api/v1/health')` 断言 200（经 Nginx 反代；`/healthz` 在 FastAPI 根路径，不经 `/api/` 反代）。  
   - **登录页**：全页截图 `01-login-page.png`。  
   - **L0**：`admin` 登录 → 总览截图 → 断言侧栏存在「部门管理」「人员管理」→ 打开 `/departments` 截图 → 退出。  
   - **L1**：`demo.hr@example.com` 登录 → 断言无「部门管理」→ 访问 `/departments` 应重定向到 `/overview`（与 [frontend/src/router/index.ts](../frontend/src/router/index.ts) `meta.roles` 一致）→ 截图 → 退出。  
   - **L4**：`demo.engineer.a@example.com` 登录 → 断言无「人员管理」「部门管理」→ 访问 `/people` 重定向 `/overview` → 截图 → 退出。  
   - **L3（任务中心预检）**：`demo.platform.lead@example.com` 打开 `/task-center`，`data-testid="task-center-view"` 截图（完整 C1 建任务仍建议手测）。  
   - **`test.afterAll`**：将上述每步 **PASS/FAIL/SKIP** 写入 `VERIFY_RUN_DIR/report.md`，并列出 `screenshots/*.png` 索引。

3. **`frontend/package.json` scripts（可选）**  
   `"test:e2e:docker-gui": "playwright test -c playwright.docker-gui.config.ts"`

## 报告模板（`report.md` 生成内容结构）

```markdown
# Docker Compose GUI 验证报告（自动化）
**对照清单**：infra/docker/E2E-GUI-VERIFICATION.md（自动化子集）
| 章节 | 步骤 ID | 结果 | 说明 |
## 截图索引
- ./screenshots/01-login-page.png
```

## 与完整 GUI 清单的关系

| 清单章节 | 自动化可覆盖 | 仍需人工 |
|----------|--------------|----------|
| A1–A4 | 否（Compose 状态） | 是 |
| A5 | 是 | |
| A6–A7 | 否 | seed / 管理员密码 |
| B | 侧栏与路由重定向可覆盖大部分 | 细粒度数据范围手测 |
| C/D/E | 部分导航截图 | 任务指派、汇报、消息回跳、Push、邀请 |

将本文件与 **`infra/docker/E2E-GUI-VERIFICATION.md`** 一并保留，便于 CI 或本地在 **Agent 模式** 下落地脚本与首次运行。
