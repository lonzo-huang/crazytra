// ── Strategies page ──────────────────────────────────────
import { useTradeStore } from '../store/tradeStore'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
} from 'recharts'

export function Strategies() {
  const signals = useTradeStore(s => s.signals)

  // Count signals per strategy
  const byStrategy: Record<string, { long: number; short: number; exit: number }> = {}
  for (const sig of signals) {
    if (!byStrategy[sig.strategy_id]) byStrategy[sig.strategy_id] = { long: 0, short: 0, exit: 0 }
    const dir = sig.direction as 'long' | 'short' | 'exit'
    if (dir in byStrategy[sig.strategy_id]) byStrategy[sig.strategy_id][dir]++
  }

  const chartData = Object.entries(byStrategy).map(([id, counts]) => ({
    id: id.replace('_v1', '').replace('_', ' '),
    ...counts,
    total: counts.long + counts.short + counts.exit,
  }))

  return (
    <div className="space-y-6">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-4">Signal activity by strategy</h2>
        {chartData.length === 0 ? (
          <p className="text-gray-500 text-sm">No signals yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <XAxis dataKey="id" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />
              <Bar dataKey="long"  fill="#22c55e" radius={[3,3,0,0]} />
              <Bar dataKey="short" fill="#ef4444" radius={[3,3,0,0]} />
              <Bar dataKey="exit"  fill="#eab308" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">Active strategies</h2>
        <div className="space-y-2">
          {['ma_cross_v1', 'mean_reversion_v1'].map(id => (
            <div key={id}
              className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
              <div>
                <div className="text-sm text-white">{id}</div>
                <div className="text-xs text-gray-400 mt-0.5">BTC-USDT · ETH-USDT</div>
              </div>
              <span className="text-xs bg-green-900 text-green-300 px-2 py-0.5 rounded-full">
                running
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Strategies
