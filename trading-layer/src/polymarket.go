// Polymarket 交易适配器
// 支持 CLOB API 实盘交易

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"go.uber.org/zap"
)

const (
	CLOB_API_BASE = "https://clob.polymarket.com"
	POLYGON_RPC   = "https://polygon-rpc.com"
)

// PolymarketAdapter CLOB API 适配器
type PolymarketAdapter struct {
	apiKey      string
	apiSecret   string
	walletAddr  string
	httpClient  *http.Client
	logger      *zap.Logger
}

func NewPolymarketAdapter(apiKey, apiSecret, walletAddr string, logger *zap.Logger) *PolymarketAdapter {
	return &PolymarketAdapter{
		apiKey:     apiKey,
		apiSecret:  apiSecret,
		walletAddr: walletAddr,
		httpClient: &http.Client{Timeout: 30 * time.Second},
		logger:     logger,
	}
}

// CLOBOrder CLOB 订单结构
type CLOBOrder struct {
	OrderID   string          `json:"orderId,omitempty"`
	MarketID  string          `json:"market"`
	AssetID   string          `json:"assetId"`
	Side      string          `json:"side"`      // "buy" or "sell"
	Price     decimal.Decimal `json:"price"`     // 0.00 ~ 1.00
	Size      decimal.Decimal `json:"size"`      // USDC 金额
	FeeRateBps int            `json:"feeRateBps"`
}

// CLOBResponse API 响应
type CLOBResponse struct {
	Success   bool   `json:"success"`
	OrderID   string `json:"orderId"`
	Error     string `json:"error,omitempty"`
	Status    string `json:"status"`
}

// SubmitOrder 提交订单到 CLOB
func (a *PolymarketAdapter) SubmitOrder(order *Order) (*OrderEvent, error) {
	// 解析 symbol 获取 condition_id 和 asset_id
	// 格式: condition_id:asset_id:slug
	conditionID, assetID, err := parsePolymarketSymbol(order.Symbol)
	if err != nil {
		return nil, fmt.Errorf("invalid polymarket symbol: %w", err)
	}

	// 构建 CLOB 订单
	clobOrder := CLOBOrder{
		MarketID:  conditionID,
		AssetID:   assetID,
		Side:      mapDirection(order.Direction),
		Price:     *order.Price,
		Size:      order.Quantity,
		FeeRateBps: 0, // 使用默认费率
	}

	a.logger.Info("submitting_polymarket_order",
		zap.String("market", conditionID),
		zap.String("side", clobOrder.Side),
		zap.String("price", clobOrder.Price.String()),
		zap.String("size", clobOrder.Size.String()))

	// 提交到 CLOB API
	resp, err := a.postOrder(clobOrder)
	if err != nil {
		return nil, fmt.Errorf("clob api error: %w", err)
	}

	if !resp.Success {
		return nil, fmt.Errorf("order rejected: %s", resp.Error)
	}

	// 更新订单状态
	event := &OrderEvent{
		EventID:   uuid.New().String(),
		OrderID:   order.OrderID,
		SignalID:  order.SignalID,
		Symbol:    order.Symbol,
		Kind:      StatusSubmitted,
		FilledQty: decimal.Zero,
		FilledPx:  *order.Price,
		Fee:       decimal.Zero,
		Timestamp: time.Now().UnixNano(),
	}

	// 注意：Polymarket 是限价单模式，需要等待撮合
	// 这里返回 submitted 状态，后续通过 WebSocket/轮询获取成交结果

	return event, nil
}

// CancelOrder 取消订单
func (a *PolymarketAdapter) CancelOrder(orderID string) error {
	url := fmt.Sprintf("%s/order/%s", CLOB_API_BASE, orderID)

	req, err := http.NewRequest("DELETE", url, nil)
	if err != nil {
		return err
	}

	if a.apiKey != "" {
		req.Header.Set("POLYMARKET_API_KEY", a.apiKey)
	}

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("cancel failed: %s", resp.Status)
	}

	return nil
}

