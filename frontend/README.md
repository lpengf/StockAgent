# Stock Agent — 前端

Next.js App Router 单页面复盘看板，所有数据来自 [`../backend`](../backend) 提供的 Python API。

## 本地开发

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8989 npm run dev
```

前端跑在 http://localhost:3000。浏览器请求 `/api/backend/…` 会被 Next.js 重写到 `http://localhost:8989/api/…`。

## 环境变量

| 变量 | 作用 |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | 客户端跳板的 URL，一般是后端的公网地址 |
| `API_BASE_URL` | 服务端组件调用后端时使用的绝对地址（docker/K8s 内部服务名） |

## 完整栈

`docker compose up -d --build` （在 [`../deploy`](../deploy) 目录）会把 Postgres/MinIO/Redis/API/Worker/Scheduler/Web 一次拉起。

## 目录

```text
app/           Next.js App Router
lib/api/       API 类型与 fetch 封装
public/        静态资源
```
