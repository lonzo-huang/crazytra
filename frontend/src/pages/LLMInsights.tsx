import { useTradeStore } from '../store/tradeStore'

function ScoreBar({ score }: { score: number }) {
  const pct    = ((score + 1) / 2) * 100
  const color  = score > 0.2 ? 'bg-green-500' : score < -0.2 ? 'bg-red-500' : 'bg-gray-500'
  return (
    <div className="relative h-2 bg-gray-700 rounded-full w-full">
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-500" />
      <div
        className={`absolute h-2 rounded-full ${color} transition-all`}
        style={{
          left:  score >= 0 ? '50%' : `${pct}%`,
          width: `${Math.abs(score) * 50}%`,
        }}
      />
    </div>
  )
}

export default function LLMInsights() {
  const weights = useTradeStore(s => s.weights)
  const entries = Object.values(weights)

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-1">LLM sentiment weights</h2>
        <p className="text-xs text-gray-500 mb-4">
          Updated by LLM layer · injected directly into SignalCombinator
        </p>

        {entries.length === 0 ? (
          <p className="text-gray-500 text-sm">Waiting for LLM analysis…</p>
        ) : (
          <div className="space-y-5">
            {entries.map(w => (
              <div key={w.symbol} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-white text-sm font-medium">{w.symbol}</span>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-semibold ${
                      w.llm_score > 0.2 ? 'text-green-400'
                      : w.llm_score < -0.2 ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      {w.llm_score >= 0 ? '+' : ''}{w.llm_score.toFixed(3)}
                    </span>
                    <span className="text-xs text-gray-500">
                      conf {(w.confidence * 100).toFixed(0)}%
                    </span>
                    <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                      {w.horizon}
                    </span>
                  </div>
                </div>
                <ScoreBar score={w.llm_score} />
                {w.key_drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {w.key_drivers.map((d, i) => (
                      <span key={i}
                        className="text-xs bg-indigo-900/50 text-indigo-300 px-2 py-0.5 rounded">
                        {d}
                      </span>
                    ))}
                  </div>
                )}
                <div className="text-xs text-gray-600">model: {w.model_used}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">Score legend</h2>
        <div className="grid grid-cols-3 gap-2 text-xs text-center">
          <div className="bg-red-900/30 text-red-400 rounded px-2 py-2">
            −1.0 to −0.5<br/>strongly bearish
          </div>
          <div className="bg-gray-800 text-gray-400 rounded px-2 py-2">
            −0.2 to +0.2<br/>neutral
          </div>
          <div className="bg-green-900/30 text-green-400 rounded px-2 py-2">
            +0.5 to +1.0<br/>strongly bullish
          </div>
        </div>
      </div>
    </div>
  )
}
