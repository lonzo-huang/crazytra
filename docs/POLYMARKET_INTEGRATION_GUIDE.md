# Polymarket 集成指南

## 概述

Polymarket 是一个去中心化的预测市场平台，用户可以对各种事件的结果进行交易。本指南将帮助你将 Polymarket 数据集成到 MirrorQuant 平台。

## Polymarket 基础

### 什么是 Polymarket？

- **类型**: 预测市场（Prediction Market）
- **区块链**: Polygon（以太坊 Layer 2）
- **交易对**: 事件结果（Yes/No）
- **价格范围**: $0.00 - $1.00（代表概率）

### 示例市场

```
市场: "Will Bitcoin reach $100,000 by end of 2024?"
- YES token: $0.35 (35% 概率)
- NO token: $0.65 (65% 概率)
```

## API 访问

### 1. Polymarket CLOB API

**官方文档**: https://docs.polymarket.com

**Base URL**: `https://clob.polymarket.com`

**主要端点**:
```
GET /markets - 获取所有市场
GET /markets/{condition_id} - 获取特定市场
GET /book - 获取订单簿
GET /trades - 获取交易历史
```

### 2. 无需 API Key

Polymarket 的公开数据 API **不需要 API Key**，可以直接访问。

## 快速开始

### 第一步：测试 API 访问

在浏览器或 PowerShell 中测试：

```powershell
# 获取热门市场
curl https://clob.polymarket.com/markets

# 获取特定市场的订单簿
curl "https://clob.polymarket.com/book?token_id=<TOKEN_ID>"
```

### 第二步：创建数据适配器

创建 Python 脚本来获取 Polymarket 数据：

```python
# polymarket_test.py
import requests
import json

class PolymarketClient:
    BASE_URL = "https://clob.polymarket.com"
    
    def get_markets(self, limit=10):
        """获取市场列表"""
        url = f"{self.BASE_URL}/markets"
        params = {"limit": limit, "active": True}
        response = requests.get(url, params=params)
        return response.json()
    
    def get_market_price(self, token_id):
        """获取市场价格"""
        url = f"{self.BASE_URL}/book"
        params = {"token_id": token_id}
        response = requests.get(url, params=params)
        return response.json()
    
    def get_trades(self, market_id, limit=20):
        """获取交易历史"""
        url = f"{self.BASE_URL}/trades"
        params = {"market": market_id, "limit": limit}
        response = requests.get(url, params=params)
        return response.json()

# 测试
if __name__ == "__main__":
    client = PolymarketClient()
    
    # 获取热门市场
    markets = client.get_markets(limit=5)
    
    print("Top 5 Polymarket Markets:")
    print("=" * 80)
    
    for market in markets:
        print(f"\nMarket: {market.get('question', 'N/A')}")
        print(f"Volume: ${market.get('volume', 0):,.2f}")
        print(f"End Date: {market.get('end_date_iso', 'N/A')}")
        
        # 获取价格
        tokens = market.get('tokens', [])
        if tokens:
            for token in tokens:
                token_id = token.get('token_id')
                outcome = token.get('outcome')
                
                # 获取最新价格
                book = client.get_market_price(token_id)
                
                if book and 'bids' in book and book['bids']:
                    best_bid = float(book['bids'][0]['price'])
                    print(f"  {outcome}: ${best_bid:.4f} ({best_bid*100:.1f}%)")
```

### 第三步：运行测试

```powershell
# 创建测试脚本
cd d:\projects\MirrorQuant
New-Item -Path "polymarket_test.py" -ItemType File

# 安装依赖
pip install requests

# 运行测试
python polymarket_test.py
```

## 集成到 MirrorQuant

### 方案 1：简单集成（推荐开始）

**目标**: 在前端显示 Polymarket 市场数据

**步骤**:

1. **创建 Polymarket 数据服务**

```python
# nautilus-core/adapters/polymarket_adapter.py
import asyncio
import aiohttp
from typing import List, Dict
from decimal import Decimal

class PolymarketDataAdapter:
    """Polymarket 数据适配器"""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session = None
    
    async def connect(self):
        """建立连接"""
        self.session = aiohttp.ClientSession()
    
    async def disconnect(self):
        """断开连接"""
        if self.session:
            await self.session.close()
    
    async def get_markets(self, limit: int = 20) -> List[Dict]:
        """获取市场列表"""
        url = f"{self.BASE_URL}/markets"
        params = {"limit": limit, "active": True}
        
        async with self.session.get(url, params=params) as response:
            return await response.json()
    
    async def get_market_orderbook(self, token_id: str) -> Dict:
        """获取订单簿"""
        url = f"{self.BASE_URL}/book"
        params = {"token_id": token_id}
        
        async with self.session.get(url, params=params) as response:
            return await response.json()
    
    async def stream_market_data(self, market_ids: List[str]):
        """轮询市场数据（Polymarket 没有 WebSocket）"""
        while True:
            for market_id in market_ids:
                try:
                    data = await self.get_market_orderbook(market_id)
                    yield {
                        "market_id": market_id,
                        "data": data,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                except Exception as e:
                    print(f"Error fetching {market_id}: {e}")
            
            await asyncio.sleep(5)  # 每 5 秒更新一次
```

2. **创建 API 端点**

```go
// api-gateway/handlers/polymarket.go
package handlers

import (
    "encoding/json"
    "net/http"
    "github.com/gin-gonic/gin"
)

type PolymarketMarket struct {
    Question    string  `json:"question"`
    Volume      float64 `json:"volume"`
    EndDate     string  `json:"end_date_iso"`
    Tokens      []Token `json:"tokens"`
}

type Token struct {
    TokenID string `json:"token_id"`
    Outcome string `json:"outcome"`
    Price   string `json:"price"`
}

// GET /api/v1/polymarket/markets
func (h *Handler) GetPolymarketMarkets(c *gin.Context) {
    // 从 Python 服务获取数据
    resp, err := http.Get("http://nautilus-core:8000/polymarket/markets")
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    defer resp.Body.Close()
    
    var markets []PolymarketMarket
    if err := json.NewDecoder(resp.Body).Decode(&markets); err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, markets)
}
```

