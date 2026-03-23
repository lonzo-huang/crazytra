package main

import (
	"context"
	"encoding/json"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
	"github.com/shopspring/decimal"
	"go.uber.org/zap"
)

// ── Data models ────────────────────────────────────────────

type Signal struct {
	SignalID    string          `json:"signal_id"`
	StrategyID string          `json:"strategy_id"`
	Symbol     string          `json:"symbol"`
	Direction  string          `json:"direction"` // long|short|exit|hold
	Strength   float64         `json:"strength"`
	Confidence float64         `json:"confidence"`
	StopLoss   *decimal.Decimal `json:"stop_loss,omitempty"`
	TakeProfit *decimal.Decimal `json:"take_profit,omitempty"`
	TargetSize *decimal.Decimal `json:"target_size,omitempty"`
	TimestampNs int64           `json:"timestamp_ns"`
	TtlMs      int             `json:"ttl_ms"`
	Reason     string          `json:"reason"`
}

type OrderCommand struct {
	CommandID  string           `json:"command_id"`
	SignalID   string           `json:"signal_id"`
	Symbol     string           `json:"symbol"`
	Direction  string           `json:"direction"`
	Quantity   decimal.Decimal  `json:"quantity"`
	OrderType  string           `json:"order_type"` // market|limit
	Price      *decimal.Decimal `json:"price,omitempty"`
	StopLoss   *decimal.Decimal `json:"stop_loss,omitempty"`
	TakeProfit *decimal.Decimal `json:"take_profit,omitempty"`
	Mode       string           `json:"mode"` // paper|live
	CreatedAt  int64            `json:"created_at"`
}

type RiskAlert struct {
	AlertID   string `json:"alert_id"`
	Kind      string `json:"kind"` // position_limit|daily_loss|drawdown|circuit_breaker
	Symbol    string `json:"symbol"`
	Message   string `json:"message"`
	Severity  string `json:"severity"` // warn|critical
	Timestamp int64  `json:"timestamp"`
}

// ── Circuit breaker ────────────────────────────────────────

const (
	cbClosed   int32 = 0
	cbOpen     int32 = 1
	cbHalfOpen int32 = 2
)

type CircuitBreaker struct {
	state        atomic.Int32
	failures     atomic.Int64
	lastFailTime atomic.Int64
	threshold    int64
	resetMs      int64
}

func NewCircuitBreaker(threshold int64, resetMs int64) *CircuitBreaker {
	cb := &CircuitBreaker{threshold: threshold, resetMs: resetMs}
	cb.state.Store(cbClosed)
	return cb
}

func (cb *CircuitBreaker) Allow() bool {
	switch cb.state.Load() {
	case cbClosed:
		return true
	case cbOpen:
		elapsed := time.Now().UnixMilli() - cb.lastFailTime.Load()
		if elapsed > cb.resetMs {
			cb.state.CompareAndSwap(cbOpen, cbHalfOpen)
			return true
		}
		return false
	default: // half-open
		return true
	}
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.failures.Store(0)
	cb.state.Store(cbClosed)
}

func (cb *CircuitBreaker) RecordFailure() {
	n := cb.failures.Add(1)
	cb.lastFailTime.Store(time.Now().UnixMilli())
	if n >= cb.threshold {
		cb.state.Store(cbOpen)
	}
}

func (cb *CircuitBreaker) IsOpen() bool { return cb.state.Load() == cbOpen }

// ── Position tracker ───────────────────────────────────────

type Position struct {
	mu         sync.RWMutex
	Symbol     string
	Quantity   decimal.Decimal
	AvgEntry   decimal.Decimal
	UnrealPnL  decimal.Decimal
	RealPnL    decimal.Decimal
	TradeCount int
}

func (p *Position) Update(qty, px decimal.Decimal) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.Quantity.IsZero() {
		p.AvgEntry = px
		p.Quantity = qty
		return
	}
	// weighted avg entry
	totalQty := p.Quantity.Add(qty)
	if !totalQty.IsZero() {
		p.AvgEntry = p.Quantity.Mul(p.AvgEntry).Add(qty.Mul(px)).Div(totalQty)
	}
	p.Quantity = totalQty
	p.TradeCount++
}

