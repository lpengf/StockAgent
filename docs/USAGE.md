# 使用文档

面向使用者、运维和二次开发者的一站式手册。系统由 [`backend/`](../backend/) (Python) 和 [`frontend/`](../frontend/) (Next.js) 两部分组成；下文所有命令假设从仓库根目录执行。

---

## 目录

1. [快速上手（Docker Compose）](#1-快速上手docker-compose)
2. [本地开发环境](#2-本地开发环境)
3. [核心概念](#3-核心概念)
4. [CLI 使用](#4-cli-使用)
5. [REST API 参考](#5-rest-api-参考)
6. [数据源与连接器](#6-数据源与连接器)
7. [调度与任务](#7-调度与任务)
8. [配置项与环境变量](#8-配置项与环境变量)
9. [数据存储](#9-数据存储)
10. [观测与告警](#10-观测与告警)
11. [测试与质量门禁](#11-测试与质量门禁)
12. [部署](#12-部署)
13. [故障排查](#13-故障排查)

---

## 1. 快速上手（Docker Compose）

前提：本机已安装 Docker Desktop（Docker Engine ≥ 24），已启动。

```bash
make compose-up
```

首次启动会依次拉起以下容器：

| 服务 | 端口 | 用途 |
| --- | --- | --- |
| `postgres` | 5432 | 元数据 |
| `redis` | 6379 | Celery broker + 缓存 |
| `minio` | 9000（S3）/ 9001（控制台） | 对象存储 |
| `minio-init` | – | 一次性创建 `stock-agent-data` bucket 后退出 |
| `migrator` | – | 一次性执行 `alembic upgrade head` 后退出 |
| `api` | 8989 | FastAPI |
| `worker` | – | Celery worker |
| `scheduler` | – | APScheduler 触发器 |
| `web` | 3000 | Next.js 前端 |

启动完成后打开：

- **前端**：http://localhost:3000
- **API 文档**：http://localhost:8989/docs
- **MinIO 控制台**：http://localhost:9001（用户名 `minioadmin` / 密码 `minioadmin`）

停止并清空数据：`make compose-down`。

**第一次触发复盘**：前端页面顶部输入 `ADMIN_API_KEY`（默认为 `.env.example` 中的 `dev-admin-key`），点击 "运行收盘复盘"，等待约 2 秒即可看到候选池、五角色决策与数据快照。

---

## 2. 本地开发环境

不用 Docker 时，仅测试**后端确定性核心**只需 Python：

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -e '.[dev]'
```

启动 API（不含持久化，仅供开发）：

```bash
stock-agent serve --reload
```

前端：

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8989 npm run dev
```

如果需要真正落盘、跑 Celery、跑调度器，最简单的方法仍是 `make compose-up`。

### 已验证的运行环境

- Python **3.11 / 3.12 / 3.13 / 3.14**（3.14 会自动装匹配版本的 numpy）
- Node.js **22.13+**（前端）
- PostgreSQL **16**、MinIO **latest**、Redis **7**（通过 docker-compose）

---

## 3. 核心概念

### 3.1 五阶段流水线（Orchestrator）

一次 "复盘运行"（`StockAgentRun`）严格按顺序执行 5 步，任何一步失败都会中断：

```
1. validate_input        数据质量门禁（覆盖率、OHLC 合法性、代码不重复）
2. compute_features      12+ 只证券的量价、流动性、基本面特征
3. build_market_review   分类市场状态：TREND_UP / RANGE / RISK_OFF
4. select_candidates     规则化打分 + 行业分散 + 硬风控过滤
5. run_agents ×5         协调 / 市场 / 量化 / 风控 / 报告
```

风控 Agent 是**发布门禁**：如果它的第一条结论不是 `"无未处理硬否决"`，`RiskGateError` 被抛出，报告 Agent 不会执行，运行以失败落盘。

### 3.2 确定性契约

给定同一 `MarketInput + id_suffix`，pipeline 产生的候选、评分、报告完全一致。**不要在 `domain/` 或 `agents/` 里引入 `datetime.now()` / `random`**。这是回放测试和审计的基础。

### 3.3 不可变快照

每次运行写入 3 个 S3 对象 + 若干 Postgres 行：

- `raw/market=CN_A/trade_date=YYYY-MM-DD/snapshot_id=.../snapshot.json` — 原始输入
- `decision/trade_date=YYYY-MM-DD/run_id=.../run.json` — 完整决策链
- `report/trade_date=YYYY-MM-DD/run_id=.../report.md` — Markdown 报告

对象先写入 S3，DB 事务后提交。崩溃时最多泄漏一个 S3 对象（可 GC），不会出现 "DB 有引用但对象不存在"。

---

## 4. CLI 使用

CLI 入口：`stock-agent`（`pip install -e .` 后可直接调用；容器内也已安装）。

```bash
stock-agent --help
```

### 4.1 同步跑一次复盘

```bash
stock-agent run                           # 用配置的 DATA_CONNECTOR，交易日 = 今天
stock-agent run --trade-date 2026-08-11   # 指定交易日
stock-agent run --suffix backfill-2026-08-11   # 指定幂等键（重跑会覆盖）
```

输出 `run_id` 到 stdout。

### 4.2 按区间回填

```bash
stock-agent backfill 2026-07-01 2026-07-31
```

顺序跑（避免 akshare 限流）。跳过失败日期继续跑，可通过 `stock_agent` logger 观察。

生产环境请改用 Celery `run_daily_screening.delay(...)` + Celery beat。

### 4.3 启动 API/Worker/Scheduler

```bash
stock-agent serve             # 开发用 uvicorn；生产请直接跑 uvicorn/gunicorn
stock-agent worker            # celery -A stock_agent.workers.celery_app worker
stock-agent scheduler         # APScheduler 触发器
```

---

## 5. REST API 参考

Base URL：`http://localhost:8989`。所有路径前缀 `/api` 除健康检查外。OpenAPI 文档：`GET /docs`。

### 5.1 认证

两种方式，二选一：

- `X-Admin-Key: <key>` — 服务间调用 / 调度器 / CLI，值来自 `ADMIN_API_KEY` 环境变量。
- `Authorization: Bearer <jwt>` — 用户端；`role=admin` 的 JWT 才能触发 POST 类操作。

只读接口（`GET /api/runs`、`GET /api/runs/{id}`）任一凭证均可。

### 5.2 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/livez` | 无 | 存活探针 |
| `GET` | `/readyz` | 无 | 就绪探针（探测 DB + S3） |
| `GET` | `/metrics` | 无 | Prometheus 指标 |
| `GET` | `/api/runs` | 只读 | 最近 30 次运行摘要 |
| `GET` | `/api/runs/{run_id}` | 只读 | 单次运行完整详情（含候选、Agent 结论、Markdown 报告） |
| `POST` | `/api/runs` | admin | 触发一次复盘并同步落盘 |

### 5.3 触发一次复盘

```bash
curl -X POST http://localhost:8989/api/runs \
  -H "X-Admin-Key: dev-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"connector": "demo"}'
```

响应：

```json
{
  "run_id": "run-20260811-a1b2c3d4",
  "snapshot_id": "snapshot-20260811-a1b2c3d4",
  "report_id": "report-20260811-a1b2c3d4",
  "trade_date": "2026-08-11",
  "as_of_time": "2026-08-11T08:30:00+00:00",
  "status": "SUCCEEDED",
  "strategy_version": "mvp-1.0.0",
  "candidates": 9,
  "rejected": 3
}
```

请求体字段（全部可选）：

- `trade_date`（`YYYY-MM-DD`）：留空则用今天。
- `connector`（`demo` / `akshare`）：覆盖 `DATA_CONNECTOR`。
- `id_suffix`：幂等键。同一个 `id_suffix` 二次调用会覆盖上次的 `run_id`。

### 5.4 查看报告

```bash
# 列表
curl -s -H "X-Admin-Key: dev-admin-key" http://localhost:8989/api/runs | jq '.items[0]'

# 详情
curl -s -H "X-Admin-Key: dev-admin-key" \
  http://localhost:8989/api/runs/run-20260811-a1b2c3d4 | jq '.report.markdown' -r
```

### 5.5 错误协议

所有失败响应统一形状：

```json
{
  "error": {
    "code": "DATA_QUALITY_ERROR",
    "message": "核心行情覆盖率 82.5% 低于 95.0% 门槛",
    "details": { "coverage": 82.5, "threshold": 95.0 }
  }
}
```

稳定的 `code` 值：

| Code | HTTP | 场景 |
| --- | --- | --- |
| `UNAUTHORIZED` | 401 | 缺少或无效凭证 |
| `FORBIDDEN` | 403 | 有凭证但权限不足（例：非 admin 调 POST） |
| `NOT_FOUND` | 404 | 运行不存在 |
| `VALIDATION_ERROR` | 422 | 请求体不合法 |
| `DATA_QUALITY_ERROR` | 422 | 数据覆盖率不达标 |
| `CONFLICT` | 409 | 幂等冲突 |
| `RISK_GATE_FAILED` | 409 | 硬风控发布门禁失败 |
| `RATE_LIMITED` | 429 | 触发限流（默认 120/min/IP） |
| `EXTERNAL_SERVICE_ERROR` | 503 | akshare / MinIO 等外部服务失败 |
| `INTERNAL_ERROR` | 500 | 未捕获异常 |

每个响应都会带回 `X-Request-Id` 头，日志里可以定位到具体请求。

---

## 6. 数据源与连接器

### 6.1 内置连接器

- **`demo`**（默认）— [`infrastructure/data_connectors/demo.py`](../backend/src/stock_agent/infrastructure/data_connectors/demo.py)。12 只固定证券、22 个交易日的合成数据。用于测试、回放和演示。
- **`akshare`** — [`infrastructure/data_connectors/akshare_connector.py`](../backend/src/stock_agent/infrastructure/data_connectors/akshare_connector.py)。免费的 A 股行情，内置 token bucket 限流 + 重试。

切换方式（`.env`）：

```
DATA_CONNECTOR=akshare
AKSHARE_RATE_LIMIT_PER_MINUTE=30
```

### 6.2 接入自建数据源

实现 `DataConnector` Protocol（[`data_connectors/base.py`](../backend/src/stock_agent/infrastructure/data_connectors/base.py)）即可：

```python
class MyConnector:
    source_id = "my-source"

    def fetch(self, request: FetchRequest) -> MarketInput:
        # 返回一个符合 domain.types.MarketInput 的对象即可，不依赖任何具体框架
        ...
```

然后在 [`data_connectors/factory.py`](../backend/src/stock_agent/infrastructure/data_connectors/factory.py) 里加分支。

### 6.3 数据契约

`MarketInput` 至少包含：

- 每只证券 `SecuritySeries`：证券代码（`XSHG.600000` 形式）、名称、行业、上市天数、`is_st`、`is_suspended`、`≥ 20` 个日线 `DailyBar`、ROE、营收增长、负债率。
- 顶层：`market="CN_A"`、`trade_date`、`as_of_time`。

覆盖率 < 95%（可通过 `COVERAGE_HARD_THRESHOLD` 调整）直接拒绝。

---

## 7. 调度与任务

### 7.1 定时任务

`scheduler` 服务默认按 `SCHEDULER_RUN_CRON`（缺省 `0 16 * * 1-5`，中国时区 16:00 每周一到五）触发一次 `run_daily_screening` Celery 任务。

修改时区：`SCHEDULER_TIMEZONE=Asia/Shanghai`（默认）。

### 7.2 Celery 队列

三条队列，同一个 worker 可全部消费：

- `agent`：Agent 编排（当前是唯一活跃队列）
- `data`：数据接入（预留给未来的独立采集 worker）
- `report`：报告发布（预留给未来的独立 worker）

### 7.3 手动触发

```bash
# 通过 Python
python -c "from stock_agent.workers.tasks import run_daily_screening; \
  print(run_daily_screening.delay('2026-08-11').id)"
```

任务失败会自动指数退避重试 3 次；仍失败则记录到 Celery 结果后端。

---

## 8. 配置项与环境变量

完整清单见 [`backend/.env.example`](../backend/.env.example) 和 [`backend/src/stock_agent/config.py`](../backend/src/stock_agent/config.py)。核心几项：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ENV` | `local` | `local` / `dev` / `staging` / `prod` |
| `LOG_JSON` | `true` | 生产建议 `true`；本地 `false` 更好读 |
| `DATABASE_URL` | `postgresql+psycopg://stock:stock@localhost:5432/stock_agent` | |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | 生产改为 AWS S3 或空 |
| `S3_BUCKET` | `stock-agent-data` | |
| `DATA_CONNECTOR` | `demo` | `demo` 或 `akshare` |
| `COVERAGE_HARD_THRESHOLD` | `95.0` | 数据覆盖率下限 |
| `MAX_FOCUS_CANDIDATES` | `5` | 重点观察数量 |
| `MAX_TOTAL_CANDIDATES` | `10` | 总候选数量 |
| `MAX_PER_INDUSTRY` | `2` | 同行业最大候选 |
| `JWT_SECRET` | `change-me-in-prod` | **生产必须改** |
| `ADMIN_API_KEY` | `dev-admin-key` | **生产必须改** |
| `RATE_LIMIT_PER_MINUTE` | `120` | 每 IP 每分钟 |
| `SCHEDULER_RUN_CRON` | `0 16 * * 1-5` | |
| `PROMETHEUS_ENABLED` | `true` | |

**不要**把 `JWT_SECRET` / `ADMIN_API_KEY` / `S3_SECRET_ACCESS_KEY` 提交到仓库。生产用 secrets manager 注入。

---

## 9. 数据存储

### 9.1 表清单（Postgres）

- `data_snapshots` — 每次运行的原始输入元数据（对象键 + 校验和 + 记录数）
- `screening_runs` — 运行主表（状态、市场状态、市场综述、数据质量、被拒数）
- `agent_runs` — 每次运行 × 每个角色一行
- `candidates` — 候选池明细
- `reports` — Markdown 报告
- `audit_logs` — 操作审计

Score / confidence 按 basis-point 整数存储（`score * 100`，`confidence * 10_000`），避免浮点误差。

### 9.2 迁移

Alembic 是**唯一**的 DDL 源。改 schema 后：

```bash
cd backend
alembic revision --autogenerate -m "add xxx"
alembic upgrade head
```

回滚：`alembic downgrade -1`。

**注意**：修改 schema 需同时更新 3 处：
1. [`infrastructure/db/models.py`](../backend/src/stock_agent/infrastructure/db/models.py) 的 ORM 模型
2. [`alembic/versions/`](../backend/alembic/versions/) 新增迁移
3. [`infrastructure/storage/run_repository.py`](../backend/src/stock_agent/infrastructure/storage/run_repository.py) 的写入语句 + [`api/schemas.py`](../backend/src/stock_agent/api/schemas.py) 的响应字段

### 9.3 对象存储 layout

```
s3://stock-agent-data/
  raw/market=CN_A/trade_date=2026-08-11/snapshot_id=...json
  decision/trade_date=2026-08-11/run_id=.../run.json
  report/trade_date=2026-08-11/run_id=.../report.md
```

路径不作为业务主键，仅用作分区。

---

## 10. 观测与告警

### 10.1 结构化日志

所有服务输出 `stdout` 的 JSON，字段：

```json
{"event": "run.persisted", "run_id": "...", "candidates": 9,
 "request_id": "abc123", "actor": "admin",
 "level": "info", "timestamp": "2026-08-11T08:30:15.412Z"}
```

生产环境挂 vector / fluentd / Loki 采集即可。

### 10.2 Prometheus 指标

`GET /metrics` 暴露：

| 指标 | 类型 | Labels |
| --- | --- | --- |
| `stock_agent_runs_started_total` | Counter | `connector` |
| `stock_agent_runs_succeeded_total` | Counter | `connector`, `status` |
| `stock_agent_runs_failed_total` | Counter | `connector`, `error_code` |
| `stock_agent_run_duration_seconds` | Histogram | `connector` |

建议告警规则：

- 24h 内没有 `runs_succeeded_total` 增长 → 调度失效
- `runs_failed_total{error_code="RISK_GATE_FAILED"}` 突增 → 数据源或规则出问题
- P95 `run_duration_seconds` > 30 秒 → 性能退化

### 10.3 OpenTelemetry

可选。设置 `OTEL_EXPORTER_ENDPOINT` 打开导出（预留）。

---

## 11. 测试与质量门禁

### 11.1 命令

```bash
make test               # 单元测试（快，无外部依赖）
make test-integration   # 全部测试（含 API 存活）
make lint               # ruff
make typecheck          # mypy 严格模式
```

### 11.2 已通过的用例

10 个测试，覆盖：

| 测试文件 | 主张 |
| --- | --- |
| [`test_orchestrator.py`](../backend/tests/unit/test_orchestrator.py) | 完整运行产出快照 + 5 角色 + 报告；ST 硬否决；覆盖率不足中断；相同输入决定性一致 |
| [`test_features.py`](../backend/tests/unit/test_features.py) | 特征值在 [0, 100]；return 与 close 历史一致 |
| [`test_risk_gate.py`](../backend/tests/unit/test_risk_gate.py) | 通过时首个结论 = `无未处理硬否决`；硬否决存在时门禁失败 |
| [`test_report.py`](../backend/tests/unit/test_report.py) | 报告含免责声明、快照 ID、策略版本 |
| [`test_api_smoke.py`](../backend/tests/integration/test_api_smoke.py) | `/livez` 返回 200 |

### 11.3 添加测试

新加的所有确定性逻辑测试放 `tests/unit/`；任何依赖 Postgres / MinIO / Redis 的测试用 `@pytest.mark.integration` 标记。CI 会分开跑。

---

## 12. 部署

### 12.1 容器镜像

`backend/Dockerfile` 是多阶段构建，非 root 用户，`tini` 作 PID 1，内置 `/livez` healthcheck。

```bash
make docker-build                           # 构建 stock-agent-backend:local
docker tag stock-agent-backend:local ghcr.io/your-org/stock-agent:v1.0.0
docker push ghcr.io/your-org/stock-agent:v1.0.0
```

### 12.2 Kubernetes（示意）

`deploy/` 目录只放了 docker-compose；K8s 部署时需要：

- 4 个 Deployment：`api`、`worker`、`scheduler`、`web`
- 1 个 Job：Alembic migrator（前置 hook）
- StatefulSet + PVC：Postgres（或用 RDS）
- 一份 Secret：`JWT_SECRET`、`ADMIN_API_KEY`、S3 凭证
- ConfigMap：其它环境变量
- HPA：`api` 按 CPU + QPS；`worker` 按 Redis 队列长度

### 12.3 上线检查清单

- [ ] `JWT_SECRET` 已改为随机 32 字节
- [ ] `ADMIN_API_KEY` 已从密钥管理系统注入
- [ ] `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` 使用 IAM Role / Workload Identity
- [ ] `DATABASE_URL` 指向托管 PostgreSQL
- [ ] `CORS_ALLOW_ORIGINS` 只含你的前端域名
- [ ] `ENV=prod`，`LOG_JSON=true`
- [ ] `PROMETHEUS_ENABLED=true`，抓取端已经配置
- [ ] 数据库备份策略已启用
- [ ] S3 bucket 已启用 versioning + 生命周期规则
- [ ] Sentry / OTEL Collector 已接入
- [ ] 限流阈值符合业务预期

---

## 13. 故障排查

### 13.1 一次运行失败了怎么定位

1. 拿到 `run_id` 或 `X-Request-Id`。
2. 日志系统中过滤 `run_id=xxx` 或 `request_id=xxx`，找到 `orchestrator.start` → `orchestrator.done` 之间的事件链。
3. Postgres 里 `SELECT * FROM audit_logs WHERE entity_id='<run_id>'`。
4. `GET /api/runs/<run_id>` 查看 `agent_runs` 的 `status` 字段，最先转 `FAILED` 的就是元凶。

### 13.2 常见问题

**Q: `curl POST /api/runs` 返回 401**
A: 忘了带 `X-Admin-Key` 头，或者环境变量 `ADMIN_API_KEY` 与头值不匹配。

**Q: `RISK_GATE_FAILED`，但候选看起来没问题**
A: `risk_officer` 的第一条 conclusion 必须等于 `无未处理硬否决`。如果代码或数据有变更导致别的字符串排在第一，orchestrator 就会拒绝发布。见 [`agents/roles.py`](../backend/src/stock_agent/agents/roles.py) 的 `RISK_GATE_PASS_SENTINEL`。

**Q: 前端 "分析中…" 一直转**
A: 打开浏览器 DevTools 看 Network。常见原因：
- 后端没跑起来（`docker compose logs api`）
- `Admin Key` 空或错
- CORS 被拦截 — 检查 `CORS_ALLOW_ORIGINS` 是否包含前端域名

**Q: akshare 返回 `EXTERNAL_SERVICE_ERROR`**
A: akshare 上游偶发抖动。系统已经内置指数退避 + 3 次重试；再失败的话检查：
- 网络能否访问 `https://push2.eastmoney.com` 等域名
- `AKSHARE_RATE_LIMIT_PER_MINUTE` 是否设置过高
- 换 `DATA_CONNECTOR=demo` 确认非行情源问题

**Q: docker compose up 时 `migrator` 报 `relation already exists`**
A: 之前跑过旧版本，schema 不一致。`make compose-down` 会清 volume，重新起就好。

**Q: 日志里看到 `object_store.put_failed`**
A: MinIO 未启动或凭证不对。生产环境检查 IAM 权限：需要 `s3:PutObject`、`s3:GetObject`、`s3:HeadBucket`。

### 13.3 报告问题

请附上：

- `X-Request-Id`（响应头）
- 运行 ID（如有）
- 结构化日志的相关片段（脱敏后）
- `GET /readyz` 的完整响应
- `stock_agent` 版本（`pip show stock-agent`）
