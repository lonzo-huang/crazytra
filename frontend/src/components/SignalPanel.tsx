/**
 * 信号面板组件 - 包含过滤、统计和详情功能
 */

import { useState, useMemo } from 'react'

interface Signal {
  signal_id: string
  symbol: string
  direction: 'long' | 'short' | 'exit' | 'hold'
  strength: number
  confidence?: number
  strategy_id: string
  timestamp_ns: number
  llm_weight?: number
  reason?: string
  entry_price?: string
  target_price?: string
  stop_loss?: string
}

interface SignalPanelProps {
  signals: Signal[]
}

export function SignalPanel({ signals }: SignalPanelProps) {
  // 过滤状态
  const [filterSymbol, setFilterSymbol] = useState<string>('all')
  const [filterStrategy, setFilterStrategy] = useState<string>('all')
  const [filterDirection, setFilterDirection] = useState<string>('all')
  
  // 展开的信号详情
  const [expandedSignal, setExpandedSignal] = useState<string | null>(null)

  // 获取所有唯一的交易对和策略
  const { symbols, strategies } = useMemo(() => {
    const symbolSet = new Set<string>()
    const strategySet = new Set<string>()
    signals.forEach(sig => {
      symbolSet.add(sig.symbol)
      strategySet.add(sig.strategy_id)
    })
    return {
      symbols: Array.from(symbolSet).sort(),
      strategies: Array.from(strategySet).sort(),
    }
  }, [signals])

  // 过滤后的信号
  const filteredSignals = useMemo(() => {
    return signals.filter(sig => {
      if (filterSymbol !== 'all' && sig.symbol !== filterSymbol) return false
      if (filterStrategy !== 'all' && sig.strategy_id !== filterStrategy) return false
      if (filterDirection !== 'all' && sig.direction !== filterDirection) return false
      return true
    })
  }, [signals, filterSymbol, filterStrategy, filterDirection])

  // 今日信号统计
  const todayStats = useMemo(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayStart = today.getTime() * 1_000_000 // 转换为纳秒

    const todaySignals = signals.filter(sig => sig.timestamp_ns >= todayStart)
    
    const longCount = todaySignals.filter(s => s.direction === 'long').length
    const shortCount = todaySignals.filter(s => s.direction === 'short').length
    const exitCount = todaySignals.filter(s => s.direction === 'exit').length

    return {
      total: todaySignals.length,
      long: longCount,
      short: shortCount,
      exit: exitCount,
    }
  }, [signals])

  // 策略表现统计
  const strategyStats = useMemo(() => {
    const stats: Record<string, { count: number; avgStrength: number }> = {}
    
    signals.forEach(sig => {
      if (!stats[sig.strategy_id]) {
        stats[sig.strategy_id] = { count: 0, avgStrength: 0 }
      }
      stats[sig.strategy_id].count++
      stats[sig.strategy_id].avgStrength += sig.strength
    })

    Object.keys(stats).forEach(key => {
      stats[key].avgStrength /= stats[key].count
    })

    return stats
  }, [signals])

  // 切换信号详情展开
  const toggleExpand = (signalId: string) => {
    setExpandedSignal(expandedSignal === signalId ? null : signalId)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日信号</div>
          <div className="text-2xl font-bold text-white">{todayStats.total}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">做多</div>
          <div className="text-2xl font-bold text-green-400">{todayStats.long}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">做空</div>
          <div className="text-2xl font-bold text-red-400">{todayStats.short}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">平仓</div>
          <div className="text-2xl font-bold text-yellow-400">{todayStats.exit}</div>
        </div>
      </div>

      {/* 过滤器 */}
      <div className="flex flex-wrap gap-3 mb-4">
        {/* 交易对过滤 */}
        <select
          value={filterSymbol}
          onChange={(e) => setFilterSymbol(e.target.value)}
          className="bg-gray-800 text-gray-300 text-sm rounded px-3 py-2 border border-gray-700 focus:border-indigo-500 focus:outline-none"
        >
          <option value="all">所有交易对</option>
          {symbols.map(sym => (
            <option key={sym} value={sym}>{sym}</option>
          ))}
        </select>

        {/* 策略过滤 */}
        <select
          value={filterStrategy}
          onChange={(e) => setFilterStrategy(e.target.value)}
          className="bg-gray-800 text-gray-300 text-sm rounded px-3 py-2 border border-gray-700 focus:border-indigo-500 focus:outline-none"
        >
          <option value="all">所有策略</option>
          {strategies.map(strat => (
            <option key={strat} value={strat}>{strat}</option>
          ))}
        </select>

        {/* 方向过滤 */}
        <select
          value={filterDirection}
          onChange={(e) => setFilterDirection(e.target.value)}
          className="bg-gray-800 text-gray-300 text-sm rounded px-3 py-2 border border-gray-700 focus:border-indigo-500 focus:outline-none"
        >
          <option value="all">所有方向</option>
          <option value="long">做多</option>
          <option value="short">做空</option>
          <option value="exit">平仓</option>
          <option value="hold">持有</option>
        </select>

        {/* 清除过滤器 */}
        {(filterSymbol !== 'all' || filterStrategy !== 'all' || filterDirection !== 'all') && (
          <button
            onClick={() => {
              setFilterSymbol('all')
              setFilterStrategy('all')
              setFilterDirection('all')
            }}
            className="text-xs text-gray-400 hover:text-white px-3 py-2 bg-gray-800 rounded border border-gray-700"
          >
            清除过滤
          </button>
        )}

        {/* 显示过滤结果数量 */}
        <div className="flex items-center text-sm text-gray-500">
          显示 {filteredSignals.length} / {signals.length} 条信号
        </div>
      </div>

      {/* 策略表现 */}
      {Object.keys(strategyStats).length > 0 && (
        <div className="mb-4 p-3 bg-gray-800 rounded-lg">
          <h3 className="text-xs font-medium text-gray-400 mb-2">策略表现</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(strategyStats).map(([strategy, stats]) => (
              <div key={strategy} className="flex justify-between items-center text-xs">
                <span className="text-gray-300 truncate mr-2">{strategy}</span>
                <div className="flex gap-2">
                  <span className="text-gray-500">{stats.count}条</span>
                  <span className="text-indigo-400">{(stats.avgStrength * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 信号列表 */}
      <div className="space-y-1 max-h-96 overflow-y-auto">
        {filteredSignals.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-4">
            {signals.length === 0 ? '等待信号...' : '没有符合条件的信号'}
          </p>
        ) : (
          filteredSignals.slice(0, 100).map(sig => (
            <SignalRow
              key={sig.signal_id}
              signal={sig}
              isExpanded={expandedSignal === sig.signal_id}
              onToggle={() => toggleExpand(sig.signal_id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

// 信号行组件
function SignalRow({ signal, isExpanded, onToggle }: {
  signal: Signal
  isExpanded: boolean
  onToggle: () => void
}) {
  const dirColor = signal.direction === 'long' ? 'text-green-400'
    : signal.direction === 'short' ? 'text-red-400'
    : signal.direction === 'exit' ? 'text-yellow-400'
    : 'text-gray-400'

  const ts = new Date(signal.timestamp_ns / 1_000_000).toLocaleTimeString()

  return (
    <div className="border-b border-gray-800">
      {/* 主行 - 可点击展开 */}
      <div
        onClick={onToggle}
        className="flex items-center gap-3 py-2 cursor-pointer hover:bg-gray-800/50 px-2 rounded transition-colors"
      >
        <span className="text-gray-500 text-xs w-20 shrink-0">{ts}</span>
        <span className="text-gray-300 w-24 shrink-0 font-medium">{signal.symbol}</span>
        <span className={`${dirColor} w-12 shrink-0 font-medium uppercase text-xs`}>
          {signal.direction}
        </span>
        <div className="flex-1 bg-gray-800 rounded-full h-1.5">
          <div
            className="bg-indigo-500 h-1.5 rounded-full transition-all"
            style={{ width: `${signal.strength * 100}%` }}
          />
        </div>
        <span className="text-gray-400 text-xs w-10 text-right">
          {(signal.strength * 100).toFixed(0)}%
        </span>
        <span className="text-gray-500 text-xs hidden md:block truncate max-w-xs">
          {signal.strategy_id}
        </span>
        <span className="text-gray-600 text-xs">
          {isExpanded ? '▼' : '▶'}
        </span>
      </div>

      {/* 展开的详情 */}
      {isExpanded && (
        <div className="px-2 pb-3 pt-1 bg-gray-800/30 rounded-b space-y-2">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            {/* 置信度 */}
            {signal.confidence !== undefined && (
              <div>
                <span className="text-gray-500">置信度: </span>
                <span className="text-gray-300 font-medium">
                  {(signal.confidence * 100).toFixed(1)}%
                </span>
              </div>
            )}

            {/* LLM 权重 */}
            {signal.llm_weight !== undefined && (
              <div>
                <span className="text-gray-500">LLM 权重: </span>
                <span className={`font-medium ${
                  signal.llm_weight > 0 ? 'text-green-400' : 
                  signal.llm_weight < 0 ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {signal.llm_weight > 0 ? '+' : ''}{signal.llm_weight.toFixed(3)}
                </span>
              </div>
            )}

            {/* 入场价 */}
            {signal.entry_price && (
              <div>
                <span className="text-gray-500">入场价: </span>
                <span className="text-gray-300 font-mono">${signal.entry_price}</span>
              </div>
            )}

            {/* 目标价 */}
            {signal.target_price && (
              <div>
                <span className="text-gray-500">目标价: </span>
                <span className="text-green-400 font-mono">${signal.target_price}</span>
              </div>
            )}

            {/* 止损价 */}
            {signal.stop_loss && (
              <div>
                <span className="text-gray-500">止损价: </span>
                <span className="text-red-400 font-mono">${signal.stop_loss}</span>
              </div>
            )}

            {/* 信号 ID */}
            <div className="col-span-2 md:col-span-3">
              <span className="text-gray-500">信号 ID: </span>
              <span className="text-gray-400 font-mono text-xs">{signal.signal_id}</span>
            </div>
          </div>

          {/* 原因说明 */}
          {signal.reason && (
            <div className="text-xs">
              <span className="text-gray-500">原因: </span>
              <span className="text-gray-300">{signal.reason}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
