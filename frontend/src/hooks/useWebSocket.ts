/**
 * useWebSocket Hook
 * 
 * 简化 WebSocket 订阅和数据接收的 React Hook。
 */

import { useEffect, useRef, useState } from 'react';
import { wsClient } from '../services/websocket';

interface UseWebSocketOptions<T> {
  channel: string | string[];
  onMessage?: (data: T) => void;
  enabled?: boolean;
}

interface UseWebSocketReturn<T> {
  data: T | null;
  isConnected: boolean;
  error: Error | null;
}

/**
 * 订阅 WebSocket channel 并接收数据
 */
export function useWebSocket<T = any>(
  options: UseWebSocketOptions<T>
): UseWebSocketReturn<T> {
  const { channel, onMessage, enabled = true } = options;
  
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(wsClient.isConnected);
  const [error, setError] = useState<Error | null>(null);
  
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    // 订阅 channel
    const channels = Array.isArray(channel) ? channel : [channel];
    wsClient.subscribe(channels);

    // 添加消息处理器
    const unsubscribers = channels.map(ch =>
      wsClient.on(ch, (receivedData: T) => {
        setData(receivedData);
        onMessageRef.current?.(receivedData);
      })
    );

    // 监听连接状态
    const checkConnection = setInterval(() => {
      setIsConnected(wsClient.isConnected);
    }, 1000);

    // 清理
    return () => {
      clearInterval(checkConnection);
      unsubscribers.forEach(unsub => unsub());
      wsClient.unsubscribe(channels);
    };
  }, [channel, enabled]);

  return { data, isConnected, error };
}

/**
 * 订阅市场 Tick 数据
 */
export function useMarketTick(symbol: string, exchange: string = 'binance') {
  const channel = `market.tick.${exchange}.${symbol.toLowerCase().replace('-', '')}`;
  
  return useWebSocket<{
    symbol: string;
    exchange: string;
    timestamp_ns: number;
    bid: string;
    ask: string;
    last: string;
    latency_us: number;
  }>({ channel });
}

/**
 * 订阅订单事件
 */
export function useOrderEvents() {
  return useWebSocket<{
    order_id: string;
    status: string;
    symbol: string;
    side: string;
    quantity: string;
    price: string;
    timestamp_ns: number;
  }>({ channel: 'order.event' });
}

/**
 * 订阅持仓更新
 */
export function usePositionUpdates() {
  return useWebSocket<{
    symbol: string;
    side: string;
    quantity: string;
    entry_price: string;
    current_price: string;
    pnl: string;
    timestamp_ns: number;
  }>({ channel: 'position.update' });
}

/**
 * 订阅账户状态
 */
export function useAccountState() {
  return useWebSocket<{
    balance: string;
    equity: string;
    margin_used: string;
    margin_available: string;
    timestamp_ns: number;
  }>({ channel: 'account.state' });
}

/**
 * 订阅风控告警
 */
export function useRiskAlerts() {
  return useWebSocket<{
    level: 'info' | 'warning' | 'error' | 'critical';
    message: string;
    details: Record<string, any>;
    timestamp_ns: number;
  }>({ channel: 'risk.alert' });
}

/**
 * 订阅多个 symbol 的 tick 数据
 */
export function useMultipleMarketTicks(
  symbols: string[],
  exchange: string = 'binance'
) {
  const channels = symbols.map(
    symbol => `market.tick.${exchange}.${symbol.toLowerCase().replace('-', '')}`
  );
  
  const [ticksMap, setTicksMap] = useState<Map<string, any>>(new Map());

  useEffect(() => {
    wsClient.subscribe(channels);

    const unsubscribers = channels.map((ch, index) =>
      wsClient.on(ch, (data: any) => {
        setTicksMap(prev => {
          const next = new Map(prev);
          next.set(symbols[index], data);
          return next;
        });
      })
    );

    return () => {
      unsubscribers.forEach(unsub => unsub());
      wsClient.unsubscribe(channels);
    };
  }, [symbols.join(','), exchange]);

  return ticksMap;
}
