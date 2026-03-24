package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/redis/go-redis/v9"
	"github.com/shopspring/decimal"
	"go.uber.org/zap"
)

type TelegramBot struct {
	bot       *tgbotapi.BotAPI
	redis     *redis.Client
	logger    *zap.Logger
	chatID    int64
	ctx       context.Context
	cancel    context.CancelFunc
}

// 订单事件
type OrderEvent struct {
	OrderID     string          `json:"order_id"`
	Symbol      string          `json:"symbol"`
	Side        string          `json:"side"`
	Status      string          `json:"status"`
	Price       decimal.Decimal `json:"price"`
	Quantity    decimal.Decimal `json:"quantity"`
	FilledQty   decimal.Decimal `json:"filled_qty"`
	TimestampNs int64           `json:"timestamp_ns"`
}

// 风险告警
type RiskAlert struct {
	AlertType   string          `json:"alert_type"`
	Severity    string          `json:"severity"`
	Message     string          `json:"message"`
	Symbol      string          `json:"symbol,omitempty"`
	Value       decimal.Decimal `json:"value,omitempty"`
	Threshold   decimal.Decimal `json:"threshold,omitempty"`
	TimestampNs int64           `json:"timestamp_ns"`
}

// 持仓更新
type PositionUpdate struct {
	Symbol      string          `json:"symbol"`
	Side        string          `json:"side"`
	Quantity    decimal.Decimal `json:"quantity"`
	EntryPrice  decimal.Decimal `json:"entry_price"`
	CurrentPrice decimal.Decimal `json:"current_price"`
	UnrealizedPnL decimal.Decimal `json:"unrealized_pnl"`
	RealizedPnL decimal.Decimal `json:"realized_pnl"`
	TimestampNs int64           `json:"timestamp_ns"`
}

// 账户状态
type AccountState struct {
	TotalEquity     decimal.Decimal `json:"total_equity"`
	AvailableBalance decimal.Decimal `json:"available_balance"`
	UsedMargin      decimal.Decimal `json:"used_margin"`
	DailyPnL        decimal.Decimal `json:"daily_pnl"`
	TotalPnL        decimal.Decimal `json:"total_pnl"`
	TimestampNs     int64           `json:"timestamp_ns"`
}

func NewTelegramBot(token string, chatID int64, redisAddr string) (*TelegramBot, error) {
	// 创建 logger
	logger, _ := zap.NewProduction()

	// 创建 Telegram Bot
	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return nil, fmt.Errorf("failed to create bot: %w", err)
	}

	logger.Info("Telegram Bot authorized", zap.String("username", bot.Self.UserName))

	// 创建 Redis 客户端
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
		DB:   0,
	})

	// 测试 Redis 连接
	ctx := context.Background()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	return &TelegramBot{
		bot:    bot,
		redis:  rdb,
		logger: logger,
		chatID: chatID,
		ctx:    ctx,
		cancel: cancel,
	}, nil
}

func (tb *TelegramBot) Start() error {
	tb.logger.Info("Starting Telegram Bot service")

	// 发送启动消息
	tb.sendMessage("🤖 Crazytra 交易机器人已启动\n\n准备接收交易通知...")

	// 订阅 Redis Streams
	go tb.subscribeOrderEvents()
	go tb.subscribeRiskAlerts()
	go tb.subscribePositionUpdates()
	go tb.subscribeAccountState()

	// 定时发送日报
	go tb.scheduleDailyReport()

	// 处理 Telegram 命令
	go tb.handleCommands()

	return nil
}

func (tb *TelegramBot) Stop() {
	tb.logger.Info("Stopping Telegram Bot service")
	tb.cancel()
	tb.redis.Close()
	tb.sendMessage("🛑 Crazytra 交易机器人已停止")
}

