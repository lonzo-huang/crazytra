import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TrendingUp, TrendingDown, Activity, Clock } from 'lucide-react';

interface Market {
  condition_id: string;
  question: string;
  volume: number;
  liquidity: number;
  end_date_iso: string;
  active: boolean;
  tokens: Array<{
    token_id: string;
    outcome: string;
  }>;
}

interface StrategySignal {
  strategy: string;
  asset_id: string;
  action: string;
  side: string;
  price: number;
  size: number;
  confidence: number;
  reason: string;
  timestamp: string;
}

interface OrderBook {
  instrument_id: string;
  bids: number[][];
  asks: number[][];
  last_update: string;
}

export function PolymarketTradingPanel() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [btcMarkets, setBtcMarkets] = useState<Market[]>([]);
  const [signals, setSignals] = useState<StrategySignal[]>([]);
  const [orderBooks, setOrderBooks] = useState<Record<string, OrderBook>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('markets');

  // 获取市场数据
  const fetchMarkets = async () => {
    try {
      const response = await fetch('/api/v1/polymarket/markets');
      const data = await response.json();
      setMarkets(data);
    } catch (error) {
      console.error('Failed to fetch markets:', error);
    }
  };

  // 获取 BTC 市场
  const fetchBtcMarkets = async () => {
    try {
      const response = await fetch('/api/v1/polymarket/markets/btc');
      const data = await response.json();
      setBtcMarkets(data.markets);
    } catch (error) {
      console.error('Failed to fetch BTC markets:', error);
    }
  };

  // 获取策略信号
  const fetchSignals = async () => {
    try {
      const response = await fetch('/api/v1/polymarket/strategy/btc5m');
      const data = await response.json();
      setSignals(data.signals || []);
    } catch (error) {
      console.error('Failed to fetch signals:', error);
    }
  };

  // 获取订单簿
  const fetchOrderBooks = async (assetIds: string[]) => {
    const books: Record<string, OrderBook> = {};
    
    for (const assetId of assetIds) {
      try {
        const response = await fetch(`/api/v1/polymarket/orderbook/${assetId}`);
        if (response.ok) {
          const data = await response.json();
          books[assetId] = data;
        }
      } catch (error) {
        console.error(`Failed to fetch order book for ${assetId}:`, error);
      }
    }
    
    setOrderBooks(books);
  };

  // 初始化数据
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchMarkets(),
        fetchBtcMarkets(),
        fetchSignals()
      ]);
      setLoading(false);
    };

    loadData();

    // 设置定时刷新
    const interval = setInterval(() => {
      fetchSignals();
    }, 30000); // 30秒刷新一次

    return () => clearInterval(interval);
  }, []);

  // 当市场数据更新时，获取订单簿
  useEffect(() => {
    if (btcMarkets.length > 0) {
      const assetIds = btcMarkets
        .flatMap(market => market.tokens)
        .map(token => token.token_id)
        .slice(0, 5); // 只获取前5个资产的订单簿
      
      fetchOrderBooks(assetIds);
    }
  }, [btcMarkets]);

  // 格式化数字
  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return `$${(num / 1000000).toFixed(1)}M`;
    } else if (num >= 1000) {
      return `$${(num / 1000).toFixed(1)}K`;
    }
    return `$${num.toFixed(2)}`;
  };

  // 格式化时间
  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // 获取订单簿信息
  const getOrderBookInfo = (assetId: string) => {
    const book = orderBooks[assetId];
    if (!book || book.bids.length === 0 || book.asks.length === 0) {
      return { spread: 0, midPrice: 0 };
    }

    const bestBid = book.bids[0][0];
    const bestAsk = book.asks[0][0];
    const spread = bestAsk - bestBid;
    const midPrice = (bestBid + bestAsk) / 2;

    return { spread, midPrice };
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center h-32">
            <Activity className="h-6 w-6 animate-spin" />
            <span className="ml-2">Loading Polymarket data...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <TrendingUp className="h-5 w-5 mr-2" />
          Polymarket Trading
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="markets">All Markets</TabsTrigger>
            <TabsTrigger value="btc">BTC Markets</TabsTrigger>
            <TabsTrigger value="signals">Strategy Signals</TabsTrigger>
          </TabsList>

          <TabsContent value="markets" className="space-y-4">
            <div className="grid gap-4">
              {markets.slice(0, 5).map((market) => (
                <Card key={market.condition_id} className="p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-medium text-sm mb-2">{market.question}</h3>
                      <div className="flex gap-4 text-xs text-muted-foreground">
                        <span>Volume: {formatNumber(market.volume)}</span>
                        <span>Liquidity: {formatNumber(market.liquidity)}</span>
                      </div>
                    </div>
                    <Badge variant={market.active ? "default" : "secondary"}>
                      {market.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="btc" className="space-y-4">
            <div className="grid gap-4">
              {btcMarkets.map((market) => (
                <Card key={market.condition_id} className="p-4">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex-1">
                      <h3 className="font-medium text-sm mb-2">{market.question}</h3>
                      <div className="flex gap-4 text-xs text-muted-foreground">
                        <span>Volume: {formatNumber(market.volume)}</span>
                        <span>Liquidity: {formatNumber(market.liquidity)}</span>
                      </div>
                    </div>
                    <Badge variant="default">BTC</Badge>
                  </div>
                  
                  {/* 显示订单簿信息 */}
                  {market.tokens.slice(0, 2).map((token) => {
                    const bookInfo = getOrderBookInfo(token.token_id);
                    return (
                      <div key={token.token_id} className="flex justify-between items-center text-xs">
                        <span className="font-medium">{token.outcome}</span>
                        <div className="flex gap-2">
                          <span>${bookInfo.midPrice.toFixed(3)}</span>
                          <span className="text-muted-foreground">
                            Spread: {(bookInfo.spread * 100).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="signals" className="space-y-4">
            <div className="grid gap-4">
              {signals.length === 0 ? (
                <Card className="p-4">
                  <div className="text-center text-muted-foreground">
                    <Clock className="h-8 w-8 mx-auto mb-2" />
                    <p>No active signals</p>
                    <p className="text-xs">Strategy is monitoring for opportunities...</p>
                  </div>
                </Card>
              ) : (
                signals.map((signal, index) => (
                  <Card key={index} className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={signal.side === 'yes' ? 'default' : 'destructive'}>
                            {signal.side.toUpperCase()}
                          </Badge>
                          <span className="text-sm font-medium">
                            {signal.action.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mb-2">{signal.reason}</p>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium">${signal.price.toFixed(3)}</div>
                        <div className="text-xs text-muted-foreground">
                          Size: {signal.size}
                        </div>
                      </div>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span>Confidence: {(signal.confidence * 100).toFixed(1)}%</span>
                      <span>{formatTime(signal.timestamp)}</span>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