func (p *Position) MarkToMarket(midPx decimal.Decimal) decimal.Decimal {
	p.mu.RLock()
	defer p.mu.RUnlock()
	if p.Quantity.IsZero() || p.AvgEntry.IsZero() {
		return decimal.Zero
	}
	return midPx.Sub(p.AvgEntry).Mul(p.Quantity)
}

// ── Risk engine ────────────────────────────────────────────

type RiskConfig struct {
	MaxPositionSize decimal.Decimal // fraction of NAV per symbol
	MaxDailyLoss    decimal.Decimal // fraction of initial NAV
	MaxDrawdown     decimal.Decimal // fraction of peak NAV
	TradingMode     string          // paper | live
	InitialNAV      decimal.Decimal
}

type RiskEngine struct {
	cfg        RiskConfig
	cb         *CircuitBreaker
	positions  map[string]*Position
	mu         sync.RWMutex
	peakNAV    decimal.Decimal
	dailyLoss  decimal.Decimal
	dayStart   time.Time
	logger     *zap.Logger
}

func NewRiskEngine(cfg RiskConfig, logger *zap.Logger) *RiskEngine {
	return &RiskEngine{
		cfg:       cfg,
		cb:        NewCircuitBreaker(5, 60_000),
		positions: make(map[string]*Position),
		peakNAV:   cfg.InitialNAV,
		dayStart:  time.Now().UTC().Truncate(24 * time.Hour),
		logger:    logger,
	}
}

func (re *RiskEngine) Validate(sig *Signal, currentNAV decimal.Decimal) ([]RiskAlert, bool) {
	var alerts []RiskAlert

	// Reset daily loss counter at midnight
	if time.Now().UTC().After(re.dayStart.Add(24 * time.Hour)) {
		re.dailyLoss = decimal.Zero
		re.dayStart  = time.Now().UTC().Truncate(24 * time.Hour)
	}

	// Circuit breaker check
	if !re.cb.Allow() {
		alerts = append(alerts, RiskAlert{
			Kind: "circuit_breaker", Symbol: sig.Symbol,
			Message:  "Circuit breaker OPEN — all trading halted",
			Severity: "critical", Timestamp: time.Now().UnixNano(),
		})
		return alerts, false
	}

	// Daily loss limit
	dailyLossFrac := re.dailyLoss.Div(re.cfg.InitialNAV).Abs()
	if dailyLossFrac.GreaterThan(re.cfg.MaxDailyLoss) {
		re.cb.RecordFailure()
		alerts = append(alerts, RiskAlert{
			Kind: "daily_loss", Symbol: sig.Symbol,
			Message:  "Daily loss limit exceeded: " + dailyLossFrac.StringFixed(4),
			Severity: "critical", Timestamp: time.Now().UnixNano(),
		})
		return alerts, false
	}

	// Drawdown check
	if currentNAV.GreaterThan(re.peakNAV) {
		re.peakNAV = currentNAV
	}
	drawdown := re.peakNAV.Sub(currentNAV).Div(re.peakNAV)
	if drawdown.GreaterThan(re.cfg.MaxDrawdown) {
		alerts = append(alerts, RiskAlert{
			Kind: "drawdown", Symbol: sig.Symbol,
			Message:  "Max drawdown exceeded: " + drawdown.StringFixed(4),
			Severity: "critical", Timestamp: time.Now().UnixNano(),
		})
		return alerts, false
	}

	// Position size check
	re.mu.RLock()
	pos := re.positions[sig.Symbol]
	re.mu.RUnlock()
	if pos != nil {
		posValue := pos.AvgEntry.Mul(pos.Quantity).Abs()
		posFrac   := posValue.Div(currentNAV)
		if posFrac.GreaterThan(re.cfg.MaxPositionSize) {
			alerts = append(alerts, RiskAlert{
				Kind: "position_limit", Symbol: sig.Symbol,
				Message:  "Position limit reached: " + posFrac.StringFixed(4),
				Severity: "warn", Timestamp: time.Now().UnixNano(),
			})
			// Warn but allow exit signals
			if sig.Direction != "exit" {
				return alerts, false
			}
		}
	}

	return alerts, true
}

func (re *RiskEngine) SizeOrder(sig *Signal, currentNAV decimal.Decimal) decimal.Decimal {
	// Base size: signal strength × max position size × NAV
	strength := decimal.NewFromFloat(sig.Strength)
	maxPos   := re.cfg.MaxPositionSize
	notional := strength.Mul(maxPos).Mul(currentNAV)
	return notional
}

