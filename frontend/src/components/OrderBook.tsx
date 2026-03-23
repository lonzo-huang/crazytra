/**
 * 订单簿组件
 * 
 * 显示实时买卖盘深度
 */

interface OrderBookProps {
  symbol: string;
  bids: Array<{ price: string; size: string }>;
  asks: Array<{ price: string; size: string }>;
}

export function OrderBook({ symbol, bids, asks }: OrderBookProps) {
  // 计算最大数量用于进度条
  const maxSize = Math.max(
    ...bids.map(b => parseFloat(b.size)),
    ...asks.map(a => parseFloat(a.size))
  );

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">{symbol} 订单簿</h3>
      
      <div className="grid grid-cols-2 gap-4">
        {/* 买单 */}
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-2 px-2">
            <span>价格</span>
            <span>数量</span>
          </div>
          <div className="space-y-1">
            {bids.slice(0, 15).map((bid, i) => {
              const sizePercent = (parseFloat(bid.size) / maxSize) * 100;
              return (
                <div key={i} className="relative px-2 py-1">
                  <div 
                    className="absolute inset-0 bg-green-500/10"
                    style={{ width: `${sizePercent}%` }}
                  />
                  <div className="relative flex justify-between text-xs">
                    <span className="text-green-400 font-mono">
                      {parseFloat(bid.price).toFixed(2)}
                    </span>
                    <span className="text-gray-400 font-mono">
                      {parseFloat(bid.size).toFixed(4)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 卖单 */}
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-2 px-2">
            <span>价格</span>
            <span>数量</span>
          </div>
          <div className="space-y-1">
            {asks.slice(0, 15).map((ask, i) => {
              const sizePercent = (parseFloat(ask.size) / maxSize) * 100;
              return (
                <div key={i} className="relative px-2 py-1">
                  <div 
                    className="absolute inset-0 bg-red-500/10"
                    style={{ width: `${sizePercent}%` }}
                  />
                  <div className="relative flex justify-between text-xs">
                    <span className="text-red-400 font-mono">
                      {parseFloat(ask.price).toFixed(2)}
                    </span>
                    <span className="text-gray-400 font-mono">
                      {parseFloat(ask.size).toFixed(4)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 价差 */}
      {bids.length > 0 && asks.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">价差</span>
            <span className="text-gray-300 font-mono">
              {(parseFloat(asks[0].price) - parseFloat(bids[0].price)).toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
