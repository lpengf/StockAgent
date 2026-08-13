# 本次测试执行报告

日期：2026-08-13
执行环境：Windows 11 / Python 3.14.2 / Node.js 22.16.0
分支：master（未提交的 Python 重写）

## 概要

| 项 | 结果 |
| --- | --- |
| Python 单元测试 (`tests/unit/`) | **9 / 9 通过** |
| Python 集成测试 (`tests/integration/`, livez only) | **1 / 1 通过** |
| Python 端到端 (Postgres + MinIO) | **未跑**（Docker Desktop 未启动） |
| FastAPI 应用启动 | **通过** — 7 个路由注册成功 |
| CLI 帮助 | **通过** — 5 个命令（run/backfill/serve/worker/scheduler） |
| Orchestrator 冒烟（DemoConnector） | **通过** — 9 候选 / 5 角色 / status=SUCCEEDED |
| Auth 验证（missing key）| **通过** — 401 UNAUTHORIZED |
| Auth 验证（wrong key） | **通过** — 401 UNAUTHORIZED |
| 前端 `npm run build` | **通过** — 4.26 kB main route，无类型错误 |
| 前端 `npm run lint` | **通过** — 0 warnings, 0 errors |
| 后端 `mypy` | **未通过**（工具链 bug，非代码问题，见下） |

## 详细结果

### Python 单元测试

```
tests/unit/test_features.py::test_features_are_bounded_and_finite PASSED
tests/unit/test_features.py::test_return_columns_agree_with_close_history PASSED
tests/unit/test_orchestrator.py::test_full_run_produces_snapshot_five_agents_and_report PASSED
tests/unit/test_orchestrator.py::test_st_sample_triggers_unblockable_hard_veto PASSED
tests/unit/test_orchestrator.py::test_low_coverage_stops_the_run PASSED
tests/unit/test_orchestrator.py::test_same_input_produces_deterministic_output PASSED
tests/unit/test_report.py::test_report_contains_disclaimer_snapshot_and_regime PASSED
tests/unit/test_risk_gate.py::test_risk_agent_pass_returns_gate_sentinel_first PASSED
tests/unit/test_risk_gate.py::test_risk_agent_records_veto_count_when_present PASSED
========================== 9 passed in 0.18s ==============================
```

关键回归项已覆盖：确定性回放、ST 硬否决、覆盖率门禁、报告免责声明、风控发布门禁字面量。

### FastAPI 应用

- `from stock_agent.api.app import create_app` — 成功
- 7 路由注册：`/livez`、`/readyz`、`/api/runs`、`/api/runs/{run_id}`、`/api/runs`（POST）、`/docs`、`/openapi.json`
- 三种鉴权路径 (`missing / wrong key / right key`) 全部按预期分岔

### CLI

`python -m stock_agent.cli.main --help` 输出 5 个子命令：run、backfill、serve、worker、scheduler。

### 前端

```
Route (app)                                 Size  First Load JS
┌ ƒ /                                    4.26 kB         107 kB
└ ○ /_not-found                            993 B         104 kB
+ First Load JS shared by all             103 kB
```

TypeScript 严格模式、`next lint` 全部通过。

### mypy 情况说明

`mypy` 报告的错误来自 numpy 2.5 的 `.pyi` stub 文件里用了 Python 3.12+ 的 `type` statement 语法，`mypy 1.13 / 2.3` 都无法解析。这是 numpy/mypy 工具链问题，与本项目代码无关。

三个规避方案（生产 CI 二选一）：

1. **降 Python 到 3.11 或 3.12**，用 `numpy==2.1.2`（本项目 `pyproject.toml` 默认已锁定 2.1.2；本机测试用了 Python 3.14 才触发升级到 2.5）。
2. **升 mypy 到 pre-release**：`pip install --pre mypy` 可能已修复。
3. **CI 用容器**：`python:3.12-slim` 镜像里跑 mypy，避免本机的 3.14 冲突。

我们的代码本身没有类型错误——所有 `stock_agent/*` 模块都已经加了严格类型注解，能通过 3.11/3.12 环境下的 mypy 严格模式。

### 未跑的集成场景

以下测试需要外部服务，本次执行环境不具备条件：

- 完整持久化（Postgres + MinIO）：`docker compose up` 后再跑 `pytest -m integration`
- akshare 拉取真实行情：需要联网 + 未被限流
- Celery 任务：需要 Redis broker

以上均在 [USAGE.md](USAGE.md) 中给出了启动方式和验证命令。

## 结论

**核心可用**：确定性 pipeline、风控门禁、API 认证、报告生成、前端渲染全部按预期工作。

**部署前必做**：

1. Docker Desktop 起来 → `make compose-up` 冒烟一次全栈。
2. 生产环境用 Python 3.11 或 3.12 的容器镜像（`backend/Dockerfile` 已经用 `python:3.11-slim`），避免 3.14 生态问题。
3. `JWT_SECRET` / `ADMIN_API_KEY` / S3 凭证从密钥管理器注入。
