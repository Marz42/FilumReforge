---
description: "Use when editing Docker Compose, Dockerfiles, Nginx configs, release checks, startup scripts, environment templates, or production deployment documentation for backend, frontend, worker, and infra."
name: "Filum Deployment"
applyTo:
  - "infra/**/*.yml"
  - "infra/**/*.yaml"
  - "infra/**/*.conf"
  - "backend/Dockerfile*"
  - "frontend/Dockerfile*"
  - "backend/scripts/*.sh"
  - "scripts/check-release.sh"
---

# Filum Deployment

- 先区分开发与生产路径：开发 / 集成联调用 [infra/docker/docker-compose.yml](../../infra/docker/docker-compose.yml)，生产 Compose 用 [infra/docker/docker-compose.prod.yml](../../infra/docker/docker-compose.prod.yml)，主机部署参考 [memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md](../../memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md)。
- 生产后端必须走 `start-prod.sh` 或等价的无 `--reload` 启动方式；不要把 `start-dev.sh`、Vite dev server 或 bind mount 方案当生产默认。
- 生产工件已经存在：`backend/Dockerfile.prod`、`frontend/Dockerfile.prod`、`infra/nginx/nginx.prod.conf`、`infra/nginx/nginx.compose.prod.conf`、`scripts/check-release.sh`；如果 README 仍否认这些工件，按文档漂移处理。
- `backend` 与 `worker` 必须共享同一份环境变量与同一个 `STORAGE_BASE_PATH`；涉及 Web Push 时，`WEB_PUSH_PUBLIC_KEY`、`WEB_PUSH_PRIVATE_KEY`、`WEB_PUSH_SUBJECT` 要同时提供给 backend 与 worker。
- Windows 下改动 shell 脚本必须保持 LF；仓库通过 `.gitattributes` 约束了 `*.sh text eol=lf`，不要引入 `CRLF`。
- 发布前验证优先执行 `bash scripts/check-release.sh`；如果目标环境只有 runtime 依赖，`pytest` 缺失应被视为 warning 或 skip，而不是默认发布阻塞。
- Compose、Nginx 和部署文档的细节优先链接 [infra/docker/README.md](../../infra/docker/README.md) 与 [memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md](../../memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md)，不要在 instruction 里复制整段操作手册。