# WebSocket 实时数据连接

本文档介绍如何在前端使用 WebSocket 订阅实时数据。

## 架构

```
Redis Streams
    ↓ 订阅
API Gateway (Go)
    ↓ WebSocket
Frontend (React)
    ↓ React Hooks
UI Components
```

## 快速开始

### 1. 基础使用

```typescript
import { useMarketTick } from '@/hooks/useWebSocket';

function PriceDisplay() {
  const { data, isConnected } = useMarketTick('BTC-USDT');

  if (!isConnected) {
    return <div>连接中...</div>;
  }

  if (!data) {
    return <div>等待数据...</div>;
  }

  return (
    <div>
      <p>买价: {data.bid}</p>
      <p>卖价: {data.ask}</p>
      <p>最新价: {data.last}</p>
    </div>
  );
}
```

### 2. 订阅多个市场

```typescript
import { useMultipleMarketTicks } from '@/hooks/useWebSocket';

function MultiMarketView() {
  const symbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT'];
  const ticksMap = useMultipleMarketTicks(symbols);

  return (
    <div>
      {symbols.map(symbol => {
        const tick = ticksMap.get(symbol);
        return (
          <div key={symbol}>
            <h3>{symbol}</h3>
            <p>价格: {tick?.last || '-'}</p>
          </div>
        );
      })}
    </div>
  );
}
```

### 3. 订阅订单事件

```typescript
import { useOrderEvents } from '@/hooks/useWebSocket';

function OrderList() {
  const { data: orderEvent } = useOrderEvents();

  useEffect(() => {
    if (orderEvent) {
      console.log('订单更新:', orderEvent);
      // 更新订单列表
    }
  }, [orderEvent]);

  return <div>订单列表...</div>;
}
```

## 可用的 Hooks

### useMarketTick

订阅单个市场的 tick 数据。

```typescript
const { data, isConnected, error } = useMarketTick(
  'BTC-USDT',  // symbol
  'binance'    // exchange (可选)
);

// data 结构
interface MarketTick {
  symbol: string;
  exchange: string;
  timestamp_ns: number;
  bid: string;        // Decimal 字符串
  ask: string;
  last: string;
  latency_us: number;
}
```

### useOrderEvents

订阅订单事件。

```typescript
const { data } = useOrderEvents();

// data 结构
interface OrderEvent {
  order_id: string;
  status: 'submitted' | 'accepted' | 'filled' | 'rejected' | 'cancelled';
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: string;
  price: string;
  timestamp_ns: number;
}
```

### usePositionUpdates

订阅持仓更新。

```typescript
const { data } = usePositionUpdates();

// data 结构
interface PositionUpdate {
  symbol: string;
  side: 'LONG' | 'SHORT';
  quantity: string;
  entry_price: string;
  current_price: string;
  pnl: string;
  timestamp_ns: number;
}
```

### useAccountState

订阅账户状态。

```typescript
const { data } = useAccountState();

// data 结构
interface AccountState {
  balance: string;
  equity: string;
  margin_used: string;
  margin_available: string;
  timestamp_ns: number;
}
```

### useRiskAlerts

订阅风控告警。

```typescript
const { data } = useRiskAlerts();

// data 结构
interface RiskAlert {
  level: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  details: Record<string, any>;
  timestamp_ns: number;
}
```

## 底层 API

### WebSocketClient

如果需要更底层的控制，可以直接使用 `WebSocketClient`。

```typescript
import { wsClient } from '@/services/websocket';

// 连接
await wsClient.connect();

// 订阅
wsClient.subscribe('market.tick.binance.btcusdt');

// 添加处理器
const unsubscribe = wsClient.on('market.tick.*', (data) => {
  console.log('收到数据:', data);
});

// 取消订阅
unsubscribe();

// 断开连接
wsClient.disconnect();
```

## Channel 命名规范

### 市场数据

```
market.tick.{exchange}.{symbol}
```

示例：
- `market.tick.binance.btcusdt`
- `market.tick.polymarket.will-btc-hit-100k`

### 订单和持仓

```
order.event          # 订单事件
position.update      # 持仓更新
account.state        # 账户状态
```

### 风控和告警

```
risk.alert           # 风控告警
```

## 通配符订阅

支持使用 `*` 通配符：

```typescript
// 订阅所有 Binance 市场
wsClient.subscribe('market.tick.binance.*');

// 订阅所有市场
wsClient.subscribe('market.tick.*');
```

