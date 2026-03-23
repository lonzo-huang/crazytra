/**
 * WebSocket 客户端
 * 
 * 连接到后端 WebSocket 服务器，订阅实时数据流。
 */

type MessageHandler = (data: any) => void;

interface WebSocketMessage {
  type: string;
  channel?: string;
  data?: any;
  channels?: string[];
  ts?: number;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectInterval: number = 5000;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private subscriptions: Set<string> = new Set();
  private isConnecting: boolean = false;
  private isManualClose: boolean = false;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * 连接到 WebSocket 服务器
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        reject(new Error('Already connecting'));
        return;
      }

      this.isConnecting = true;
      this.isManualClose = false;

      console.log('[WebSocket] Connecting to', this.url);

      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected');
        this.isConnecting = false;

        // 重新订阅之前的 channels
        if (this.subscriptions.size > 0) {
          this.subscribe(Array.from(this.subscriptions));
        }

        resolve();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        this.isConnecting = false;
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        this.isConnecting = false;
        this.ws = null;

        // 自动重连（除非是手动关闭）
        if (!this.isManualClose) {
          this.scheduleReconnect();
        }
      };
    });
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.isManualClose = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    console.log('[WebSocket] Manually disconnected');
  }

  /**
   * 订阅 channels
   */
  subscribe(channels: string | string[]): void {
    const channelArray = Array.isArray(channels) ? channels : [channels];

    // 记录订阅
    channelArray.forEach(ch => this.subscriptions.add(ch));

    // 发送订阅消息
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        type: 'subscribe',
        channels: channelArray,
      });

      console.log('[WebSocket] Subscribed to', channelArray);
    }
  }

  /**
   * 取消订阅
   */
  unsubscribe(channels: string | string[]): void {
    const channelArray = Array.isArray(channels) ? channels : [channels];

    // 移除订阅记录
    channelArray.forEach(ch => this.subscriptions.delete(ch));

    // 发送取消订阅消息
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        type: 'unsubscribe',
        channels: channelArray,
      });

      console.log('[WebSocket] Unsubscribed from', channelArray);
    }
  }

  /**
   * 添加消息处理器
   */
  on(channel: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set());
    }

    this.handlers.get(channel)!.add(handler);

    // 返回取消订阅函数
    return () => {
      this.off(channel, handler);
    };
  }

  /**
   * 移除消息处理器
   */
  off(channel: string, handler: MessageHandler): void {
    const handlers = this.handlers.get(channel);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.handlers.delete(channel);
      }
    }
  }

  /**
   * 发送消息
   */
  private send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] Cannot send, not connected');
    }
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: string): void {
    try {
      const message: WebSocketMessage = JSON.parse(data);

      switch (message.type) {
        case 'data':
          this.handleDataMessage(message);
          break;

        case 'subscribed':
          console.log('[WebSocket] Subscription confirmed:', message.channels);
          break;

        case 'unsubscribed':
          console.log('[WebSocket] Unsubscription confirmed:', message.channels);
          break;

        case 'pong':
          // Pong 响应，用于心跳检测
          break;

        default:
          console.warn('[WebSocket] Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  /**
   * 处理数据消息
   */
  private handleDataMessage(message: WebSocketMessage): void {
    if (!message.channel || !message.data) {
      return;
    }

    // 调用所有匹配的处理器
    this.handlers.forEach((handlers, pattern) => {
      if (this.matchChannel(pattern, message.channel!)) {
        handlers.forEach(handler => {
          try {
            handler(message.data);
          } catch (error) {
            console.error('[WebSocket] Handler error:', error);
          }
        });
      }
    });
  }

  /**
   * 匹配 channel 模式
   */
  private matchChannel(pattern: string, channel: string): boolean {
    // 精确匹配
    if (pattern === channel) {
      return true;
    }

    // 通配符匹配
    if (pattern.includes('*')) {
      const regex = new RegExp(
        '^' + pattern.replace(/\*/g, '.*') + '$'
      );
      return regex.test(channel);
    }

    return false;
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    console.log(`[WebSocket] Reconnecting in ${this.reconnectInterval}ms...`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect().catch(error => {
        console.error('[WebSocket] Reconnect failed:', error);
      });
    }, this.reconnectInterval);
  }

  /**
   * 发送 ping
   */
  ping(): void {
    this.send({ type: 'ping' });
  }

  /**
   * 获取连接状态
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// 创建全局 WebSocket 实例
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';
export const wsClient = new WebSocketClient(WS_URL);

// 自动连接
wsClient.connect().catch(error => {
  console.error('[WebSocket] Initial connection failed:', error);
});

// 定期发送 ping
setInterval(() => {
  if (wsClient.isConnected) {
    wsClient.ping();
  }
}, 30000);