// GetOrder 查询订单状态
func (a *PolymarketAdapter) GetOrder(orderID string) (*OrderStatus, error) {
	url := fmt.Sprintf("%s/order/%s", CLOB_API_BASE, orderID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	if a.apiKey != "" {
		req.Header.Set("POLYMARKET_API_KEY", a.apiKey)
	}

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("get order failed: %s", resp.Status)
	}

	var result struct {
		OrderID string `json:"orderId"`
		Status  string `json:"status"`
		Size    string `json:"size"`
		Price   string `json:"price"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	status := mapCLOBStatus(result.Status)
	return &status, nil
}

// postOrder 发送订单到 CLOB API
func (a *PolymarketAdapter) postOrder(order CLOBOrder) (*CLOBResponse, error) {
	payload, err := json.Marshal(order)
	if err != nil {
		return nil, err
	}

	url := CLOB_API_BASE + "/order"
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(payload))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	if a.apiKey != "" {
		req.Header.Set("POLYMARKET_API_KEY", a.apiKey)
	}

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result CLOBResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return &result, nil
}

// mapDirection 映射方向
func mapDirection(dir string) string {
	switch dir {
	case "long", "buy":
		return "buy"
	case "short", "sell", "exit":
		return "sell"
	default:
		return "buy"
	}
}

// mapCLOBStatus 映射 CLOB 状态
func mapCLOBStatus(status string) OrderStatus {
	switch status {
	case "PENDING":
		return StatusPending
	case "OPEN":
		return StatusSubmitted
	case "PARTIALLY_FILLED":
		return StatusPartialFilled
	case "FILLED":
		return StatusFilled
	case "CANCELLED":
		return StatusCancelled
	default:
		return StatusPending
	}
}

// parsePolymarketSymbol 解析 symbol
// 格式: condition_id:asset_id:slug
func parsePolymarketSymbol(symbol string) (conditionID, assetID string, err error) {
	parts := splitSymbol(symbol)
	if len(parts) < 2 {
		return "", "", fmt.Errorf("invalid symbol format, expected condition_id:asset_id:slug")
	}
	return parts[0], parts[1], nil
}

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

// PolymarketPaperBroker Polymarket 纸面交易模拟器
// 模拟预测市场的特殊规则
type PolymarketPaperBroker struct {
	*PaperBroker
	logger *zap.Logger
}

func NewPolymarketPaperBroker(initialCash decimal.Decimal, cfg PaperConfig, logger *zap.Logger) *PolymarketPaperBroker {
	return &PolymarketPaperBroker{
		PaperBroker: NewPaperBroker(initialCash, cfg, logger),
		logger:      logger,
	}
}

// ExecutePredictionMarket 执行预测市场交易
// 预测市场的特殊之处：价格 = 概率 (0~1)
func (b *PolymarketPaperBroker) ExecutePredictionMarket(order *Order, yesPrice decimal.Decimal) (*OrderEvent, error) {
	// 模拟延迟
	jitter := time.Duration(rand.Intn(b.cfg.FillDelayMs)) * time.Millisecond
	time.Sleep(jitter)

	b.mu.Lock()
	defer b.mu.Unlock()

	// 预测市场滑点（按市场深度调整）
	slipBps := b.cfg.SlippageBps
	slip := yesPrice.Mul(slipBps).Div(decimal.NewFromInt(10000))

	var fillPx decimal.Decimal
	if order.Direction == "long" || order.Direction == "buy" {
		fillPx = yesPrice.Add(slip) // 买入 Yes = 支付更高价格
	} else {
		fillPx = yesPrice.Sub(slip) // 卖出 Yes = 获得更低价格
	}

	// 确保价格在 [0, 1] 范围内
	if fillPx.GreaterThan(decimal.NewFromInt(1)) {
		fillPx = decimal.NewFromInt(1)
	}
	if fillPx.LessThan(decimal.Zero) {
		fillPx = decimal.Zero
	}

	// 计算 shares 数量
	// 投入金额 / 价格 = 获得的 shares
	shares := order.Quantity.Div(fillPx)

	// 手续费 (Polymarket 约 0-2%)
	feeRate := decimal.NewFromFloat(0.001) // 0.1%
	fee := order.Quantity.Mul(feeRate)

	totalCost := order.Quantity.Add(fee)

	b.logger.Info("paper_fill_polymarket",
		zap.String("symbol", order.Symbol),
		zap.String("dir", order.Direction),
		zap.String("yes_price", yesPrice.String()),
		zap.String("fill_price", fillPx.String()),
		zap.String("shares", shares.StringFixed(4)),
		zap.String("notional", order.Quantity.StringFixed(2)),
		zap.String("fee", fee.StringFixed(4)),
		zap.String("cash", b.cash.StringFixed(2)))

	switch order.Direction {
	case "long", "buy":
		if totalCost.GreaterThan(b.cash) {
			// 资金不足，调整数量
			maxNotional := b.cash.Mul(decimal.NewFromFloat(0.99))
			shares = maxNotional.Div(fillPx)
			order.Quantity = shares.Mul(fillPx)
			fee = order.Quantity.Mul(feeRate)
			totalCost = order.Quantity.Add(fee)
		}

		if shares.LessThanOrEqual(decimal.Zero) {
			return nil, nil
		}

		b.cash = b.cash.Sub(totalCost)
		b.positions[order.Symbol] = b.positions[order.Symbol].Add(shares)

	case "short", "sell", "exit":
		pos := b.positions[order.Symbol]
		if pos.LessThanOrEqual(decimal.Zero) {
			return nil, nil
		}

		if shares.GreaterThan(pos) {
			shares = pos
			order.Quantity = shares.Mul(fillPx)
			fee = order.Quantity.Mul(feeRate)
		}

		revenue := order.Quantity
		totalFee := fee
		b.cash = b.cash.Add(revenue.Sub(totalFee))
		b.positions[order.Symbol] = pos.Sub(shares)
	}

	return &OrderEvent{
		EventID:   uuid.New().String(),
		OrderID:   order.OrderID,
		SignalID:  order.SignalID,
		Symbol:    order.Symbol,
		Kind:      StatusFilled,
		FilledQty: shares,
		FilledPx:  fillPx,
		Fee:       fee,
		Timestamp: time.Now().UnixNano(),
	}, nil
}
