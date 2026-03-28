/**
 * MirrorQuant Tick 标准类型定义（TypeScript）
 * 用于前端和 API Gateway
 */

/** 订单簿档位 */
export interface OrderBookLevel {
  price: number;
  size: number;
}

/** 完整订单簿 */
export interface OrderBook {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
}

/** Polymarket 专用扩展字段 */
export interface PolymarketExtension {
  outcome?: "YES" | "NO";
  liquidity?: number;
  probability?: number;
  market_type?: "binary" | "categorical";
}

/** 资产类型 */
export type InstrumentType = "prediction" | "spot" | "future" | "option" | "swap";

/** 数据来源 */
export type DataSource = "polymarket" | "binance" | "trading212" | "tiger" | "okx" | "bybit";

/** 成交方向 */
export type TradeSide = "buy" | "sell";

/** MQ Tick 核心数据 */
export interface MQTickPayload {
  /** MQ 统一符号格式，如 POLY:TRUMP_WIN */
  symbol: string;
  
  /** 交易所原始市场 ID */
  market_id: string;
  
  /** 资产类型 */
  instrument_type: InstrumentType;
  
  /** 交易所名称 */
  exchange: string;
  
  // 最佳买卖价
  bid?: number;
  ask?: number;
  mid?: number;
  
  // 最佳买卖量
  bid_size?: number;
  ask_size?: number;
  
  // 最新成交
  last_price?: number;
  last_size?: number;
  last_side?: TradeSide;
  
  // 市场统计
  volume_24h?: number;
  open_interest?: number;
  
  // 完整订单簿（可选）
  orderbook?: OrderBook;
  
  // Polymarket 专用扩展
  polymarket?: PolymarketExtension;
}

/** MQ Tick 完整事件（顶层 Envelope） */
export interface MQTickEvent {
  /** 事件类型，固定为 "market_tick" */
  type: "market_tick";
  
  /** MQ 接收时间戳（毫秒） */
  ts_event: number;
  
  /** 交易所事件时间戳（毫秒） */
  ts_exchange: number;
  
  /** 数据来源 */
  source: DataSource;
  
  /** Tick 核心数据 */
  payload: MQTickPayload;
}

/** MQ Tick 示例 */
export const MQTickExample: MQTickEvent = {
  type: "market_tick",
  ts_event: 1710000000123,
  ts_exchange: 1710000000100,
  source: "polymarket",
  payload: {
    symbol: "POLY:TRUMP_WIN",
    market_id: "0xabc123",
    instrument_type: "prediction",
    exchange: "polymarket",
    bid: 0.62,
    ask: 0.63,
    mid: 0.625,
    bid_size: 1200,
    ask_size: 900,
    last_price: 0.63,
    last_size: 100,
    last_side: "buy",
    volume_24h: 120000,
    polymarket: {
      outcome: "YES",
      probability: 0.63,
      market_type: "binary"
    }
  }
};

/** NT Tick → MQ Tick 转换器 */
export class NTToMQTickConverter {
  /**
   * 将 Polymarket 市场数据转换为 MQ Tick
   */
  static convertPolymarketMarket(
    marketId: string,
    bid?: number,
    ask?: number,
    volume?: number,
    liquidity?: number
  ): MQTickEvent {
    const mid = bid && ask ? (bid + ask) / 2 : undefined;
    
    return {
      type: "market_tick",
      ts_event: Date.now(),
      ts_exchange: Date.now(),
      source: "polymarket",
      payload: {
        symbol: `POLY:${marketId}`,
        market_id: marketId,
        instrument_type: "prediction",
        exchange: "polymarket",
        bid,
        ask,
        mid,
        bid_size: 1000,
        ask_size: 1000,
        last_price: mid,
        volume_24h: volume,
        polymarket: {
          liquidity,
          probability: mid,
          market_type: "binary"
        }
      }
    };
  }
  
  /**
   * 验证 MQ Tick 格式
   */
  static validate(tick: unknown): tick is MQTickEvent {
    if (typeof tick !== "object" || tick === null) return false;
    
    const t = tick as any;
    
    return (
      t.type === "market_tick" &&
      typeof t.ts_event === "number" &&
      typeof t.ts_exchange === "number" &&
      typeof t.source === "string" &&
      typeof t.payload === "object" &&
      typeof t.payload.symbol === "string" &&
      typeof t.payload.market_id === "string" &&
      typeof t.payload.instrument_type === "string" &&
      typeof t.payload.exchange === "string"
    );
  }
}

/** WebSocket 消息类型（用于前端订阅） */
export interface MQWebSocketMessage {
  action: "subscribe" | "unsubscribe" | "tick";
  channel?: string;
  data?: MQTickEvent;
}

/** Redis Stream 键名生成器 */
export class MQStreamKeys {
  static marketTick(exchange: string, symbol: string): string {
    return `market.tick.${exchange}.${symbol}`;
  }
  
  static orderRequest(accountId: string): string {
    return `order.request.${accountId}`;
  }
  
  static orderEvent(accountId: string): string {
    return `order.event.${accountId}`;
  }
  
  static positionUpdate(accountId: string): string {
    return `position.update.${accountId}`;
  }
  
  static accountState(accountId: string): string {
    return `account.state.${accountId}`;
  }
  
  static llmWeight(strategyId: string): string {
    return `llm.weight.${strategyId}`;
  }
  
  /** 多租户版本（带用户前缀） */
  static userMarketTick(userId: string, exchange: string, symbol: string): string {
    return `user:${userId}:market.tick.${exchange}.${symbol}`;
  }
  
  static userOrderRequest(userId: string, accountId: string): string {
    return `user:${userId}:order.request.${accountId}`;
  }
  
  static userOrderEvent(userId: string, accountId: string): string {
    return `user:${userId}:order.event.${accountId}`;
  }
}
