package main

import (
	"context"
	"encoding/json"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
	"github.com/shopspring/decimal"
	"go.uber.org/zap"
)

// ── Order state machine ────────────────────────────────────

type OrderStatus string

const (
	StatusPending       OrderStatus = "pending"
	StatusSubmitted     OrderStatus = "submitted"
	StatusPartialFilled OrderStatus = "partial_filled"
	StatusFilled        OrderStatus = "filled"
	StatusCancelled     OrderStatus = "cancelled"
	StatusRejected      OrderStatus = "rejected"
)

type Order struct {
	OrderID    string          `json:"order_id"`
	CommandID  string          `json:"command_id"`
	SignalID   string          `json:"signal_id"`
	Symbol     string          `json:"symbol"`
	Direction  string          `json:"direction"`
	Quantity   decimal.Decimal `json:"quantity"`
	OrderType  string          `json:"order_type"`
	Price      *decimal.Decimal `json:"price,omitempty"`
	StopLoss   *decimal.Decimal `json:"stop_loss,omitempty"`
	TakeProfit *decimal.Decimal `json:"take_profit,omitempty"`
	Status     OrderStatus     `json:"status"`
	FilledQty  decimal.Decimal `json:"filled_qty"`
	FilledPx   decimal.Decimal `json:"filled_px"`
	Fee        decimal.Decimal `json:"fee"`
	Mode       string          `json:"mode"`
	CreatedAt  int64           `json:"created_at"`
	UpdatedAt  int64           `json:"updated_at"`
}

type OrderEvent struct {
	EventID   string      `json:"event_id"`
	OrderID   string      `json:"order_id"`
	SignalID  string      `json:"signal_id"`
	Symbol    string      `json:"symbol"`
	Kind      OrderStatus `json:"kind"`
	FilledQty decimal.Decimal `json:"filled_qty"`
	FilledPx  decimal.Decimal `json:"filled_px"`
	Fee       decimal.Decimal `json:"fee"`
	Timestamp int64       `json:"timestamp"`
}

// ── OMS (Order Management System) ─────────────────────────

type OMS struct {
	orders map[string]*Order
	mu     sync.RWMutex
	logger *zap.Logger
}

func NewOMS(logger *zap.Logger) *OMS {
	return &OMS{orders: make(map[string]*Order), logger: logger}
}

func (o *OMS) Create(cmd map[string]any) *Order {
	cmdJSON, _ := json.Marshal(cmd)
	var cmdObj struct {
		CommandID  string           `json:"command_id"`
		SignalID   string           `json:"signal_id"`
		Symbol     string           `json:"symbol"`
		Direction  string           `json:"direction"`
		Quantity   decimal.Decimal  `json:"quantity"`
		OrderType  string           `json:"order_type"`
		Price      *decimal.Decimal `json:"price"`
		StopLoss   *decimal.Decimal `json:"stop_loss"`
		TakeProfit *decimal.Decimal `json:"take_profit"`
		Mode       string           `json:"mode"`
	}
	_ = json.Unmarshal(cmdJSON, &cmdObj)

	order := &Order{
		OrderID:    uuid.New().String(),
		CommandID:  cmdObj.CommandID,
		SignalID:   cmdObj.SignalID,
		Symbol:     cmdObj.Symbol,
		Direction:  cmdObj.Direction,
		Quantity:   cmdObj.Quantity,
		OrderType:  cmdObj.OrderType,
		Price:      cmdObj.Price,
		StopLoss:   cmdObj.StopLoss,
		TakeProfit: cmdObj.TakeProfit,
		Status:     StatusPending,
		Mode:       cmdObj.Mode,
		CreatedAt:  time.Now().UnixNano(),
		UpdatedAt:  time.Now().UnixNano(),
	}
	o.mu.Lock()
	o.orders[order.OrderID] = order
	o.mu.Unlock()
	return order
}

func (o *OMS) Transition(orderID string, status OrderStatus,
	qty, px, fee decimal.Decimal) *Order {
	o.mu.Lock()
	defer o.mu.Unlock()
	ord := o.orders[orderID]
	if ord == nil {
		return nil
	}
	ord.Status    = status
	ord.FilledQty = qty
	ord.FilledPx  = px
	ord.Fee       = fee
	ord.UpdatedAt = time.Now().UnixNano()
	return ord
}