func (re *RiskEngine) RecordFill(symbol string, qty, px, pnl decimal.Decimal) {
	re.mu.Lock()
	if re.positions[symbol] == nil {
		re.positions[symbol] = &Position{Symbol: symbol}
	}
	re.positions[symbol].Update(qty, px)
	re.mu.Unlock()

	if pnl.IsNegative() {
		re.dailyLoss = re.dailyLoss.Add(pnl)
	}
}

// ── Main service ───────────────────────────────────────────

func main() {
	_ = godotenv.Load()

	logger, _ := zap.NewProduction()
	defer logger.Sync()

	redisURL := getenv("REDIS_URL", "redis://localhost:6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisURL[8:]})

	nav, _ := decimal.NewFromString(getenv("PAPER_INITIAL_CASH", "100000"))
	cfg := RiskConfig{
		MaxPositionSize: mustDecimal(getenv("MAX_POSITION_SIZE", "0.2")),
		MaxDailyLoss:    mustDecimal(getenv("MAX_DAILY_LOSS", "0.05")),
		MaxDrawdown:     mustDecimal(getenv("MAX_DRAWDOWN", "0.15")),
		TradingMode:     getenv("TRADING_MODE", "paper"),
		InitialNAV:      nav,
	}

	engine := NewRiskEngine(cfg, logger)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	logger.Info("risk_engine_started",
		zap.String("mode", cfg.TradingMode),
		zap.String("nav", nav.String()))

	// Create consumer group
	group := "risk-cg"
	_ = rdb.XGroupCreateMkStream(ctx, "strategy.signal", group, "$").Err()
	_ = rdb.XGroupCreateMkStream(ctx, "order.event", group, "$").Err()

	go func() {
		for {
			entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    group,
				Consumer: "risk-1",
				Streams:  []string{"strategy.signal", ">"},
				Count:    20,
				Block:    200 * time.Millisecond,
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
					var sig Signal
					if err := json.Unmarshal([]byte(raw.(string)), &sig); err != nil {
						ackIDs = append(ackIDs, msg.ID)
						continue
					}

					alerts, ok := engine.Validate(&sig, nav)

					// Publish alerts
					for _, alert := range alerts {
						alertJSON, _ := json.Marshal(alert)
						_ = rdb.XAdd(ctx, &redis.XAddArgs{
							Stream: "risk.alert",
							MaxLen: 5000, Approx: true,
							Values: map[string]any{
								"kind": alert.Kind, "severity": alert.Severity,
								"data": string(alertJSON),
							},
						}).Err()
						logger.Warn("risk_alert",
							zap.String("kind", alert.Kind),
							zap.String("symbol", alert.Symbol),
							zap.String("msg", alert.Message))
					}

					if ok {
						notional := engine.SizeOrder(&sig, nav)
						cmd := OrderCommand{
							CommandID: sig.SignalID + "-cmd",
							SignalID:  sig.SignalID,
							Symbol:    sig.Symbol,
							Direction: sig.Direction,
							Quantity:  notional,
							OrderType: "market",
							StopLoss:  sig.StopLoss,
							TakeProfit: sig.TakeProfit,
							Mode:      cfg.TradingMode,
							CreatedAt: time.Now().UnixNano(),
						}
						cmdJSON, _ := json.Marshal(cmd)
						_ = rdb.XAdd(ctx, &redis.XAddArgs{
							Stream: "order.command",
							MaxLen: 10000, Approx: true,
							Values: map[string]any{
								"symbol": cmd.Symbol,
								"dir":    cmd.Direction,
								"data":   string(cmdJSON),
							},
						}).Err()
						logger.Info("order_approved",
							zap.String("symbol", sig.Symbol),
							zap.String("dir", sig.Direction),
							zap.String("notional", notional.StringFixed(2)))
					}
					ackIDs = append(ackIDs, msg.ID)
				}
			}
			if len(ackIDs) > 0 {
				_ = rdb.XAck(ctx, "strategy.signal", group, ackIDs...).Err()
			}
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	logger.Info("risk_engine_stopping")
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func mustDecimal(s string) decimal.Decimal {
	d, _ := decimal.NewFromString(s)
	return d
}

func mustInt(s string) int64 {
	n, _ := strconv.ParseInt(s, 10, 64)
	return n
}