3. **前端展示组件**

```typescript
// frontend/src/components/PolymarketPanel.tsx
import React, { useEffect, useState } from 'react';

interface PolymarketMarket {
  question: string;
  volume: number;
  end_date_iso: string;
  tokens: Array<{
    token_id: string;
    outcome: string;
    price: string;
  }>;
}

export default function PolymarketPanel() {
  const [markets, setMarkets] = useState<PolymarketMarket[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMarkets();
    const interval = setInterval(fetchMarkets, 10000); // 每 10 秒更新
    return () => clearInterval(interval);
  }, []);

  const fetchMarkets = async () => {
    try {
      const response = await fetch('/api/v1/polymarket/markets');
      const data = await response.json();
      setMarkets(data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch Polymarket markets:', error);
    }
  };

  if (loading) {
    return <div className="text-gray-400">Loading Polymarket markets...</div>;
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h2 className="text-lg font-semibold text-white mb-4">
        Polymarket Prediction Markets
      </h2>
      
      <div className="space-y-3">
        {markets.map((market, index) => (
          <div
            key={index}
            className="bg-gray-800 rounded-lg p-3 hover:bg-gray-750 transition"
          >
            <div className="text-sm text-white mb-2">
              {market.question}
            </div>
            
            <div className="flex items-center justify-between text-xs">
              <div className="text-gray-400">
                Volume: ${market.volume.toLocaleString()}
              </div>
              
              <div className="flex gap-3">
                {market.tokens.map((token) => {
                  const price = parseFloat(token.price);
                  const probability = (price * 100).toFixed(1);
                  const color = token.outcome === 'Yes' 
                    ? 'text-green-400' 
                    : 'text-red-400';
                  
                  return (
                    <div key={token.token_id} className={color}>
                      {token.outcome}: {probability}%
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 方案 2：完整集成（后续）

**包含**:
- Nautilus Trader 自定义适配器
- 实盘交易支持
- 策略回测
- WebSocket 实时数据（使用轮询模拟）

## 测试步骤

### 1. 最简单的测试

创建独立的测试脚本：

```python
# test_polymarket.py
import requests

def test_polymarket_api():
    """测试 Polymarket API"""
    
    print("Testing Polymarket API...")
    print("=" * 80)
    
    # 获取市场列表
    url = "https://clob.polymarket.com/markets"
    params = {"limit": 3, "active": True}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        markets = response.json()
        
        print(f"\nFound {len(markets)} markets:")
        
        for i, market in enumerate(markets, 1):
            print(f"\n{i}. {market.get('question', 'N/A')}")
            print(f"   Volume: ${market.get('volume', 0):,.2f}")
            print(f"   Liquidity: ${market.get('liquidity', 0):,.2f}")
            
            tokens = market.get('tokens', [])
            for token in tokens:
                outcome = token.get('outcome', 'N/A')
                print(f"   - {outcome} token: {token.get('token_id', 'N/A')}")
        
        print("\n✅ Polymarket API test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_polymarket_api()
```

运行测试：
```powershell
python test_polymarket.py
```

### 2. 集成到前端测试

在 Dashboard 页面添加 Polymarket 面板：

```typescript
// frontend/src/pages/Dashboard.tsx
import PolymarketPanel from '../components/PolymarketPanel';

// 在 Dashboard 中添加
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <PolymarketPanel />
  {/* 其他组件 */}
</div>
```

## 常见问题

### Q: Polymarket 有 WebSocket 吗？

**A**: 目前 Polymarket CLOB API 主要是 REST API，没有公开的 WebSocket。我们使用轮询（每 5-10 秒）来获取实时数据。

### Q: 需要 API Key 吗？

**A**: 查看公开数据**不需要** API Key。但如果要进行交易，需要连接钱包。

### Q: 如何进行交易？

**A**: Polymarket 交易需要：
1. Polygon 钱包（MetaMask）
2. USDC 代币
3. 使用 Polymarket SDK 或直接调用智能合约

### Q: 数据更新频率？

**A**: 建议 5-10 秒轮询一次，避免过于频繁请求。

## 推荐的测试顺序

1. **第一步：API 测试**（5 分钟）
   ```powershell
   python test_polymarket.py
   ```

2. **第二步：创建数据适配器**（30 分钟）
   - 创建 `polymarket_adapter.py`
   - 实现基本的数据获取

3. **第三步：前端展示**（1 小时）
   - 创建 `PolymarketPanel` 组件
   - 集成到 Dashboard

4. **第四步：实时更新**（30 分钟）
   - 实现轮询机制
   - 添加 WebSocket 模拟

5. **第五步：Nautilus 集成**（后续）
   - 创建自定义 DataClient
   - 实现交易功能

## 参考资料

- [Polymarket 官方文档](https://docs.polymarket.com)
- [Polymarket CLOB API](https://docs.polymarket.com/#clob-api)
- [Polymarket SDK](https://github.com/Polymarket/py-clob-client)
- [Nautilus Trader 自定义适配器](https://nautilustrader.io/docs/latest/integrations/adapters.html)

## 下一步

完成 Polymarket 集成后，你可以：
1. 添加更多预测市场（Augur、Gnosis）
2. 实现 LLM 情感分析（分析市场问题）
3. 创建预测市场交易策略
4. 回测历史预测市场数据

---

**现在开始测试！运行 `python test_polymarket.py` 看看能否获取数据。**
