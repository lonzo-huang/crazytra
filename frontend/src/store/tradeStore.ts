import { create } from 'zustand'

// ── Types ────────────────────────────────────────────────

export interface Tick {
  symbol:       string
  bid:          string
  ask:          string
  last:         string
  volume_24h:   string
  timestamp_ns: number
  latency_us:   number
}

export interface Signal {
  signal_id:   string
  strategy_id: string
  symbol:      string
  direction:   'long' | 'short' | 'exit' | 'hold'
  strength:    number
  confidence:  number
  reason:      string
  timestamp_ns: number
}

export interface OrderEvent {
  event_id:   string
  order_id:   string
  symbol:     string
  kind:       string
  filled_qty: string
  filled_px:  string
  fee:        string
  timestamp:  number
}

export interface RiskAlert {
  alert_id:  string
  kind:      string
  symbol:    string
  message:   string
  severity:  'warn' | 'critical'
  timestamp: number
}

export interface LLMWeight {
  symbol:      string
  llm_score:   number
  confidence:  number
  horizon:     string
  key_drivers: string[]
  model_used:  string
}

// ── Store ────────────────────────────────────────────────

interface TradeStore {
  // Connection
  wsStatus:  'connecting' | 'connected' | 'disconnected'

  // Market data
  ticks:     Record<string, Tick>
  tickHistory: Record<string, Tick[]>   // last 500 ticks per symbol

  // Strategy & orders
  signals:   Signal[]
  orders:    OrderEvent[]
  alerts:    RiskAlert[]
  weights:   Record<string, LLMWeight>

  // Actions
  setWsStatus: (s: TradeStore['wsStatus']) => void
  onTick:      (t: Tick) => void
  onSignal:    (s: Signal) => void
  onOrder:     (e: OrderEvent) => void
  onAlert:     (a: RiskAlert) => void
  onWeight:    (w: LLMWeight) => void
}

export const useTradeStore = create<TradeStore>((set) => ({
  wsStatus:    'disconnected',
  ticks:       {},
  tickHistory: {},
  signals:     [],
  orders:      [],
  alerts:      [],
  weights:     {},

  setWsStatus: (wsStatus) => set({ wsStatus }),

  onTick: (t) => set((s) => {
    const prev = s.tickHistory[t.symbol] ?? []
    const hist = [...prev, t].slice(-500)  // keep last 500
    return {
      ticks:       { ...s.ticks, [t.symbol]: t },
      tickHistory: { ...s.tickHistory, [t.symbol]: hist },
    }
  }),

  onSignal: (sig) => set((s) => ({
    signals: [sig, ...s.signals].slice(0, 200),
  })),

  onOrder: (e) => set((s) => ({
    orders: [e, ...s.orders].slice(0, 500),
  })),

  onAlert: (a) => set((s) => ({
    alerts: [a, ...s.alerts].slice(0, 100),
  })),

  onWeight: (w) => set((s) => ({
    weights: { ...s.weights, [w.symbol]: w },
  })),
}))

// ── WebSocket connection manager ─────────────────────────

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

export function connectWS(url: string = '/ws') {
  const store = useTradeStore.getState()
  store.setWsStatus('connecting')

  ws = new WebSocket(url)

  ws.onopen = () => {
    store.setWsStatus('connected')
    if (reconnectTimer) clearTimeout(reconnectTimer)
  }

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data) as Record<string, any>
      const topic = (msg._topic as string) ?? ''

      if (topic.startsWith('market.tick')) {
        store.onTick(msg as unknown as Tick)
      } else if (topic === 'strategy.signal') {
        store.onSignal(msg as unknown as Signal)
      } else if (topic === 'order.event') {
        store.onOrder(msg as unknown as OrderEvent)
      } else if (topic === 'risk.alert') {
        store.onAlert(msg as unknown as RiskAlert)
      } else if (topic === 'llm.weight') {
        store.onWeight(msg as unknown as LLMWeight)
      }
    } catch { /* ignore malformed */ }
  }

  ws.onclose = () => {
    store.setWsStatus('disconnected')
    reconnectTimer = setTimeout(() => connectWS(url), 3000)
  }

  ws.onerror = () => {
    ws?.close()
  }
}
