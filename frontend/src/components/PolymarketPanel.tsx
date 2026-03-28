import React, { useEffect, useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Activity, Search, Filter, SortAsc } from 'lucide-react';

interface PolymarketToken {
  token_id: string;
  outcome: string;
  price?: string;
}

interface PolymarketMarket {
  condition_id: string;
  question: string;
  description?: string;
  volume: number;
  liquidity: number;
  end_date_iso: string;
  tokens: PolymarketToken[];
  active: boolean;
}

type SortOption = 'volume' | 'liquidity' | 'ending_soon' | 'newest';

export default function PolymarketPanel() {
  const [markets, setMarkets] = useState<PolymarketMarket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('volume');
  const [minVolume, setMinVolume] = useState(0);

  useEffect(() => {
    fetchMarkets();
    const interval = setInterval(fetchMarkets, 30000); // 每 30 秒更新
    return () => clearInterval(interval);
  }, []);

  const fetchMarkets = async () => {
    try {
      const response = await fetch('/api/v1/polymarket/markets');
      
      if (!response.ok) {
        throw new Error('Failed to fetch Polymarket markets');
      }
      
      const data = await response.json();
      setMarkets(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch Polymarket markets:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  // 筛选和排序市场
  const filteredAndSortedMarkets = useMemo(() => {
    let filtered = markets;

    // 搜索过滤
    if (searchQuery) {
      filtered = filtered.filter(m => 
        m.question.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // 交易量过滤
    if (minVolume > 0) {
      filtered = filtered.filter(m => (m.volume || 0) >= minVolume);
    }

    // 排序
    const sorted = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'volume':
          return (b.volume || 0) - (a.volume || 0);
        case 'liquidity':
          return (b.liquidity || 0) - (a.liquidity || 0);
        case 'ending_soon':
          return new Date(a.end_date_iso).getTime() - new Date(b.end_date_iso).getTime();
        case 'newest':
          return new Date(b.end_date_iso).getTime() - new Date(a.end_date_iso).getTime();
        default:
          return 0;
      }
    });

    return sorted;
  }, [markets, searchQuery, minVolume, sortBy]);

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `$${(volume / 1000000).toFixed(2)}M`;
    } else if (volume >= 1000) {
      return `$${(volume / 1000).toFixed(1)}K`;
    }
    return `$${volume.toFixed(0)}`;
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-purple-400 animate-pulse" />
          <h2 className="text-lg font-semibold text-white">Polymarket Predictions</h2>
        </div>
        <div className="text-gray-400 text-sm">Loading markets...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-white">Polymarket Predictions</h2>
        </div>
        <div className="text-red-400 text-sm">
          ⚠️ {error}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-white">Polymarket Predictions</h2>
        </div>
        <div className="text-xs text-gray-500">
          {filteredAndSortedMarkets.length} / {markets.length} markets
        </div>
      </div>

      {/* Search and Filters */}
      <div className="mb-4 space-y-3">
        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search markets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
        </div>

        {/* Filters Row */}
        <div className="flex gap-3 items-center flex-wrap">
          {/* Sort By */}
          <div className="flex items-center gap-2">
            <SortAsc className="w-4 h-4 text-gray-500" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            >
              <option value="volume">Highest Volume</option>
              <option value="liquidity">Highest Liquidity</option>
              <option value="ending_soon">Ending Soon</option>
              <option value="newest">Newest</option>
            </select>
          </div>

          {/* Min Volume Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={minVolume}
              onChange={(e) => setMinVolume(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            >
              <option value={0}>All Volume</option>
              <option value={1000}>$1K+</option>
              <option value={10000}>$10K+</option>
              <option value={100000}>$100K+</option>
              <option value={1000000}>$1M+</option>
            </select>
          </div>

          {/* Clear Filters */}
          {(searchQuery || minVolume > 0) && (
            <button
              onClick={() => {
                setSearchQuery('');
                setMinVolume(0);
              }}
              className="text-xs text-purple-400 hover:text-purple-300 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>
      
      {/* Markets List */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto custom-scrollbar">
        {filteredAndSortedMarkets.length === 0 ? (
          <div className="text-gray-400 text-sm text-center py-8">
            {markets.length === 0 ? 'No active markets available' : 'No markets match your filters'}
          </div>
        ) : (
          filteredAndSortedMarkets.map((market) => (
            <MarketCard key={market.condition_id} market={market} />
          ))
        )}
      </div>
    </div>
  );
}

function MarketCard({ market }: { market: PolymarketMarket }) {
  const formatVolume = (volume: number) => {
    if (!volume || isNaN(volume)) return '$0';
    
    if (volume >= 1000000) {
      return `$${(volume / 1000000).toFixed(2)}M`;
    } else if (volume >= 1000) {
      return `$${(volume / 1000).toFixed(1)}K`;
    }
    return `$${volume.toFixed(0)}`;
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      
      if (diffDays < 0) return 'Ended';
      if (diffDays === 0) return 'Today';
      if (diffDays === 1) return 'Tomorrow';
      if (diffDays < 7) return `${diffDays} days`;
      
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition-colors cursor-pointer group">
      <div className="text-sm text-white mb-3 line-clamp-2 group-hover:text-purple-300 transition-colors">
        {market.question}
      </div>
      
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-4 text-xs text-gray-400">
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Vol:</span>
            <span className="text-gray-300">{formatVolume(market.volume)}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Ends:</span>
            <span className="text-gray-300">{formatDate(market.end_date_iso)}</span>
          </div>
        </div>
      </div>
      
      <div className="flex gap-2">
        {market.tokens.map((token) => {
          const price = token.price ? parseFloat(token.price) : 0;
          const probability = (price * 100).toFixed(1);
          const isYes = token.outcome.toLowerCase() === 'yes';
          
          return (
            <div
              key={token.token_id}
              className={`flex-1 rounded-md px-3 py-2 ${
                isYes 
                  ? 'bg-green-500/10 border border-green-500/20' 
                  : 'bg-red-500/10 border border-red-500/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-medium ${
                  isYes ? 'text-green-400' : 'text-red-400'
                }`}>
                  {token.outcome}
                </span>
                {price > 0 && (
                  <div className="flex items-center gap-1">
                    {isYes ? (
                      <TrendingUp className="w-3 h-3 text-green-400" />
                    ) : (
                      <TrendingDown className="w-3 h-3 text-red-400" />
                    )}
                    <span className={`text-sm font-semibold ${
                      isYes ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {probability}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
