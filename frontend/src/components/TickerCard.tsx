/**
 * Ticker 卡片组件
 * 
 * 显示实时价格和迷你图表
 */

import { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts';

interface TickerCardProps {
  symbol: string;
  bid: string;
  ask: string;
  last: string;
  latency_us?: number;
  history: Array<{ time: number; price: number }>;
}

export function TickerCard({ symbol, bid, ask, last, latency_us, history }: TickerCardProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const currentPrice = parseFloat(last);
  const prevPrice = history.length > 1 ? history[history.length - 2].price : currentPrice;
  const priceChange = currentPrice - prevPrice;
  const priceChangePercent = prevPrice > 0 ? (priceChange / prevPrice) * 100 : 0;
  const isUp = priceChange >= 0;

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 60,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        visible: false,
      },
      timeScale: {
        visible: false,
      },
    });

    const lineSeries = chart.addLineSeries({
      color: isUp ? '#22c55e' : '#ef4444',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [isUp]);

  // 更新图表数据
  useEffect(() => {
    if (seriesRef.current && history.length > 0) {
      const chartData: LineData[] = history.map(h => ({
        time: (h.time / 1000) as Time, // 转换为秒
        value: h.price,
      }));
      seriesRef.current.setData(chartData);
    }
  }, [history]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
      {/* 头部 */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-sm font-medium text-gray-300">{symbol}</h3>
          {latency_us !== undefined && (
            <span className="text-xs text-gray-500">{latency_us}µs</span>
          )}
        </div>
        <div className={`text-xs font-medium px-2 py-1 rounded ${
          isUp ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {isUp ? '+' : ''}{priceChangePercent.toFixed(2)}%
        </div>
      </div>

      {/* 价格 */}
      <div className={`text-2xl font-bold mb-1 ${
        isUp ? 'text-green-400' : 'text-red-400'
      }`}>
        ${parseFloat(last).toFixed(2)}
      </div>

      {/* 买卖价 */}
      <div className="flex gap-4 text-xs text-gray-500 mb-3">
        <span>买 {parseFloat(bid).toFixed(2)}</span>
        <span>卖 {parseFloat(ask).toFixed(2)}</span>
      </div>

      {/* 迷你图表 */}
      <div ref={chartContainerRef} />
    </div>
  );
}
