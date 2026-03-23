import { useTradeStore } from '../store/tradeStore'

const SEVERITY_STYLE: Record<string, string> = {
  critical: 'border-red-500/60 bg-red-500/10 text-red-300',
  warn:     'border-yellow-500/60 bg-yellow-500/10 text-yellow-300',
}

const KIND_LABEL: Record<string, string> = {
  circuit_breaker: 'Circuit breaker',
  daily_loss:      'Daily loss limit',
  drawdown:        'Max drawdown',
  position_limit:  'Position limit',
}

export default function Alerts() {
  const alerts = useTradeStore(s => s.alerts)

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-4">
          Risk alerts
          {alerts.length > 0 && (
            <span className="ml-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
              {alerts.filter(a => a.severity === 'critical').length}
            </span>
          )}
        </h2>

        {alerts.length === 0 ? (
          <p className="text-gray-500 text-sm">No alerts · risk engine nominal</p>
        ) : (
          <div className="space-y-2">
            {alerts.map(a => (
              <div key={a.alert_id}
                className={`border rounded-lg px-4 py-3 ${SEVERITY_STYLE[a.severity] ?? ''}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold uppercase tracking-wide">
                    {KIND_LABEL[a.kind] ?? a.kind}
                  </span>
                  <span className="text-xs opacity-60">
                    {new Date(a.timestamp / 1_000_000).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm">{a.message}</div>
                {a.symbol && (
                  <div className="text-xs opacity-60 mt-1">{a.symbol}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
