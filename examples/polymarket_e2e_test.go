// 端到端测试程序
// 验证 Polymarket 数据流：CLOB API -> Redis -> 交易层

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

func main() {
	fmt.Println("=== Polymarket 端到端测试 ===")

	// 1. 测试数据层 -> Redis
	fmt.Println("\n1. 测试数据层到 Redis 的连接...")
	testDataLayerToRedis()

	// 2. 测试交易层消费
	fmt.Println("\n2. 测试交易层消费数据...")
	testTradingLayerConsumer()

	// 3. 测试订单发布
	fmt.Println("\n3. 测试订单发布...")
	testOrderCommand()

	fmt.Println("\n=== 测试完成 ===")
}

// 测试数据层到 Redis
func testDataLayerToRedis() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	// 模拟一个 Polymarket tick
	tick := map[string]interface{}{
		"symbol": map[string]string{
			"exchange": "polymarket",
			"base":     "0x123abc:0x456def:will-btc-hit-100k-2024",
			"quote":    "USDC",
		},
		"timestamp_ns": time.Now().UnixNano(),
		"received_ns":  time.Now().UnixNano(),
		"bid_price":    "0.65",
		"ask_price":    "0.66",
		"bid_size":     "1000.00",
		"ask_size":     "800.00",
		"last_price":   "0.655",
		"last_size":    "0",
		"volume_24h":   "0",
		"latency_us":   "1500",
	}

	tickJSON, _ := json.Marshal(tick)

	// 发布到 Redis Stream
	streamKey := "market.tick.polymarket.will-btc-hit-100k-2024-USDC"
	err := rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: streamKey,
		Values: map[string]interface{}{
			"data": string(tickJSON),
			"sym":  "will-btc-hit-100k-2024-USDC",
		},
	}).Err()

	if err != nil {
		log.Printf("❌ Redis 发布失败: %v", err)
		return
	}

	fmt.Printf("✅ 已发布 tick 到 %s\n", streamKey)
	fmt.Printf("   Bid: 0.65 (65%% 概率), Ask: 0.66 (66%% 概率)\n")

	// 验证数据可读
	entries, err := rdb.XRead(ctx, &redis.XReadArgs{
		Streams: []string{streamKey, "0"},
		Count:   1,
	}).Result()

	if err != nil {
		log.Printf("❌ Redis 读取失败: %v", err)
		return
	}

	if len(entries) > 0 && len(entries[0].Messages) > 0 {
		fmt.Println("✅ 成功从 Redis 读取 tick")
	}
}

// 测试交易层消费
func testTradingLayerConsumer() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	// 创建消费者组（如果交易层已启动，这里会复用）
	group := "trading-cg"
	streamKey := "market.tick.polymarket.will-btc-hit-100k-2024-USDC"

	// 尝试创建消费者组
	_ = rdb.XGroupCreateMkStream(ctx, streamKey, group, "$").Err()

	// 消费消息
	entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
		Group:    group,
		Consumer: "test-consumer",
		Streams:  []string{streamKey, ">"},
		Count:    10,
		Block:    2 * time.Second,
	}).Result()

	if err != nil {
		log.Printf("⚠️  消费超时或出错: %v", err)
		fmt.Println("   提示：确保 Redis 中有数据，或交易层已在运行")
		return
	}

	for _, entry := range entries {
		for _, msg := range entry.Messages {
			if raw, ok := msg.Values["data"].(string); ok {
				var tick map[string]interface{}
				if err := json.Unmarshal([]byte(raw), &tick); err == nil {
					fmt.Printf("✅ 消费到 tick: bid=%v, ask=%v\n",
						tick["bid_price"], tick["ask_price"])

					// 确认消息
					rdb.XAck(ctx, streamKey, group, msg.ID)
				}
			}
		}
	}
}

// 测试订单命令
func testOrderCommand() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	// 创建测试订单
	order := map[string]interface{}{
		"command_id":  "cmd-test-001",
		"signal_id":   "sig-001",
		"symbol":      "0x123abc:0x456def:will-btc-hit-100k-2024",
		"direction":   "long",
		"quantity":    "100.00",
		"order_type":  "limit",
		"price":       "0.65",
		"mode":        "paper",
	}

	orderJSON, _ := json.Marshal(order)

	// 发布到 order.command
	err := rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: "order.command",
		Values: map[string]interface{}{
			"data": string(orderJSON),
		},
	}).Err()

	if err != nil {
		log.Printf("❌ 订单发布失败: %v", err)
		return
	}

	fmt.Printf("✅ 已发布订单命令: %s\n", order["command_id"])
	fmt.Printf("   市场: %s\n", order["symbol"])
	fmt.Printf("   方向: %s, 金额: %s USDC\n", order["direction"], order["quantity"])
	fmt.Printf("   价格: %s (%%概率)\n", order["price"])

	// 等待交易层处理并检查 order.event
	time.Sleep(500 * time.Millisecond)

	// 读取订单事件
	events, err := rdb.XRead(ctx, &redis.XReadArgs{
		Streams: []string{"order.event", "0"},
		Count:   10,
	}).Result()

	if err != nil {
		log.Printf("⚠️  读取订单事件失败: %v", err)
		return
	}

	for _, entry := range events {
		for _, msg := range entry.Messages {
			if raw, ok := msg.Values["data"].(string); ok {
				var event map[string]interface{}
				if err := json.Unmarshal([]byte(raw), &event); err == nil {
					fmt.Printf("✅ 收到订单事件: status=%s\n", event["kind"])
				}
			}
		}
	}
}
