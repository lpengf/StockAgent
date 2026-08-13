# Chat 运行看板实现文档

## 1. 实现范围

当前 Chat 运行看板是一个单页交互原型，实现以下能力：

- Chat 总数与状态统计；
- 四列 Kanban 状态展示；
- 文本搜索和 Agent 筛选；
- HTML5 拖拽修改状态；
- Chat 详情抽屉；
- 进度、标签和异常提示；
- 桌面端与移动端响应式布局；
- Sites 私有站点构建和发布。

当前版本未实现持久化、真实数据同步、身份验证和后端状态更新。

## 2. 技术栈

| 领域 | 选型 |
| --- | --- |
| UI | React 19、TypeScript、Next App Router 兼容组件 |
| 构建 | vinext、Vite、Cloudflare Worker 兼容输出 |
| 样式 | 全局 CSS、Tailwind CSS 导入 |
| 状态管理 | React `useState` 和 `useMemo` |
| 拖拽 | 浏览器原生 HTML5 Drag and Drop API |
| 部署 | OpenAI Sites |

运行时要求为 Node.js 22.13 或更高版本。

## 3. 核心文件

Chat Kanban 发布版本的核心文件如下：

```text
app/page.tsx              页面组件、演示数据和全部交互逻辑
app/globals.css           页面布局、卡片、抽屉和响应式样式
app/layout.tsx            中文页面语言和站点元数据
.openai/hosting.json      Sites 项目标识与资源声明
package.json              开发、构建和测试脚本
```

注意：仓库可能同时进行 StockAgent 主应用开发。本文描述的是已发布的 Chat Kanban 版本；集成时建议将看板拆分为独立路由和组件，避免与主首页互相覆盖。

## 4. 数据模型

### 4.1 状态类型

```ts
type Status = "queued" | "running" | "attention" | "done";
```

状态与界面文案的映射：

| 数据值 | 界面文案 |
| --- | --- |
| `queued` | 待处理 |
| `running` | 进行中 |
| `attention` | 需关注 |
| `done` | 已完成 |

### 4.2 Chat 类型

```ts
type Chat = {
  id: string;
  title: string;
  summary: string;
  status: Status;
  agent: string;
  model: string;
  updatedAt: string;
  duration: string;
  progress?: number;
  tags: string[];
  warning?: string;
};
```

字段说明：

- `id`：稳定且唯一的 Chat 标识。
- `status`：决定卡片所在列。
- `progress`：可选，取值建议为 `0` 至 `100`。
- `warning`：可选；存在时使用异常卡片样式。
- `updatedAt`、`duration`：当前原型为展示字符串；生产实现建议改为机器可计算的时间戳和毫秒数。

## 5. 前端状态与派生数据

页面维护以下本地状态：

```ts
const [chats, setChats] = useState(initialChats);
const [query, setQuery] = useState("");
const [agent, setAgent] = useState("全部 Agent");
const [selected, setSelected] = useState<Chat | null>(null);
const [dragging, setDragging] = useState<string | null>(null);
```

派生数据通过 `useMemo` 计算：

- Agent 下拉选项从 Chat 数据去重生成；
- 可见 Chat 同时应用文本搜索和 Agent 筛选；
- 每列数量从当前 Chat 状态实时统计。

这套实现适合中小规模原型。Chat 数量达到数千条时，应增加服务端分页、虚拟列表或按状态分段加载。

## 6. 关键交互实现

### 6.1 搜索和筛选

搜索将 `title`、`summary` 和 `id` 拼接后转为小写进行包含匹配。Agent 筛选使用精确匹配，两个条件以逻辑与组合。

### 6.2 拖拽修改状态

卡片通过 `draggable` 开启原生拖拽：

1. `onDragStart` 记录当前 Chat ID；
2. 状态列通过 `onDragOver` 允许放置；
3. `onDrop` 调用 `moveChat`；
4. `moveChat` 使用不可变更新方式修改目标 Chat 的 `status`；
5. React 重新计算状态列和顶部统计。

当前拖动属于乐观的本地更新，没有失败回滚。接入 API 后应在请求失败时恢复原状态并显示通知。

### 6.3 详情抽屉

点击或按 `Enter` 时，将卡片对象写入 `selected`。当 `selected` 非空时渲染全屏遮罩和右侧抽屉。点击遮罩或关闭按钮将其置为 `null`。

建议后续增加：

- `Escape` 关闭；
- 打开后的焦点捕获；
- 关闭后焦点回到原卡片；
- `aria-modal` 和对话框语义。

