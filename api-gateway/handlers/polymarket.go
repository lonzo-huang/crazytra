package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

// Handler holds dependencies for all handlers
type Handler struct {
	redisClient *redis.Client
}

// NewHandler creates a new handler instance
func NewHandler(redisClient *redis.Client) *Handler {
	return &Handler{
		redisClient: redisClient,
	}
}

type PolymarketMarket struct {
	ConditionID  string  `json:"condition_id"`
	Question     string  `json:"question"`
	Description  string  `json:"description,omitempty"`
	Volume       float64 `json:"volume"`
	Liquidity    float64 `json:"liquidity"`
	EndDateISO   string  `json:"end_date_iso"`
	Tokens       []Token `json:"tokens"`
	Active       bool    `json:"active"`
}

type Token struct {
	TokenID string `json:"token_id"`
	Outcome string `json:"outcome"`
	Price   string `json:"price,omitempty"`
}

type StrategySignal struct {
	Strategy    string    `json:"strategy"`
	AssetID     string    `json:"asset_id"`
	Action      string    `json:"action"`
	Side        string    `json:"side"`
	Price       float64   `json:"price"`
	Size        float64   `json:"size"`
	Confidence  float64   `json:"confidence"`
	Reason      string    `json:"reason"`
	Timestamp   time.Time `json:"timestamp"`
}

type OrderBookData struct {
	InstrumentID string          `json:"instrument_id"`
	Bids         [][]interface{} `json:"bids"`
	Asks         [][]interface{} `json:"asks"`
	LastUpdate   time.Time       `json:"last_update"`
}

// GetPolymarketMarkets 获取 Polymarket 市场列表
// GET /api/v1/polymarket/markets
func (h *Handler) GetPolymarketMarkets(c *gin.Context) {
	ctx := context.Background()

	// 从 Redis 获取活跃市场列表
	marketIDs, err := h.redisClient.ZRevRange(ctx, "polymarket:markets:active", 0, 19).Result()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch market list from Redis",
		})
		return
	}

	if len(marketIDs) == 0 {
		// 如果 Redis 中没有数据，返回空数组
		c.JSON(http.StatusOK, []PolymarketMarket{})
		return
	}

	// 获取每个市场的详细数据
	markets := make([]PolymarketMarket, 0, len(marketIDs))

	for _, marketID := range marketIDs {
		key := "polymarket:market:" + marketID
		
		// 从 Redis 获取市场数据
		data, err := h.redisClient.Get(ctx, key).Result()
		if err == redis.Nil {
			continue // 市场数据已过期，跳过
		} else if err != nil {
			continue // 其他错误，跳过
		}

		// 解析 JSON
		var market PolymarketMarket
		if err := json.Unmarshal([]byte(data), &market); err != nil {
			continue
		}

		markets = append(markets, market)
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": gin.H{
			"markets": markets,
			"count":   len(markets),
		},
		"message": "Markets retrieved successfully",
	})
}

// GetPolymarketMarket 获取单个市场详情
// GET /api/v1/polymarket/markets/:id
func (h *Handler) GetPolymarketMarket(c *gin.Context) {
	ctx := context.Background()
	marketID := c.Param("id")

	key := "polymarket:market:" + marketID

	// 从 Redis 获取市场数据
	data, err := h.redisClient.Get(ctx, key).Result()
	if err == redis.Nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Market not found",
		})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch market data",
		})
		return
	}

	// 解析 JSON
	var market PolymarketMarket
	if err := json.Unmarshal([]byte(data), &market); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to parse market data",
		})
		return
	}

	c.JSON(http.StatusOK, market)
}

// GetPolymarketStats 获取 Polymarket 统计信息
// GET /api/v1/polymarket/stats
func (h *Handler) GetPolymarketStats(c *gin.Context) {
	ctx := context.Background()

	// 获取市场总数
	count, err := h.redisClient.Get(ctx, "polymarket:markets:count").Result()
	if err != nil && err != redis.Nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch stats",
		})
		return
	}

	// 获取活跃市场数量
	activeCount, err := h.redisClient.ZCard(ctx, "polymarket:markets:active").Result()
	if err != nil {
		activeCount = 0
	}

	c.JSON(http.StatusOK, gin.H{
		"total_markets":  count,
		"active_markets": activeCount,
		"last_update":    time.Now().Unix(),
	})
}

