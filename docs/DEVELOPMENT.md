# 开发指南

面向二次开发者。用户使用请看 [USAGE.md](USAGE.md)。

## 目录结构

```
backend/
├── src/stock_agent/
│   ├── domain/            纯领域层（IO-free），numpy + pydantic
│   ├── agents/            五角色实现
│   ├── application/       用例编排 orchestrator + 报告渲染
│   ├── infrastructure/    IO 边界：DB、S3、行情连接器、LLM 网关
│   ├── api/               FastAPI 路由 + 认证 + 中间件
│   ├── workers/           Celery
│   ├── scheduler/         APScheduler
│   ├── cli/               Typer CLI
│   ├── config.py          pydantic-settings
│   ├── logging.py         structlog 配置
│   └── errors.py          领域错误
├── tests/{unit,integration}/
├── alembic/               DB 迁移
└── pyproject.toml

frontend/
├── app/                   Next.js App Router
├── lib/api/               类型化 fetch 客户端
└── package.json
```

## 分层规则

**Domain** 不允许 import：`sqlalchemy`、`boto3`、`fastapi`、`celery`、`akshare`、`stock_agent.infrastructure.*`、`stock_agent.api.*`。

**Application** 可以 import Domain + Infrastructure 的 **接口**（Protocol），不 import 具体实现类。

**Infrastructure** 可以 import 任何东西，但它是唯一有 IO 权限的层。

**API / CLI / Workers** 只做 "接线"：读配置、注入依赖、调 orchestrator、序列化响应。

违反分层规则的 PR 会在 code review 阶段被拒。

## 加一个新角色（例：Fundamental Agent）

1. `domain/types.py`：把新的 `role_id` 字面量加入 `AgentRoleId` Literal。
2. `agents/roles.py`：新增 `run_fundamental_agent(...)`，返回 `AgentResult`。
3. `application/orchestrator.py`：在 `agents = [...]` 列表里加进去。**必须在 `run_risk_agent` 之前**，否则风控看不到它的输出。
4. `tests/unit/test_orchestrator.py`：把断言 `len(run.agents) == 5` 改成 6，或者更好——改成 `len(run.agents) == len(EXPECTED_AGENTS)` 并把常量提到 orchestrator。
5. 前端 `lib/api/types.ts` 的 `AgentResult` 已经通用，无需改。
6. 如果需要 LLM，通过 `infrastructure/llm/gateway.py` 里的 `LLMGateway` Protocol 注入，别在 agent 里直接调外部 API。

## 加一个新硬风控规则

1. `domain/risk.py::evaluate_risk` — 追加一个 `RiskDecision`，`rule_id` 用 `RISK-<类别>-XXX` 命名。
2. 只在 `severity="HARD_VETO"` 的规则失败时才影响候选池；`"WARNING"` 只在报告里体现。
3. 加一个单元测试：构造一个会触发新规则的 `SecuritySeries`，断言它不会出现在 `run.candidates` 中。

## 加一个新数据源

见 [USAGE.md §6.2](USAGE.md#62-接入自建数据源)。核心是实现 `DataConnector` Protocol，然后在 factory 里加分支。

## 加一个新 API 端点

1. 在 `api/routes/` 里新增文件（或复用现有的 `runs.py`）。
2. 用 `Depends(require_actor)` 或 `Depends(require_admin)` 声明鉴权要求。
3. 请求/响应模型放 `api/schemas.py`（继承 `ApiModel`，即 Pydantic + 允许别名）。
4. 在 `api/app.py::create_app()` 里 `app.include_router(...)`。
5. 加一个 `@pytest.mark.integration` 的测试，用 `TestClient` 打真实链路。

## 数据库 schema 变更清单

见 [USAGE.md §9.2](USAGE.md#92-迁移)。三处必须同步。

## 前端联调

前端调用统一走 `lib/api/client.ts`。类型定义在 `lib/api/types.ts` — 和 `stock_agent.api.schemas` 保持一一对应。

如果后端加了新字段：

1. 更新 `api/schemas.py` 的 Pydantic 响应模型。
2. 更新 `lib/api/types.ts` 的对应类型。
3. 如果要展示，改 `app/dashboard.tsx`。

CI 会跑 `npm run build`，TS 类型不对齐会 fail。

## 本地跑单个测试

```bash
cd backend
pytest tests/unit/test_orchestrator.py -v -k "deterministic"
pytest tests/unit/test_orchestrator.py::test_st_sample_triggers_unblockable_hard_veto
```

## Debug 提示

- **日志太多**：`LOG_LEVEL=WARNING` 或 `LOG_JSON=false` 让日志变可读。
- **想在 REPL 里跑 orchestrator**：
  ```python
  from stock_agent.infrastructure.data_connectors.demo import DemoConnector
  from stock_agent.infrastructure.data_connectors.base import FetchRequest
  from stock_agent.application.orchestrator import run_stock_agent
  from datetime import date

  mi = DemoConnector().fetch(FetchRequest(trade_date=date(2026, 8, 11)))
  run = run_stock_agent(mi, "repl")
  print(run.report_markdown)
  ```
- **想看 SQL**：`sqlalchemy` 的 `echo=True` 可以在 `db/session.py` 里临时打开，别提交。

## 发布流程

1. 更新 `pyproject.toml` 和 `src/stock_agent/__init__.py` 的版本号。
2. `make lint typecheck test` 全绿。
3. Tag：`git tag v1.0.1 && git push --tags`。
4. GitHub Actions 会跑 CI；通过后手动 build & push 镜像。
5. K8s deployment 换镜像 tag（或用 argocd auto-sync）。
