package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"go.uber.org/zap"
)

// NLP 命令处理器
type NLPHandler struct {
	ollamaURL string
	model     string
	logger    *zap.Logger
	client    *http.Client
}

// 命令意图
type CommandIntent struct {
	Action     string            `json:"action"`      // 动作类型
	Parameters map[string]string `json:"parameters"`  // 参数
	Confidence float64           `json:"confidence"`  // 置信度
	Response   string            `json:"response"`    // 回复消息
}

// Ollama 请求
type OllamaRequest struct {
	Model  string `json:"model"`
	Prompt string `json:"prompt"`
	Stream bool   `json:"stream"`
}

// Ollama 响应
type OllamaResponse struct {
	Response string `json:"response"`
	Done     bool   `json:"done"`
}

func NewNLPHandler(ollamaURL, model string, logger *zap.Logger) *NLPHandler {
	return &NLPHandler{
		ollamaURL: ollamaURL,
		model:     model,
		logger:    logger,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// 解析自然语言命令
func (h *NLPHandler) ParseCommand(ctx context.Context, userMessage string) (*CommandIntent, error) {
	h.logger.Info("Parsing natural language command", zap.String("message", userMessage))

	// 构建提示词
	prompt := h.buildPrompt(userMessage)

	// 调用 Ollama
	response, err := h.callOllama(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("failed to call Ollama: %w", err)
	}

	// 解析 JSON 响应
	intent, err := h.parseIntent(response)
	if err != nil {
		return nil, fmt.Errorf("failed to parse intent: %w", err)
	}

	h.logger.Info("Parsed command intent",
		zap.String("action", intent.Action),
		zap.Float64("confidence", intent.Confidence))

	return intent, nil
}

// 构建提示词
func (h *NLPHandler) buildPrompt(userMessage string) string {
	return fmt.Sprintf(`你是一个交易系统命令解析助手。用户会用自然语言发送命令，你需要将其转换为结构化的命令。

支持的命令类型：
1. QUERY_STATUS - 查询账户状态
2. QUERY_POSITIONS - 查询持仓
3. QUERY_PRICE - 查询价格
4. CLOSE_POSITION - 平仓
5. CLOSE_ALL - 平掉所有仓位
6. PAUSE_TRADING - 暂停交易
7. RESUME_TRADING - 恢复交易
8. ENABLE_STRATEGY - 启用策略
9. DISABLE_STRATEGY - 禁用策略
10. QUERY_PNL - 查询盈亏
11. QUERY_TRADES - 查询交易历史
12. SET_RISK_LIMIT - 设置风控参数
13. UNKNOWN - 无法识别的命令

用户消息: "%s"

请以 JSON 格式返回，包含以下字段：
{
  "action": "命令类型",
  "parameters": {
    "symbol": "交易对（如果适用）",
    "strategy": "策略名称（如果适用）",
    "value": "数值（如果适用）"
  },
  "confidence": 0.95,
  "response": "给用户的友好回复"
}

只返回 JSON，不要其他内容。`, userMessage)
}

// 调用 Ollama
func (h *NLPHandler) callOllama(ctx context.Context, prompt string) (string, error) {
	reqBody := OllamaRequest{
		Model:  h.model,
		Prompt: prompt,
		Stream: false,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", h.ollamaURL+"/api/generate", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := h.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("Ollama returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var ollamaResp OllamaResponse
	if err := json.Unmarshal(body, &ollamaResp); err != nil {
		return "", err
	}

	return ollamaResp.Response, nil
}

// 解析意图
func (h *NLPHandler) parseIntent(response string) (*CommandIntent, error) {
	// 提取 JSON 部分（可能包含在其他文本中）
	jsonStr := h.extractJSON(response)

	var intent CommandIntent
	if err := json.Unmarshal([]byte(jsonStr), &intent); err != nil {
		// 如果解析失败，返回默认的未知命令
		return &CommandIntent{
			Action:     "UNKNOWN",
			Parameters: make(map[string]string),
			Confidence: 0.0,
			Response:   "抱歉，我无法理解这个命令。请尝试使用 /help 查看可用命令。",
		}, nil
	}

	return &intent, nil
}

// 提取 JSON 字符串
func (h *NLPHandler) extractJSON(text string) string {
	// 查找第一个 { 和最后一个 }
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")

	if start == -1 || end == -1 || start >= end {
		return text
	}

	return text[start : end+1]
}

// 执行命令
func (tb *TelegramBot) executeNLPCommand(intent *CommandIntent) error {
	tb.logger.Info("Executing NLP command", zap.String("action", intent.Action))

	switch intent.Action {
	case "QUERY_STATUS":
		tb.sendAccountStatus()

	case "QUERY_POSITIONS":
		tb.sendPositions()

	case "QUERY_PRICE":
		symbol := intent.Parameters["symbol"]
		if symbol == "" {
			tb.sendMessage("请指定要查询的交易对，例如：查询 BTC-USDT 的价格")
			return nil
		}
		tb.queryPrice(symbol)

	case "CLOSE_POSITION":
		symbol := intent.Parameters["symbol"]
		if symbol == "" {
			tb.sendMessage("请指定要平仓的交易对，例如：平掉 BTC-USDT 的仓位")
			return nil
		}
		tb.closePosition(symbol)

	case "CLOSE_ALL":
		tb.closeAllPositions()

	case "PAUSE_TRADING":
		tb.pauseTrading()

	case "RESUME_TRADING":
		tb.resumeTrading()

	case "ENABLE_STRATEGY":
		strategy := intent.Parameters["strategy"]
		if strategy == "" {
			tb.sendMessage("请指定要启用的策略名称")
			return nil
		}
		tb.enableStrategy(strategy)

	case "DISABLE_STRATEGY":
		strategy := intent.Parameters["strategy"]
		if strategy == "" {
			tb.sendMessage("请指定要禁用的策略名称")
			return nil
		}
		tb.disableStrategy(strategy)

	case "QUERY_PNL":
		tb.sendPnLReport()

	case "QUERY_TRADES":
		tb.sendRecentTrades()

	case "SET_RISK_LIMIT":
		// TODO: 实现风控参数设置
		tb.sendMessage("风控参数设置功能开发中...")

	case "UNKNOWN":
		tb.sendMessage(intent.Response)

	default:
		tb.sendMessage("抱歉，我还不支持这个命令。")
	}

	return nil
}

// 查询价格
func (tb *TelegramBot) queryPrice(symbol string) {
	// 从 Redis 获取最新价格
	result, err := tb.redis.Get(tb.ctx, fmt.Sprintf("price:%s", symbol)).Result()
	if err != nil {
		tb.sendMessage(fmt.Sprintf("无法获取 %s 的价格", symbol))
		return
	}

	message := fmt.Sprintf("💰 <b>%s 实时价格</b>\n\n价格: $%s", symbol, result)
	tb.sendMessage(message)
}

// 平仓
func (tb *TelegramBot) closePosition(symbol string) {
	// 发送平仓命令到 Redis
	command := map[string]interface{}{
		"action":       "CLOSE_POSITION",
		"symbol":       symbol,
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage(fmt.Sprintf("✅ 已发送平仓指令：%s", symbol))
}

// 平掉所有仓位
func (tb *TelegramBot) closeAllPositions() {
	command := map[string]interface{}{
		"action":       "CLOSE_ALL",
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage("✅ 已发送平掉所有仓位指令")
}

// 暂停交易
func (tb *TelegramBot) pauseTrading() {
	command := map[string]interface{}{
		"action":       "PAUSE_TRADING",
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage("⏸️ 已暂停所有交易")
}

// 恢复交易
func (tb *TelegramBot) resumeTrading() {
	command := map[string]interface{}{
		"action":       "RESUME_TRADING",
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage("▶️ 已恢复交易")
}

// 启用策略
func (tb *TelegramBot) enableStrategy(strategy string) {
	command := map[string]interface{}{
		"action":       "ENABLE_STRATEGY",
		"strategy":     strategy,
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage(fmt.Sprintf("✅ 已启用策略：%s", strategy))
}

// 禁用策略
func (tb *TelegramBot) disableStrategy(strategy string) {
	command := map[string]interface{}{
		"action":       "DISABLE_STRATEGY",
		"strategy":     strategy,
		"timestamp_ns": time.Now().UnixNano(),
		"source":       "telegram",
	}

	jsonData, _ := json.Marshal(command)
	tb.redis.Publish(tb.ctx, "trading.command", jsonData)

	tb.sendMessage(fmt.Sprintf("⏸️ 已禁用策略：%s", strategy))
}

// 发送盈亏报告
func (tb *TelegramBot) sendPnLReport() {
	// TODO: 从 Redis 获取盈亏数据
	message := "💰 <b>盈亏报告</b>\n\n待实现..."
	tb.sendMessage(message)
}

// 发送最近交易
func (tb *TelegramBot) sendRecentTrades() {
	// TODO: 从 Redis 获取交易历史
	message := "📊 <b>最近交易</b>\n\n待实现..."
	tb.sendMessage(message)
}
