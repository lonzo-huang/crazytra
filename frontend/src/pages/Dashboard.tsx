import { useTradeStore } from '../store/tradeStore'
import { TickerCard } from '../components/TickerCard'
import { PriceChart } from '../components/PriceChart'
import { OrderBook } from '../components/OrderBook'
import { useMarketTick } from '../hooks/useWebSocket'
import { useMemo } from 'react'

function SignalRow({ sig }: { sig: ReturnType<typeof useTradeStore>['signals'][0] }) {
  const dirColor = sig.direction === 'long'  ? 'text-green-400'
                 : sig.direction === 'short' ? 'text-red-400'
                 : sig.direction === 'exit'  ? 'text-yellow-400'
                 : 'text-gray-400'
  const ts = new Date(sig.timestamp_ns / 1_000_000).toLocaleTimeString()
  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-800 text-sm">
      <span className="text-gray-500 text-xs w-20 shrink-0">{ts}</span>
      <span className="text-gray-300 w-24 shrink-0">{sig.symbol}</span>
      <span className={`${dirColor} w-12 shrink-0 font-medium uppercase text-xs`}>
        {sig.direction}
      </span>
      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
        <div className="bg-indigo-500 h-1.5 rounded-full"
             style={{ width: `${sig.strength * 100}%` }} />
      </div>
      <span className="text-gray-400 text-xs w-10 text-right">
        {(sig.strength * 100).toFixed(0)}%
      </span>
      <span className="text-gray-500 text-xs hidden md:block truncate max-w-xs">
        {sig.strategy_id}
      </span>
    </div>
  )
}

export default function Dashboard() {
  const signals = useTradeStore(s => s.signals)
  const ticks = useTradeStore(s => s.ticks)
  const tickHistory = useTradeStore(s => s.tickHistory)
  
  // 动态获取所有有数据的市场
  const availableSymbols = useMemo(() => {
    return Object.keys(ticks).sort()
  }, [ticks])
  
  // 如果没有数据，显示默认市场
  const SYMBOLS = availableSymbols.length > 0 
    ? availableSymbols 
    : ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'MATIC-USDT']

  // 准备图表数据
  const chartData = useMemo(() => {
    const history = tickHistory['BTC-USDT'] || []
    return history.slice(-100).map(tick => ({
      time: Math.floor(tick.timestamp_ns / 1_000_000_000) as any,
      open: parseFloat(tick.last),
      high: parseFloat(tick.last) * 1.001,
      low: parseFloat(tick.last) * 0.999,
      close: parseFloat(tick.last),
    }))
  }, [tickHistory])

  // 准备订单簿数据
  const orderBookData = useMemo(() => {
    const tick = ticks['BTC-USDT']
    if (!tick) return { bids: [], asks: [] }
    
    const midPrice = (parseFloat(tick.bid) + parseFloat(tick.ask)) / 2
    const bids = Array.from({ length: 15 }, (_, i) => ({
      price: (midPrice - i * 0.5).toFixed(2),
      size: (Math.random() * 2).toFixed(4),
    }))
    const asks = Array.from({ length: 15 }, (_, i) => ({
      price: (midPrice + i * 0.5).toFixed(2),
      size: (Math.random() * 2).toFixed(4),
    }))
    
    return { bids, asks }
  }, [ticks])

  return (
    <div className="space-y-6">
      {/* Ticker cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {SYMBOLS.map(symbol => {
          const tick = ticks[symbol]
          const history = tickHistory[symbol] || []
          const priceHistory = history.slice(-60).map(t => ({
            time: t.timestamp_ns,
            price: (parseFloat(t.bid) + parseFloat(t.ask)) / 2,
          }))
          
          return tick ? (
            <TickerCard
              key={symbol}
              symbol={symbol}
              bid={tick.bid}
              ask={tick.ask}
              last={tick.last}
              latency_us={tick.latency_us}
              history={priceHistory}
            />
          ) : (
            <div key={symbol} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-xs text-gray-400 font-medium tracking-wider mb-2">{symbol}</div>
              <div className="text-gray-500 text-sm">等待数据...</div>
            </div>
          )
        })}
      </div>

      {/* 主图表和订单簿 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* K线图 */}
        <div className="lg:col-span-2">
          <PriceChart symbol="BTC-USDT" data={chartData} height={400} />
        </div>
        
        {/* 订单簿 */}
        <div>
          <OrderBook 
            symbol="BTC-USDT" 
            bids={orderBookData.bids}
            asks={orderBookData.asks}
          />
        </div>
      </div>

      {/* Signal feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">实时信号</h2>
        {signals.length === 0 ? (
          <p className="text-gray-500 text-sm">等待信号...</p>
        ) : (
          <div className="max-h-80 overflow-y-auto">
            {signals.slice(0, 50).map(sig => (
              <SignalRow key={sig.signal_id} sig={sig} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