// 订阅订单事件
func (tb *TelegramBot) subscribeOrderEvents() {
	tb.logger.Info("Subscribing to order events")

	for {
		select {
		case <-tb.ctx.Done():
			return
		default:
			result, err := tb.redis.XRead(tb.ctx, &redis.XReadArgs{
				Streams: []string{"order.event", "$"},
				Block:   time.Second * 5,
				Count:   10,
			}).Result()

			if err != nil && err != redis.Nil {
				tb.logger.Error("Failed to read order events", zap.Error(err))
				time.Sleep(time.Second)
				continue
			}

			for _, stream := range result {
				for _, msg := range stream.Messages {
					tb.handleOrderEvent(msg.Values)
					tb.redis.XAck(tb.ctx, "order.event", "telegram-bot-cg", msg.ID)
				}
			}
		}
	}
}

// 处理订单事件
func (tb *TelegramBot) handleOrderEvent(data map[string]interface{}) {
	jsonData, _ := json.Marshal(data)
	var event OrderEvent
	if err := json.Unmarshal(jsonData, &event); err != nil {
		tb.logger.Error("Failed to parse order event", zap.Error(err))
		return
	}

	// 根据订单状态发送不同的消息
	var emoji string
	var statusText string

	switch event.Status {
	case "FILLED":
		emoji = "✅"
		statusText = "成交"
	case "PARTIALLY_FILLED":
		emoji = "⏳"
		statusText = "部分成交"
	case "CANCELED":
		emoji = "❌"
		statusText = "已取消"
	case "REJECTED":
		emoji = "🚫"
		statusText = "已拒绝"
	default:
		return // 其他状态不通知
	}

	sideEmoji := "🟢"
	if event.Side == "SELL" || event.Side == "SHORT" {
		sideEmoji = "🔴"
	}

	message := fmt.Sprintf(
		"%s <b>订单%s</b>\n\n"+
			"%s <b>%s</b> %s\n"+
			"价格: $%s\n"+
			"数量: %s\n"+
			"成交: %s\n"+
			"订单ID: <code>%s</code>",
		emoji, statusText,
		sideEmoji, event.Symbol, event.Side,
		event.Price.StringFixed(2),
		event.Quantity.StringFixed(4),
		event.FilledQty.StringFixed(4),
		event.OrderID,
	)

	tb.sendMessage(message)
}

// 订阅风险告警
func (tb *TelegramBot) subscribeRiskAlerts() {
	tb.logger.Info("Subscribing to risk alerts")

	for {
		select {
		case <-tb.ctx.Done():
			return
		default:
			result, err := tb.redis.XRead(tb.ctx, &redis.XReadArgs{
				Streams: []string{"risk.alert", "$"},
				Block:   time.Second * 5,
				Count:   10,
			}).Result()

			if err != nil && err != redis.Nil {
				tb.logger.Error("Failed to read risk alerts", zap.Error(err))
				time.Sleep(time.Second)
				continue
			}

			for _, stream := range result {
				for _, msg := range stream.Messages {
					tb.handleRiskAlert(msg.Values)
					tb.redis.XAck(tb.ctx, "risk.alert", "telegram-bot-cg", msg.ID)
				}
			}
		}
	}
}

// 处理风险告警
func (tb *TelegramBot) handleRiskAlert(data map[string]interface{}) {
	jsonData, _ := json.Marshal(data)
	var alert RiskAlert
	if err := json.Unmarshal(jsonData, &alert); err != nil {
		tb.logger.Error("Failed to parse risk alert", zap.Error(err))
		return
	}

	var emoji string
	switch alert.Severity {
	case "CRITICAL":
		emoji = "🚨"
	case "HIGH":
		emoji = "⚠️"
	case "MEDIUM":
		emoji = "⚡"
	default:
		emoji = "ℹ️"
	}

	message := fmt.Sprintf(
		"%s <b>风险告警</b>\n\n"+
			"类型: %s\n"+
			"级别: %s\n"+
			"消息: %s",
		emoji,
		alert.AlertType,
		alert.Severity,
		alert.Message,
	)

	if alert.Symbol != "" {
		message += fmt.Sprintf("\n交易对: %s", alert.Symbol)
	}

	if !alert.Value.IsZero() {
		message += fmt.Sprintf("\n当前值: %s", alert.Value.StringFixed(2))
	}

	if !alert.Threshold.IsZero() {
		message += fmt.Sprintf("\n阈值: %s", alert.Threshold.StringFixed(2))
	}

	tb.sendMessage(message)
}

