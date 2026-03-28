# MirrorQuant 前端

基于 React + TypeScript + Vite 的实时交易界面。

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **TailwindCSS** - 样式框架
- **Lightweight Charts** - TradingView 官方图表库（40KB）
- **Zustand** - 状态管理
- **React Router** - 路由管理

## 功能特性

### 📊 实时数据

- **WebSocket 连接**：订阅 Redis Streams 实时数据
- **自动重连**：网络断开自动恢复
- **低延迟**：显示微秒级延迟

### 📈 专业图表

使用 **Lightweight Charts**（TradingView 官方开源）：

- **K 线图**：实时价格走势
- **深度图**：订单簿可视化
- **迷你图**：Ticker 卡片中的价格趋势
- **响应式**：自适应屏幕大小

### 🎯 交易功能

- **实时价格**：买卖价、最新价
- **订单簿**：深度显示
- **信号监控**：策略信号实时推送
- **订单管理**：订单状态跟踪
- **持仓展示**：实时 PnL

### 🤖 LLM 洞察

- **情感分析**：新闻情感评分
- **权重可视化**：LLM 权重趋势
- **关键驱动**：影响因素展示

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量

```bash
# 创建 .env 文件
cp .env.example .env
```

编辑 `.env`：

```bash
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080/ws
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 4. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录。

## 项目结构

```
frontend/
├── src/
│   ├── components/          # UI 组件
│   │   ├── PriceChart.tsx   # K线图、深度图
│   │   ├── TickerCard.tsx   # 价格卡片
│   │   └── OrderBook.tsx    # 订单簿
│   ├── hooks/               # React Hooks
│   │   └── useWebSocket.ts  # WebSocket Hook
│   ├── pages/               # 页面组件
│   │   ├── Dashboard.tsx    # 仪表盘
│   │   ├── Orders.tsx       # 订单页面
│   │   ├── Strategies.tsx   # 策略页面
│   │   ├── LLMInsights.tsx  # LLM 洞察
│   │   └── Alerts.tsx       # 告警页面
│   ├── services/            # 服务
│   │   └── websocket.ts     # WebSocket 客户端
│   ├── store/               # 状态管理
│   │   └── tradeStore.ts    # 交易状态
│   ├── App.tsx              # 主应用
│   └── main.tsx             # 入口文件
├── docs/                    # 文档
│   └── WEBSOCKET.md         # WebSocket 使用指南
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 组件使用

### PriceChart - K 线图

```tsx
import { PriceChart } from '@/components/PriceChart';

function TradingView() {
  const data = [
    { time: 1704067200, open: 67800, high: 67900, low: 67700, close: 67850 },
    // ...
  ];

  return <PriceChart symbol="BTC-USDT" data={data} height={400} />;
}
```

### TickerCard - 价格卡片

```tsx
import { TickerCard } from '@/components/TickerCard';

function Dashboard() {
  return (
    <TickerCard
      symbol="BTC-USDT"
      bid="67840.50"
      ask="67841.20"
      last="67840.80"
      latency_us={50}
      history={priceHistory}
    />
  );
}
```

### OrderBook - 订单簿

```tsx
import { OrderBook } from '@/components/OrderBook';

function Trading() {
  const bids = [
    { price: "67840.50", size: "0.5" },
    { price: "67840.00", size: "1.2" },
  ];

  const asks = [
    { price: "67841.20", size: "0.8" },
    { price: "67841.50", size: "1.5" },
  ];

  return <OrderBook symbol="BTC-USDT" bids={bids} asks={asks} />;
}
```

## WebSocket 使用

### 订阅市场数据

```tsx
import { useMarketTick } from '@/hooks/useWebSocket';

function PriceDisplay() {
  const { data, isConnected } = useMarketTick('BTC-USDT');

  if (!isConnected) return <div>连接中...</div>;
  if (!data) return <div>等待数据...</div>;

  return (
    <div>
      <p>买价: {data.bid}</p>
      <p>卖价: {data.ask}</p>
      <p>最新: {data.last}</p>
    </div>
  );
}
```

### 订阅订单事件

```tsx
import { useOrderEvents } from '@/hooks/useWebSocket';

function OrderMonitor() {
  const { data: orderEvent } = useOrderEvents();

  useEffect(() => {
    if (orderEvent) {
      console.log('订单更新:', orderEvent);
      toast.success(`订单 ${orderEvent.status}`);
    }
  }, [orderEvent]);

  return null;
}
```

## 状态管理

使用 Zustand 管理全局状态：

```tsx
import { useTradeStore } from '@/store/tradeStore';

function Component() {
  // 读取状态
  const ticks = useTradeStore(state => state.ticks);
  const signals = useTradeStore(state => state.signals);

  // 更新状态
  const addTick = useTradeStore(state => state.addTick);
  const addSignal = useTradeStore(state => state.addSignal);

  return <div>...</div>;
}
```

## 样式定制

使用 TailwindCSS 工具类：

```tsx
// 深色主题
<div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
  <h3 className="text-gray-300">标题</h3>
  <p className="text-gray-500">内容</p>
</div>

// 价格颜色
<span className="text-green-400">上涨</span>
<span className="text-red-400">下跌</span>
```

## 性能优化

### 1. 图表优化

- 使用 Lightweight Charts（仅 40KB）
- 自动响应式调整
- 硬件加速渲染

### 2. WebSocket 优化

- 批量消息处理
- 自动重连机制
- 消息缓冲

### 3. 状态优化

- Zustand 选择器避免不必要的重渲染
- React.memo 缓存组件
- useMemo/useCallback 优化计算

## Docker 部署

### 开发环境

```bash
docker-compose up frontend
```

### 生产环境

```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 故障排查

### 问题：WebSocket 连接失败

**检查**：
1. API 网关是否运行
2. WebSocket URL 是否正确
3. 浏览器控制台错误

### 问题：图表不显示

**检查**：
1. 数据格式是否正确
2. 容器尺寸是否有效
3. 浏览器控制台错误

### 问题：样式不生效

**检查**：
1. TailwindCSS 是否正确配置
2. 运行 `npm run dev` 重新编译
3. 清除浏览器缓存

## 开发指南

### 添加新页面

1. 在 `src/pages/` 创建组件
2. 在 `App.tsx` 添加路由
3. 在导航栏添加链接

### 添加新组件

1. 在 `src/components/` 创建组件
2. 使用 TypeScript 定义 Props
3. 使用 TailwindCSS 样式

### 添加新 Hook

1. 在 `src/hooks/` 创建 Hook
2. 使用 TypeScript 定义类型
3. 导出供组件使用

## 参考资料

- [React 文档](https://react.dev/)
- [Vite 文档](https://vitejs.dev/)
- [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [TailwindCSS](https://tailwindcss.com/)
- [Zustand](https://github.com/pmndrs/zustand)