## 消息格式

### 客户端 → 服务器

#### 订阅

```json
{
  "type": "subscribe",
  "channels": ["market.tick.binance.btcusdt"]
}
```

#### 取消订阅

```json
{
  "type": "unsubscribe",
  "channels": ["market.tick.binance.btcusdt"]
}
```

#### Ping

```json
{
  "type": "ping"
}
```

### 服务器 → 客户端

#### 数据消息

```json
{
  "type": "data",
  "channel": "market.tick.binance.btcusdt",
  "data": {
    "symbol": "BTC-USDT",
    "bid": "67840.50",
    "ask": "67841.20",
    "last": "67840.80"
  },
  "ts": 1704067200000000000
}
```

#### 订阅确认

```json
{
  "type": "subscribed",
  "channels": ["market.tick.binance.btcusdt"]
}
```

#### Pong

```json
{
  "type": "pong",
  "ts": 1704067200000000000
}
```

## 连接管理

### 自动重连

WebSocket 客户端会自动重连：

- 连接断开后 5 秒自动重连
- 重连时自动恢复之前的订阅
- 支持手动断开（不会自动重连）

```typescript
// 手动断开（不会自动重连）
wsClient.disconnect();

// 手动连接
await wsClient.connect();
```

### 心跳检测

客户端每 30 秒发送一次 ping，服务器会响应 pong。

## 性能优化

### 批量消息

服务器会批量发送消息，减少网络开销：

```typescript
// 客户端自动处理批量消息
wsClient.on('market.tick.*', (data) => {
  // 每条消息都会调用此处理器
});
```

### 消息缓冲

客户端有 256 条消息的发送缓冲区，防止消息丢失。

## 错误处理

### 连接错误

```typescript
wsClient.connect()
  .then(() => console.log('已连接'))
  .catch(error => console.error('连接失败:', error));
```

### 消息处理错误

```typescript
wsClient.on('market.tick.*', (data) => {
  try {
    // 处理数据
  } catch (error) {
    console.error('处理错误:', error);
  }
});
```

## 调试

### 启用日志

WebSocket 客户端会自动输出日志到控制台：

```
[WebSocket] Connecting to ws://localhost:8080/ws
[WebSocket] Connected
[WebSocket] Subscribed to ["market.tick.binance.btcusdt"]
[WebSocket] Subscription confirmed: ["market.tick.binance.btcusdt"]
```

### 检查连接状态

```typescript
console.log('是否连接:', wsClient.isConnected);
```

## 示例：实时价格图表

```typescript
import { useMarketTick } from '@/hooks/useWebSocket';
import { useState, useEffect } from 'react';

function PriceChart({ symbol }: { symbol: string }) {
  const { data } = useMarketTick(symbol);
  const [prices, setPrices] = useState<number[]>([]);

  useEffect(() => {
    if (data?.last) {
      setPrices(prev => [...prev.slice(-99), parseFloat(data.last)]);
    }
  }, [data]);

  return (
    <div>
      <h2>{symbol} 价格走势</h2>
      {/* 使用 lightweight-charts 或其他图表库 */}
      <LineChart data={prices} />
    </div>
  );
}
```

## 示例：订单通知

```typescript
import { useOrderEvents } from '@/hooks/useWebSocket';
import { useEffect } from 'react';
import { toast } from 'react-hot-toast';

function OrderNotifications() {
  const { data: orderEvent } = useOrderEvents();

  useEffect(() => {
    if (!orderEvent) return;

    switch (orderEvent.status) {
      case 'filled':
        toast.success(`订单已成交: ${orderEvent.symbol}`);
        break;
      case 'rejected':
        toast.error(`订单被拒绝: ${orderEvent.symbol}`);
        break;
    }
  }, [orderEvent]);

  return null;
}
```

## 环境变量

```bash
# .env
VITE_WS_URL=ws://localhost:8080/ws
```

## 故障排查

### 问题：无法连接

**检查**：
1. WebSocket 服务器是否运行
2. URL 是否正确
3. 防火墙设置

### 问题：频繁断连

**检查**：
1. 网络稳定性
2. 服务器负载
3. 心跳超时设置

### 问题：收不到数据

**检查**：
1. 是否正确订阅了 channel
2. Redis 是否有数据
3. Channel 名称是否正确

## 参考资料

- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [React Hooks](https://react.dev/reference/react)
- [Gorilla WebSocket](https://github.com/gorilla/websocket)
