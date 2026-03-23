/**
 * 价格图表组件 - 使用 Lightweight Charts
 * 
 * 支持实时 K 线图和深度图
 */

import { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts';

interface PriceChartProps {
  symbol: string;
  data: CandlestickData[];
  height?: number;
}

export function PriceChart({ symbol, data, height = 400 }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 创建图表
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#334155',
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // 创建 K 线系列
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    // 响应式调整
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
  }, [height]);

  // 更新数据
  useEffect(() => {
    if (seriesRef.current && data.length > 0) {
      seriesRef.current.setData(data);
    }
  }, [data]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-medium text-gray-300">{symbol}</h3>
        <div className="flex gap-2 text-xs">
          <button className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300">
            1m
          </button>
          <button className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300">
            5m
          </button>
          <button className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300">
            1h
          </button>
          <button className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300">
            1d
          </button>
        </div>
      </div>
      <div ref={chartContainerRef} />
    </div>
  );
}

/**
 * 实时价格线图表
 */
interface RealtimePriceChartProps {
  symbol: string;
  height?: number;
}

export function RealtimePriceChart({ symbol, height = 300 }: RealtimePriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        visible: false,
      },
    });

    const lineSeries = chart.addLineSeries({
      color: '#6366f1',
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
  }, [height]);

  return <div ref={chartContainerRef} />;
}

/**
 * 深度图表
 */
interface DepthChartProps {
  bids: Array<{ price: number; size: number }>;
  asks: Array<{ price: number; size: number }>;
  height?: number;
}

export function DepthChart({ bids, asks, height = 300 }: DepthChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bidSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const askSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      rightPriceScale: {
        borderColor: '#334155',
      },
      timeScale: {
        visible: false,
      },
    });

    // 买单深度
    const bidSeries = chart.addAreaSeries({
      topColor: 'rgba(34, 197, 94, 0.4)',
      bottomColor: 'rgba(34, 197, 94, 0.0)',
      lineColor: 'rgba(34, 197, 94, 1)',
      lineWidth: 2,
    });

    // 卖单深度
    const askSeries = chart.addAreaSeries({
      topColor: 'rgba(239, 68, 68, 0.4)',
      bottomColor: 'rgba(239, 68, 68, 0.0)',
      lineColor: 'rgba(239, 68, 68, 1)',
      lineWidth: 2,
    });

    chartRef.current = chart;
    bidSeriesRef.current = bidSeries;
    askSeriesRef.current = askSeries;

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
  }, [height]);

  // 更新深度数据
  useEffect(() => {
    if (!bidSeriesRef.current || !askSeriesRef.current) return;

    // 计算累积深度
    let cumBidSize = 0;
    const bidData = bids.map(({ price, size }) => {
      cumBidSize += size;
      return { time: price as Time, value: cumBidSize };
    });

    let cumAskSize = 0;
    const askData = asks.map(({ price, size }) => {
      cumAskSize += size;
      return { time: price as Time, value: cumAskSize };
    });

    bidSeriesRef.current.setData(bidData);
    askSeriesRef.current.setData(askData);
  }, [bids, asks]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">订单深度</h3>
      <div ref={chartContainerRef} />
    </div>
  );
}