// 订阅持仓更新
func (tb *TelegramBot) subscribePositionUpdates() {
	tb.logger.Info("Subscribing to position updates")

	lastNotify := make(map[string]time.Time)
	notifyInterval := time.Minute * 5 // 每个持仓5分钟最多通知一次

	for {
		select {
		case <-tb.ctx.Done():
			return
		default:
			result, err := tb.redis.XRead(tb.ctx, &redis.XReadArgs{
				Streams: []string{"position.update", "$"},
				Block:   time.Second * 5,
				Count:   10,
			}).Result()

			if err != nil && err != redis.Nil {
				tb.logger.Error("Failed to read position updates", zap.Error(err))
				time.Sleep(time.Second)
				continue
			}

			for _, stream := range result {
				for _, msg := range stream.Messages {
					var pos PositionUpdate
					jsonData, _ := json.Marshal(msg.Values)
					if err := json.Unmarshal(jsonData, &pos); err != nil {
						continue
					}

					// 限流：避免频繁通知
					if last, ok := lastNotify[pos.Symbol]; ok {
						if time.Since(last) < notifyInterval {
							continue
						}
					}
					lastNotify[pos.Symbol] = time.Now()

					tb.handlePositionUpdate(pos)
					tb.redis.XAck(tb.ctx, "position.update", "telegram-bot-cg", msg.ID)
				}
			}
		}
	}
}

// 处理持仓更新
func (tb *TelegramBot) handlePositionUpdate(pos PositionUpdate) {
	pnlEmoji := "📊"
	if pos.UnrealizedPnL.GreaterThan(decimal.Zero) {
		pnlEmoji = "📈"
	} else if pos.UnrealizedPnL.LessThan(decimal.Zero) {
		pnlEmoji = "📉"
	}

	sideEmoji := "🟢"
	if pos.Side == "SHORT" {
		sideEmoji = "🔴"
	}

	message := fmt.Sprintf(
		"%s <b>持仓更新</b>\n\n"+
			"%s <b>%s</b> %s\n"+
			"数量: %s\n"+
			"入场价: $%s\n"+
			"当前价: $%s\n"+
			"未实现盈亏: $%s\n"+
			"已实现盈亏: $%s",
		pnlEmoji,
		sideEmoji, pos.Symbol, pos.Side,
		pos.Quantity.StringFixed(4),
		pos.EntryPrice.StringFixed(2),
		pos.CurrentPrice.StringFixed(2),
		pos.UnrealizedPnL.StringFixed(2),
		pos.RealizedPnL.StringFixed(2),
	)

	tb.sendMessage(message)
}

// 订阅账户状态
func (tb *TelegramBot) subscribeAccountState() {
	tb.logger.Info("Subscribing to account state")

	for {
		select {
		case <-tb.ctx.Done():
			return
		default:
			result, err := tb.redis.XRead(tb.ctx, &redis.XReadArgs{
				Streams: []string{"account.state", "$"},
				Block:   time.Second * 5,
				Count:   1,
			}).Result()

			if err != nil && err != redis.Nil {
				tb.logger.Error("Failed to read account state", zap.Error(err))
				time.Sleep(time.Second)
				continue
			}

			for _, stream := range result {
				for _, msg := range stream.Messages {
					// 账户状态更新频率较低，不需要每次都通知
					tb.redis.XAck(tb.ctx, "account.state", "telegram-bot-cg", msg.ID)
				}
			}
		}
	}
}