func (o *OMS) Get(orderID string) *Order {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return o.orders[orderID]
}

func (o *OMS) AllOrders() []*Order {
	o.mu.RLock()
	defer o.mu.RUnlock()
	out := make([]*Order, 0, len(o.orders))
	for _, v := range o.orders {
		out = append(out, v)
	}
	return out
}

// ── Paper trading broker ───────────────────────────────────

type PaperConfig struct {
	MakerFee    decimal.Decimal
	TakerFee    decimal.Decimal
	SlippageBps decimal.Decimal
	FillDelayMs int // simulate exchange latency
}

var DefaultPaperConfig = PaperConfig{
	MakerFee:    decimal.NewFromFloat(0.0002),
	TakerFee:    decimal.NewFromFloat(0.0005),
	SlippageBps: decimal.NewFromFloat(1.0),
	FillDelayMs: 50,
}

type PaperBroker struct {
	cfg      PaperConfig
	cash     decimal.Decimal
	positions map[string]decimal.Decimal
	mu       sync.Mutex
	logger   *zap.Logger
}

func NewPaperBroker(initialCash decimal.Decimal, cfg PaperConfig, logger *zap.Logger) *PaperBroker {
	return &PaperBroker{
		cfg:       cfg,
		cash:      initialCash,
		positions: make(map[string]decimal.Decimal),
		logger:    logger,
	}
}

func (b *PaperBroker) Execute(order *Order, midPrice decimal.Decimal) (*OrderEvent, error) {
	// Simulate exchange latency
	jitter := time.Duration(rand.Intn(b.cfg.FillDelayMs)) * time.Millisecond
	time.Sleep(jitter)

	b.mu.Lock()
	defer b.mu.Unlock()

	// Apply slippage
	slip := midPrice.Mul(b.cfg.SlippageBps).Div(decimal.NewFromInt(10000))
	var fillPx decimal.Decimal
	if order.Direction == "long" {
		fillPx = midPrice.Add(slip)
	} else {
		fillPx = midPrice.Sub(slip)
	}

	qty := order.Quantity.Div(fillPx) // convert notional → quantity
	fee := qty.Mul(fillPx).Mul(b.cfg.TakerFee)

	switch order.Direction {
	case "long":
		cost := qty.Mul(fillPx).Add(fee)
		if cost.GreaterThan(b.cash) {
			qty   = b.cash.Mul(decimal.NewFromFloat(0.99)).Div(fillPx.Mul(decimal.NewFromFloat(1.0005)))
			fee   = qty.Mul(fillPx).Mul(b.cfg.TakerFee)
			cost  = qty.Mul(fillPx).Add(fee)
		}
		if qty.LessThanOrEqual(decimal.Zero) {
			return nil, nil
		}
		b.cash = b.cash.Sub(cost)
		b.positions[order.Symbol] = b.positions[order.Symbol].Add(qty)

	case "short", "exit":
		pos := b.positions[order.Symbol]
		if pos.LessThanOrEqual(decimal.Zero) {
			return nil, nil
		}
		if qty.GreaterThan(pos) {
			qty = pos
		}
		revenue := qty.Mul(fillPx)
		fee      = revenue.Mul(b.cfg.TakerFee)
		b.cash   = b.cash.Add(revenue.Sub(fee))
		b.positions[order.Symbol] = pos.Sub(qty)
	}

	b.logger.Info("paper_fill",
		zap.String("symbol", order.Symbol),
		zap.String("dir", order.Direction),
		zap.String("qty", qty.StringFixed(6)),
		zap.String("px", fillPx.StringFixed(4)),
		zap.String("fee", fee.StringFixed(4)),
		zap.String("cash", b.cash.StringFixed(2)))

	return &OrderEvent{
		EventID:   uuid.New().String(),
		OrderID:   order.OrderID,
		SignalID:  order.SignalID,
		Symbol:    order.Symbol,
		Kind:      StatusFilled,
		FilledQty: qty,
		FilledPx:  fillPx,
		Fee:       fee,
		Timestamp: time.Now().UnixNano(),
	}, nil
}