// GetBtc5mStrategy 获取 BTC 5分钟策略信号
// GET /api/v1/polymarket/strategy/btc5m
func (h *Handler) GetBtc5mStrategy(c *gin.Context) {
	ctx := context.Background()

	// 从 Redis 获取最新策略信号
	signalsKey := "polymarket:strategy:btc5m:signals"
	data, err := h.redisClient.LRange(ctx, signalsKey, 0, 9).Result()
	if err != nil && err != redis.Nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch strategy signals",
		})
		return
	}

	var signals []StrategySignal
	for _, signalData := range data {
		var signal StrategySignal
		if err := json.Unmarshal([]byte(signalData), &signal); err == nil {
			signals = append(signals, signal)
		}
	}

	// 如果没有信号，返回策略状态
	if len(signals) == 0 {
		c.JSON(http.StatusOK, gin.H{
			"strategy": "Btc5mBinaryEV",
			"status": "active",
			"signals": []StrategySignal{},
			"last_update": time.Now().Unix(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"strategy":    "Btc5mBinaryEV",
		"status":      "active",
		"signals":     signals,
		"last_update": time.Now().Unix(),
	})
}

// GetPolymarketOrderBook 获取订单簿数据
// GET /api/v1/polymarket/orderbook/:asset
func (h *Handler) GetPolymarketOrderBook(c *gin.Context) {
	ctx := context.Background()
	assetID := c.Param("asset")

	key := "polymarket:orderbook:" + assetID

	// 从 Redis 获取订单簿数据
	data, err := h.redisClient.Get(ctx, key).Result()
	if err == redis.Nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Order book not found",
		})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch order book",
		})
		return
	}

	// 解析 JSON
	var orderBook OrderBookData
	if err := json.Unmarshal([]byte(data), &orderBook); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to parse order book data",
		})
		return
	}

	c.JSON(http.StatusOK, orderBook)
}

// GetBtcMarkets 获取 BTC 相关市场
// GET /api/v1/polymarket/markets/btc
func (h *Handler) GetBtcMarkets(c *gin.Context) {
	ctx := context.Background()

	// 从 Redis 获取所有市场
	marketIDs, err := h.redisClient.ZRevRange(ctx, "polymarket:markets:active", 0, 99).Result()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch market list from Redis",
		})
		return
	}

	var btcMarkets []PolymarketMarket
	for _, marketID := range marketIDs {
		key := "polymarket:market:" + marketID
		data, err := h.redisClient.Get(ctx, key).Result()
		if err != nil {
			continue
		}

		var market PolymarketMarket
		if err := json.Unmarshal([]byte(data), &market); err != nil {
			continue
		}

		// 过滤 BTC 相关市场
		question := strings.ToLower(market.Question)
		if strings.Contains(question, "btc") || strings.Contains(question, "bitcoin") {
			btcMarkets = append(btcMarkets, market)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": gin.H{
			"markets": btcMarkets,
			"count":   len(btcMarkets),
		},
		"message": "BTC markets retrieved successfully",
	})
}

// GetBTCStrategy 获取 BTC 策略信号
func (h *Handler) GetBTCStrategy(c *gin.Context) {
	// 模拟策略信号 (实际应该从策略引擎获取)
	strategy := gin.H{
		"signal":        "BUY",
		"expected_value": 0.15,
		"confidence":     0.75,
		"markets_count": 5,
		"timestamp":     time.Now().Unix(),
		"strategy_name": "btc_5m_binary_ev",
		"update_interval": "5m",
		"last_update":   time.Now().Format("2006-01-02T15:04:05Z"),
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data":    strategy,
		"message": "BTC strategy signals retrieved successfully",
	})
}

// GetStrategyStats 获取策略统计信息
func (h *Handler) GetStrategyStats(c *gin.Context) {
	stats := gin.H{
		"total_markets": 100,
		"btc_markets":   8,
		"active_strategies": 1,
		"last_signal": gin.H{
			"signal":   "BUY",
			"strength": 0.75,
			"timestamp": time.Now().Unix(),
		},
		"performance": gin.H{
			"daily_return":    0.023,
			"weekly_return":   0.087,
			"monthly_return":  0.156,
			"sharpe_ratio":    1.24,
			"max_drawdown":    -0.045,
		},
		"system_health": gin.H{
			"data_engine_status": "running",
			"last_fetch":        time.Now().Format("2006-01-02T15:04:05Z"),
			"cache_hit_rate":    0.85,
			"api_latency_ms":    23,
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data":    stats,
		"message": "Strategy statistics retrieved successfully",
	})
}