// 定时发送日报
func (tb *TelegramBot) scheduleDailyReport() {
	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	// 每天早上8点发送
	for {
		now := time.Now()
		next := time.Date(now.Year(), now.Month(), now.Day(), 8, 0, 0, 0, now.Location())
		if now.After(next) {
			next = next.Add(24 * time.Hour)
		}

		select {
		case <-tb.ctx.Done():
			return
		case <-time.After(time.Until(next)):
			tb.sendDailyReport()
		}
	}
}

// 发送日报
func (tb *TelegramBot) sendDailyReport() {
	tb.logger.Info("Sending daily report")

	// 从 Redis 获取统计数据
	// TODO: 实现具体的统计逻辑

	message := fmt.Sprintf(
		"📊 <b>每日交易报告</b>\n\n"+
			"日期: %s\n\n"+
			"📈 今日统计\n"+
			"总交易次数: -\n"+
			"盈利交易: -\n"+
			"亏损交易: -\n"+
			"胜率: -\n\n"+
			"💰 盈亏统计\n"+
			"今日盈亏: $-\n"+
			"累计盈亏: $-\n"+
			"最大回撤: -\n\n"+
			"🎯 策略表现\n"+
			"待实现...",
		time.Now().Format("2006-01-02"),
	)

	tb.sendMessage(message)
}

// 处理 Telegram 命令
func (tb *TelegramBot) handleCommands() {
	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := tb.bot.GetUpdatesChan(u)

	for update := range updates {
		if update.Message == nil {
			continue
		}

		if !update.Message.IsCommand() {
			continue
		}

		switch update.Message.Command() {
		case "start":
			tb.sendMessage("👋 欢迎使用 Crazytra 交易机器人！\n\n可用命令：\n/status - 查看账户状态\n/positions - 查看持仓\n/report - 生成交易报告")
		case "status":
			tb.sendAccountStatus()
		case "positions":
			tb.sendPositions()
		case "report":
			tb.sendDailyReport()
		case "help":
			tb.sendMessage("📖 帮助信息\n\n/status - 账户状态\n/positions - 当前持仓\n/report - 交易报告")
		}
	}
}

// 发送账户状态
func (tb *TelegramBot) sendAccountStatus() {
	// TODO: 从 Redis 获取最新账户状态
	message := "💼 <b>账户状态</b>\n\n待实现..."
	tb.sendMessage(message)
}

// 发送持仓信息
func (tb *TelegramBot) sendPositions() {
	// TODO: 从 Redis 获取当前持仓
	message := "📊 <b>当前持仓</b>\n\n待实现..."
	tb.sendMessage(message)
}

// 发送消息
func (tb *TelegramBot) sendMessage(text string) {
	msg := tgbotapi.NewMessage(tb.chatID, text)
	msg.ParseMode = "HTML"

	if _, err := tb.bot.Send(msg); err != nil {
		tb.logger.Error("Failed to send message", zap.Error(err))
	}
}

func main() {
	// 从环境变量读取配置
	token := os.Getenv("TELEGRAM_BOT_TOKEN")
	if token == "" {
		fmt.Println("TELEGRAM_BOT_TOKEN is required")
		os.Exit(1)
	}

	chatID := int64(0)
	fmt.Sscanf(os.Getenv("TELEGRAM_CHAT_ID"), "%d", &chatID)
	if chatID == 0 {
		fmt.Println("TELEGRAM_CHAT_ID is required")
		os.Exit(1)
	}

	redisAddr := os.Getenv("REDIS_URL")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	// 创建 Telegram Bot
	bot, err := NewTelegramBot(token, chatID, redisAddr)
	if err != nil {
		fmt.Printf("Failed to create bot: %v\n", err)
		os.Exit(1)
	}

	// 启动服务
	if err := bot.Start(); err != nil {
		fmt.Printf("Failed to start bot: %v\n", err)
		os.Exit(1)
	}

	// 等待中断信号
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	// 优雅关闭
	bot.Stop()
}