func (b *PaperBroker) NAV(prices map[string]decimal.Decimal) decimal.Decimal {
	b.mu.Lock()
	defer b.mu.Unlock()
	nav := b.cash
	for sym, qty := range b.positions {
		if px, ok := prices[sym]; ok {
			nav = nav.Add(qty.Mul(px))
		}
	}
	return nav
}

// ── Price cache (latest bid/ask from Redis) ────────────────

type PriceCache struct {
	prices map[string]decimal.Decimal
	mu     sync.RWMutex
}

func (pc *PriceCache) Set(symbol string, mid decimal.Decimal) {
	pc.mu.Lock()
	pc.prices[symbol] = mid
	pc.mu.Unlock()
}

func (pc *PriceCache) Get(symbol string) (decimal.Decimal, bool) {
	pc.mu.RLock()
	defer pc.mu.RUnlock()
	v, ok := pc.prices[symbol]
	return v, ok
}

// ── Main service ───────────────────────────────────────────

func main() {
	_ = godotenv.Load()
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	redisURL := getenv("REDIS_URL", "redis://localhost:6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisURL[8:]})

	initialCash, _ := decimal.NewFromString(getenv("PAPER_INITIAL_CASH", "100000"))
	mode := getenv("TRADING_MODE", "paper")

	oms := NewOMS(logger)

	// 根据模式创建不同的 broker
	var broker interface {
		Execute(order *Order, midPrice decimal.Decimal) (*OrderEvent, error)
	}

	// 创建 Polymarket 适配器（实盘模式）
	var polymarketAdapter *PolymarketAdapter
	if mode == "live" {
		polyKey := getenv("POLYMARKET_API_KEY", "")
		polySecret := getenv("POLYMARKET_API_SECRET", "")
		walletAddr := getenv("WALLET_ADDRESS", "")
		polymarketAdapter = NewPolymarketAdapter(polyKey, polySecret, walletAddr, logger)
	}

	// 创建纸面交易 broker（用于纸面模式和测试）
	paperBroker := NewPaperBroker(initialCash, DefaultPaperConfig, logger)
	polyPaperBroker := NewPolymarketPaperBroker(initialCash, DefaultPaperConfig, logger)

	prices := &PriceCache{prices: make(map[string]decimal.Decimal)}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	logger.Info("trading_layer_started", zap.String("mode", mode),
		zap.String("cash", initialCash.String()))

	group := "trading-cg"
	_ = rdb.XGroupCreateMkStream(ctx, "order.command", group, "$").Err()
	_ = rdb.XGroupCreateMkStream(ctx, "market.tick.binance.btcusdt", group, "$").Err()
	_ = rdb.XGroupCreateMkStream(ctx, "market.tick.binance.ethusdt", group, "$").Err()
	// 添加 Polymarket tick 流
	_ = rdb.XGroupCreateMkStream(ctx, "market.tick.polymarket.will-btc-hit-100k-2024-USDC", group, "$").Err()

	// Tick listener → price cache
	go func() {
		// 添加 Polymarket 到监听列表
		tickTopics := []string{
			"market.tick.binance.btcusdt",
			"market.tick.binance.ethusdt",
			"market.tick.polymarket.will-btc-hit-100k-2024-USDC", // Polymarket BTC 预测市场
		}
		streams := make([]string, 0, len(tickTopics)*2)
		for _, t := range tickTopics {
			streams = append(streams, t, ">")
		}
		for {
			entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group: group, Consumer: "trading-price-1",
				Streams: streams, Count: 100, Block: 50 * time.Millisecond,
			}).Result()
			if err != nil {
				time.Sleep(50 * time.Millisecond)
				continue
			}
			var ackArgs []string
			for _, stream := range entries {
				for _, msg := range stream.Messages {
					// 检查是否是 Polymarket 市场
					isPolymarket := false
					for _, topic := range tickTopics {
						if topic == stream.Stream {
							isPolymarket = true
							break
						}
					}
					if !isPolymarket {
						continue
					}

					if raw, ok := msg.Values["data"].(string); ok {
						var tick struct {
							Symbol string `json:"symbol"`
							Bid    string `json:"bid"`
							Ask    string `json:"ask"`
							Exchange string `json:"exchange"`
						}
						if err := json.Unmarshal([]byte(raw), &tick); err == nil {
							bid, _ := decimal.NewFromString(tick.Bid)
							ask, _ := decimal.NewFromString(tick.Ask)
							mid := bid.Add(ask).Div(decimal.NewFromInt(2))
							if !mid.IsZero() {
								prices.Set(tick.Symbol, mid)
								logger.Debug("price_updated",
									zap.String("symbol", tick.Symbol),
									zap.String("exchange", tick.Exchange),
									zap.String("mid", mid.String()))
							}
						}
					}
					ackArgs = append(ackArgs, msg.ID)
				}
			}
			for _, t := range tickTopics {
				if len(ackArgs) > 0 {
					_ = rdb.XAck(ctx, t, group, ackArgs...).Err()
				}
			}
		}
	}()

	// Order command consumer
	go func() {
		for {
			entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group: group, Consumer: "trading-exec-1",
				Streams: []string{"order.command", ">"},
				Count:   10, Block: 100 * time.Millisecond,
			}).Result()
			if err != nil || len(entries) == 0 {
				time.Sleep(10 * time.Millisecond)
				continue
			}

			var ackIDs []string
			for _, stream := range entries {
				for _, msg := range stream.Messages {
					raw := msg.Values["data"]
					if raw == nil {
						ackIDs = append(ackIDs, msg.ID)
						continue
					}
					var cmdMap map[string]any
					if err := json.Unmarshal([]byte(raw.(string)), &cmdMap); err != nil {
						ackIDs = append(ackIDs, msg.ID)
						continue
					}

					order := oms.Create(cmdMap)
					sym   := order.Symbol
					mid, ok := prices.Get(sym)
					if !ok {
						logger.Warn("no_price_for_symbol", zap.String("symbol", sym))
						ackIDs = append(ackIDs, msg.ID)
						continue
					}

					var event *OrderEvent
					var execErr error

					if isPolymarketSymbol(order.Symbol) {
						// Polymarket 特殊处理
						// 使用预测市场的 yes 价格（mid 已经是概率价格 0~1）
						if mode == "paper" {
							event, execErr = polyPaperBroker.ExecutePredictionMarket(order, mid)
						} else if mode == "live" && polymarketAdapter != nil {
							event, execErr = polymarketAdapter.SubmitOrder(order)
						}
					} else {
						// 传统交易所
						if mode == "paper" {
							event, execErr = paperBroker.Execute(order, mid)
						} else {
							logger.Warn("live trading not implemented for this exchange",
								zap.String("symbol", order.Symbol))
							execErr = fmt.Errorf("live trading not supported")
						}
					}

					if execErr != nil || event == nil {
						logger.Error("execution_failed",
							zap.Error(execErr),
							zap.String("symbol", order.Symbol))
						oms.Transition(order.OrderID, StatusRejected,
							decimal.Zero, decimal.Zero, decimal.Zero)
						ackIDs = append(ackIDs, msg.ID)
						continue
					}

					oms.Transition(order.OrderID, event.Kind,
						event.FilledQty, event.FilledPx, event.Fee)

					evJSON, _ := json.Marshal(event)
					_ = rdb.XAdd(ctx, &redis.XAddArgs{
						Stream: "order.event",
						MaxLen: 50000, Approx: true,
						Values: map[string]any{
							"order_id": event.OrderID,
							"symbol":   event.Symbol,
							"kind":     string(event.Kind),
							"data":     string(evJSON),
						},
					}).Err()

					ackIDs = append(ackIDs, msg.ID)
				}
			}
			if len(ackIDs) > 0 {
				_ = rdb.XAck(ctx, "order.command", group, ackIDs...).Err()
			}
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	logger.Info("trading_layer_stopping")
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// isPolymarketSymbol 判断是否是 Polymarket 市场
// Polymarket symbol 格式包含冒号分隔的 condition_id 和 asset_id
func isPolymarketSymbol(symbol string) bool {
	// 检查是否包含多个冒号（Polymarket 格式：condition_id:asset_id:slug）
	parts := splitSymbol(symbol)
	return len(parts) >= 2 && len(parts[0]) > 10 // condition_id 通常是较长的 hex 字符串
}

// splitSymbol 分割 symbol
func splitSymbol(s string) []string {
	var parts []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == ':' {
			parts = append(parts, s[start:i])
			start = i + 1
		}
	}
	parts = append(parts, s[start:])
	return parts
}
