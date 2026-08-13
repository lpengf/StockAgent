# 知衡 · 股票复盘 Agent

面向中国 A 股的收盘后研究 Agent。系统使用确定性代码完成数据质检、特征计算、股票筛选和硬风控，再由 5 个结构化角色完成市场解读、复核与报告生成。

> 本项目仅用于研究与决策支持，**不构成投资建议**，不执行自动交易。

## 架构

```
┌────────────┐    HTTP    ┌────────────────────────────────────┐
│  frontend  │ ────────▶  │  backend (FastAPI + Celery)         │
│  Next.js   │            │  ├─ domain/       确定性量化+风控    │
│  React 19  │            │  ├─ agents/       5 个角色           │
└────────────┘            │  ├─ application/  orchestrator      │
                          │  ├─ infrastructure/ DB + S3 + akshare│
                          │  ├─ api/          REST + Prometheus │
                          │  ├─ workers/      Celery tasks       │
                          │  └─ scheduler/    APScheduler        │
                          └────────────────────────────────────┘
                                    │              │           │
                                    ▼              ▼           ▼
                              PostgreSQL      MinIO / S3    Redis
```

关键性质：

- **确定性**：给定同一 `MarketInput`，pipeline 产出的候选、评分和报告完全一致，可回放。
- **风控发布门禁**：Risk Agent 的第一条结论如果不是 `无未处理硬否决`，Orchestrator 直接抛错，报告 Agent 不会执行。
- **不可变快照**：每次运行的原始输入、决策 JSON、Markdown 报告分别写入 S3；DB 只存元数据。
- **完全类型化**：Python `mypy strict` + Pydantic v2 + SQLAlchemy 2.x；前端 TypeScript 严格模式。

## 快速启动（Docker Compose）

```bash
make compose-up

# API:   http://localhost:8989/docs
# Web:   http://localhost:3000
# MinIO 控制台: http://localhost:9001 (minioadmin / minioadmin)
```

首次启动时 `migrator` 会跑 Alembic 迁移，`minio-init` 创建 `stock-agent-data` bucket，其它服务等它们完成后启动。

## 本地开发

```bash
# 后端
cd backend
uv venv && source .venv/bin/activate      # 或 python -m venv .venv
uv pip install -e '.[dev]'
stock-agent serve --reload                 # http://localhost:8989

# 前端（另开一个终端）
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8989 npm run dev
```

## 测试

```bash
make test              # 单元测试（快）
make test-integration  # 集成测试，需要 Postgres + MinIO
make lint typecheck    # ruff + mypy
```

CI（[.github/workflows/ci.yml](.github/workflows/ci.yml)）在 GitHub Actions 上执行同样的门禁。

## 文档

- [**docs/USAGE.md**](docs/USAGE.md) — 使用手册（API 参考、CLI、配置、故障排查）
- [**docs/DEVELOPMENT.md**](docs/DEVELOPMENT.md) — 开发指南（分层规则、加角色/规则/端点的清单）
- [**docs/TEST_REPORT.md**](docs/TEST_REPORT.md) — 最近一次测试执行结果
- [docs/stock-agent-design.md](docs/stock-agent-design.md) — 完整技术设计
- [docs/stock-agent-requirements.md](docs/stock-agent-requirements.md) — 需求文档

## 目录

```
backend/     Python 后端服务
frontend/    Next.js 前端
deploy/      docker-compose 与相关初始化脚本
docs/        需求、技术设计、使用与开发文档
```

## 接入真实行情

默认 `DATA_CONNECTOR=demo`，用内置固定数据。切换到 akshare：

```bash
export DATA_CONNECTOR=akshare
# 需要先在 stock_agent.infrastructure.data_connectors.factory 中传入 security_ids
```

生产环境请评估：合法授权的数据源、交易日历、akshare 的稳定性、Redis 层缓存、日线数据的时间点正确性。
