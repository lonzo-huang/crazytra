import { useTradeStore } from '../store/tradeStore'

const KIND_COLOR: Record<string, string> = {
  filled:         'text-green-400',
  partial_filled: 'text-yellow-400',
  cancelled:      'text-gray-400',
  rejected:       'text-red-400',
}

export default function Orders() {
  const orders = useTradeStore(s => s.orders)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h2 className="text-sm font-medium text-gray-300 mb-4">Order history</h2>
      {orders.length === 0 ? (
        <p className="text-gray-500 text-sm">No orders yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b border-gray-800">
                <th className="text-left pb-2 pr-4">Time</th>
                <th className="text-left pb-2 pr-4">Symbol</th>
                <th className="text-left pb-2 pr-4">Status</th>
                <th className="text-right pb-2 pr-4">Qty</th>
                <th className="text-right pb-2 pr-4">Price</th>
                <th className="text-right pb-2">Fee</th>
              </tr>
            </thead>
            <tbody>
              {orders.slice(0, 100).map(o => (
                <tr key={o.event_id} className="border-b border-gray-800/50">
                  <td className="py-2 pr-4 text-gray-500 text-xs">
                    {new Date(o.timestamp / 1_000_000).toLocaleTimeString()}
                  </td>
                  <td className="py-2 pr-4 text-gray-200">{o.symbol}</td>
                  <td className={`py-2 pr-4 font-medium ${KIND_COLOR[o.kind] ?? 'text-gray-400'}`}>
                    {o.kind}
                  </td>
                  <td className="py-2 pr-4 text-right text-gray-300">
                    {parseFloat(o.filled_qty).toFixed(5)}
                  </td>
                  <td className="py-2 pr-4 text-right text-gray-300">
                    ${parseFloat(o.filled_px).toFixed(2)}
                  </td>
                  <td className="py-2 text-right text-gray-500">
                    ${parseFloat(o.fee).toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