## 7. 样式设计

样式集中在 `app/globals.css`，主要设计规则包括：

- 深色固定侧边栏和浅色工作区；
- 白色统计卡片和灰色 Kanban 列；
- 蓝、橙、绿分别表示运行、异常和完成；
- 状态卡片采用轻边框、圆角和悬停阴影；
- `1100px` 以下使用固定宽度横向滚动列；
- `760px` 以下折叠导航并调整指标布局。

当前没有使用图片或外部图标库，界面主要依赖文字、符号、颜色和 CSS 形状。

## 8. 本地开发与验证

安装依赖：

```bash
npm install
```

启动开发环境：

```bash
npm run dev
```

生成部署构建：

```bash
npm run build
```

提交前至少验证：

- 页面可以正常构建；
- 四种状态均能正确显示；
- 搜索和 Agent 筛选可组合使用；
- 卡片可拖动到其他列；
- 顶部数量随状态变化更新；
- 详情抽屉可打开和关闭；
- 窄屏下看板可以横向滚动。

## 9. 建议的真实 Chat API

### 9.1 查询接口

建议提供：

```http
GET /api/chats?status=running&agent_id=market-agent&query=复盘&cursor=...
```

响应示例：

```json
{
  "items": [
    {
      "id": "CH-1042",
      "title": "今日 A 股收盘复盘",
      "summary": "汇总指数、市场宽度与主线行业",
      "status": "running",
      "agent": { "id": "market-agent", "name": "市场分析 Agent" },
      "model": "gpt-5.4",
      "progress": 68,
      "started_at": "2026-08-11T16:32:00+08:00",
      "updated_at": "2026-08-11T16:40:24+08:00",
      "warning": null,
      "tags": ["每日任务", "A股"],
      "version": 7
    }
  ],
  "next_cursor": null,
  "summary": {
    "total": 8,
    "queued": 1,
    "running": 2,
    "attention": 2,
    "done": 3
  }
}
```

### 9.2 状态更新接口

```http
PATCH /api/chats/{chat_id}
Content-Type: application/json

{
  "status": "attention",
  "version": 7
}
```

建议使用版本号或 ETag 实现乐观并发控制，避免覆盖 Agent 刚刚写入的新状态。

### 9.3 实时同步

生产环境建议选择以下方式之一：

- Server-Sent Events：适合服务器单向推送状态和进度；
- WebSocket：适合需要双向实时控制的场景；
- 短轮询：实现简单，可作为 MVP 方案。

建议事件类型至少包含：

- `chat.created`；
- `chat.status_changed`；
- `chat.progress_updated`；
- `chat.warning_raised`；
- `chat.completed`。

## 10. 持久化与审计

生产实现建议记录：

- Chat 当前状态和状态版本；
- 每次状态变化的前值、后值和发生时间；
- 变更来源：Agent、调度器或人工操作；
- 人工拖动时的操作者和原因；
- Agent、模型、Prompt 和数据快照版本；
- 异常、重试次数和最终处理结果。

对已完成状态的人工回退或对异常状态的强制关闭，应要求填写原因并生成审计日志。

## 11. 安全与权限

建议至少定义以下权限：

| 角色 | 权限 |
| --- | --- |
| 只读观察者 | 查看统计、卡片和详情 |
| 运营人员 | 修改非终态任务状态、处理告警 |
| 管理员 | 重试、终止、回退和配置 Agent |

后端必须再次校验权限，不能仅依赖前端隐藏按钮。Chat 摘要、日志和错误信息应脱敏，避免泄露 API 密钥、账户凭据和完整用户持仓。

## 12. 推荐拆分方案

接入主应用时建议调整为：

```text
app/chats/page.tsx                 Chat 看板路由
components/chat-board/Board.tsx   看板容器
components/chat-board/Column.tsx  状态列
components/chat-board/Card.tsx    Chat 卡片
components/chat-board/Drawer.tsx  详情抽屉
lib/chats/api.ts                   API 客户端
lib/chats/types.ts                 类型和状态映射
```

这样可以让页面布局、业务模型和数据访问相互独立，便于测试和替换数据源。

## 13. 后续实施顺序

1. 将看板迁移到独立 `/chats` 路由。
2. 把演示数据和类型从页面组件中拆出。
3. 接入只读 `GET /api/chats`。
4. 增加加载、空数据、错误和断线状态。
5. 接入实时状态更新。
6. 实现带回滚的拖拽状态更新。
7. 增加登录、角色权限和操作审计。
8. 补充组件测试、API 合约测试和端到端测试。

