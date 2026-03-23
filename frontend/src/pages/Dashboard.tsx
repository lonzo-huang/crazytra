import { useTradeStore } from '../store/tradeStore'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts'

function TickerCard({ symbol }: { symbol: string }) {
  const tick    = useTradeStore(s => s.ticks[symbol])
  const history = useTradeStore(s => s.tickHistory[symbol] ?? [])

  const chartData = history.slice(-60).map((t, i) => ({
    i,
    mid: ((parseFloat(t.bid) + parseFloat(t.ask)) / 2).toFixed(2),
  }))

  const mid  = tick ? ((parseFloat(tick.bid) + parseFloat(tick.ask)) / 2).toFixed(2) : '—'
  const prev = history.length > 1 ? history[history.length - 2] : null
  const prevMid = prev ? (parseFloat(prev.bid) + parseFloat(prev.ask)) / 2 : null
  const currMid = tick ? (parseFloat(tick.bid) + parseFloat(tick.ask)) / 2 : null
  const up = prevMid && currMid ? currMid >= prevMid : null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs text-gray-400 font-medium tracking-wider">{symbol}</span>
        {tick && (
          <span className="text-xs text-gray-500">{tick.latency_us}µs</span>
        )}
      </div>
      <div className={`text-2xl font-semibold mb-1 ${
        up === true ? 'text-green-400' : up === false ? 'text-red-400' : 'text-white'
      }`}>
        ${mid}
      </div>
      {tick && (
        <div className="flex gap-4 text-xs text-gray-500 mb-3">
          <span>bid {parseFloat(tick.bid).toFixed(2)}</span>
          <span>ask {parseFloat(tick.ask).toFixed(2)}</span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={50}>
        <LineChart data={chartData}>
          <Line type="monotone" dataKey="mid" stroke="#6366f1"
                dot={false} strokeWidth={1.5} />
          <YAxis domain={['auto', 'auto']} hide />
          <XAxis dataKey="i" hide />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

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
  const SYMBOLS = ['BTC-USDT', 'ETH-USDT']

  return (
    <div className="space-y-6">
      {/* Ticker cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {SYMBOLS.map(sym => <TickerCard key={sym} symbol={sym} />)}
      </div>

      {/* Signal feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">Live signals</h2>
        {signals.length === 0 ? (
          <p className="text-gray-500 text-sm">Waiting for signals…</p>
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
