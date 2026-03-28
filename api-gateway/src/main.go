package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"api-gateway/handlers"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// ── WebSocket hub ──────────────────────────────────────────

type WSClient struct {
	conn *websocket.Conn
	send chan []byte
	subs map[string]bool // subscribed topics
}

type WSHub struct {
	clients    map[*WSClient]bool
	broadcast  chan []byte
	register   chan *WSClient
	unregister chan *WSClient
	mu         sync.RWMutex
}

func NewWSHub() *WSHub {
	return &WSHub{
		clients:    make(map[*WSClient]bool),
		broadcast:  make(chan []byte, 512),
		register:   make(chan *WSClient),
		unregister: make(chan *WSClient),
	}
}

func (h *WSHub) Run() {
	for {
		select {
		case c := <-h.register:
			h.mu.Lock()
			h.clients[c] = true
			h.mu.Unlock()
		case c := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[c]; ok {
				delete(h.clients, c)
				close(c.send)
			}
			h.mu.Unlock()
		case msg := <-h.broadcast:
			h.mu.RLock()
			for c := range h.clients {
				select {
				case c.send <- msg:
				default:
					// client too slow — drop
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (h *WSHub) BroadcastJSON(v any) {
	b, err := json.Marshal(v)
	if err != nil {
		return
	}
	select {
	case h.broadcast <- b:
	default:
	}
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

func (h *WSHub) ServeWS(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		return
	}
	client := &WSClient{conn: conn, send: make(chan []byte, 256), subs: make(map[string]bool)}
	h.register <- client

	// Writer goroutine
	go func() {
		defer func() {
			h.unregister <- client
			conn.Close()
		}()
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case msg, ok := <-client.send:
				if !ok {
					conn.WriteMessage(websocket.CloseMessage, []byte{})
					return
				}
				conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
				if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
					return
				}
			case <-ticker.C:
				conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
				if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
					return
				}
			}
		}
	}()

	// Reader goroutine
	go func() {
		defer func() { h.unregister <- client }()
		conn.SetReadLimit(4096)
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		conn.SetPongHandler(func(string) error {
			conn.SetReadDeadline(time.Now().Add(60 * time.Second))
			return nil
		})
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				return
			}
		}
	}()
}

// ── Redis stream relay ─────────────────────────────────────

func relayStreams(ctx context.Context, rdb *redis.Client, hub *WSHub, logger *zap.Logger) {
	topics := []string{
		"market.tick.binance.btcusdt",
		"market.tick.binance.ethusdt",
		"strategy.signal",
		"order.event",
		"risk.alert",
		"llm.weight",
	}

	group := "gateway-relay"
	for _, t := range topics {
		_ = rdb.XGroupCreateMkStream(ctx, t, group, "$").Err()
	}

	streamArgs := make([]string, 0, len(topics)*2)
	for _, t := range topics {
		streamArgs = append(streamArgs, t, ">")
	}

	for {
		entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    group,
			Consumer: "gateway-1",
			Streams:  streamArgs,
			Count:    100,
			Block:    50 * time.Millisecond,
		}).Result()
		if err != nil {
			time.Sleep(100 * time.Millisecond)
			continue
		}

		var allAcks = make(map[string][]string)
		for _, stream := range entries {
			for _, msg := range stream.Messages {
				var payload map[string]any
				for k, v := range msg.Values {
					if str, ok := v.(string); ok && k == "data" {
						_ = json.Unmarshal([]byte(str), &payload)
					}
				}
				if payload == nil {
					payload = make(map[string]any)
					for k, v := range msg.Values {
						payload[k] = v
					}
				}
				payload["_topic"] = stream.Stream
				payload["_id"]    = msg.ID
				hub.BroadcastJSON(payload)
				allAcks[stream.Stream] = append(allAcks[stream.Stream], msg.ID)
			}
		}
		for topic, ids := range allAcks {
			_ = rdb.XAck(ctx, topic, group, ids...).Err()
		}
	}
}

// ── JWT middleware ─────────────────────────────────────────

func JWTMiddleware(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		auth := c.GetHeader("Authorization")
		if auth == "" || !strings.HasPrefix(auth, "Bearer ") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing token"})
			return
		}
		tokenStr := strings.TrimPrefix(auth, "Bearer ")
		token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {
			return []byte(secret), nil
		})
		if err != nil || !token.Valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}
		c.Next()
	}
}

// ── REST handlers ──────────────────────────────────────────

func setupRoutes(r *gin.Engine, rdb *redis.Client, hub *WSHub, secret string) {
	auth := JWTMiddleware(secret)
	h := handlers.NewHandler(rdb)

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "ts": time.Now().Unix()})
	})

	// WebSocket endpoint (no auth for simplicity — add in production)
	r.GET("/ws", hub.ServeWS)

	api := r.Group("/api/v1")
	
	// Polymarket endpoints (no auth for now - public data)
	api.GET("/polymarket/markets", h.GetPolymarketMarkets)
	api.GET("/polymarket/markets/:id", h.GetPolymarketMarket)
	api.GET("/polymarket/stats", h.GetPolymarketStats)
	api.GET("/polymarket/markets/btc", h.GetBTCMarkets)
	api.GET("/polymarket/strategy/btc5m", h.GetBTCStrategy)
	api.GET("/polymarket/strategy/stats", h.GetStrategyStats)
	api.GET("/polymarket/orderbook/:asset", h.GetPolymarketOrderBook)
	
	// Protected endpoints
	api.Use(auth)
	{
		// Strategies
		api.GET("/strategies", func(c *gin.Context) {
			// In production: call strategy-layer service
			c.JSON(http.StatusOK, gin.H{"strategies": []string{"ma_cross_v1", "mean_reversion_v1"}})
		})

		// Orders
		api.GET("/orders", func(c *gin.Context) {
			ctx := c.Request.Context()
			entries, _ := rdb.XRevRange(ctx, "order.event", "+", "-").Result()
			orders := make([]map[string]any, 0, len(entries))
			for _, e := range entries {
				if raw, ok := e.Values["data"].(string); ok {
					var o map[string]any
					if json.Unmarshal([]byte(raw), &o) == nil {
						orders = append(orders, o)
					}
				}
			}
			c.JSON(http.StatusOK, gin.H{"orders": orders})
		})

		// Risk alerts
		api.GET("/alerts", func(c *gin.Context) {
			ctx := c.Request.Context()
			entries, _ := rdb.XRevRange(ctx, "risk.alert", "+", "-").Result()
			alerts := make([]map[string]any, 0)
			for _, e := range entries {
				if raw, ok := e.Values["data"].(string); ok {
					var a map[string]any
					if json.Unmarshal([]byte(raw), &a) == nil {
						alerts = append(alerts, a)
					}
				}
			}
			c.JSON(http.StatusOK, gin.H{"alerts": alerts})
		})

		// Latest LLM weights
		api.GET("/weights", func(c *gin.Context) {
			ctx := c.Request.Context()
			entries, _ := rdb.XRevRange(ctx, "llm.weight", "+", "-").Result()
			weights := make([]map[string]any, 0)
			seen := map[string]bool{}
			for _, e := range entries {
				sym, _ := e.Values["symbol"].(string)
				if seen[sym] {
					continue
				}
				seen[sym] = true
				if raw, ok := e.Values["data"].(string); ok {
					var w map[string]any
					if json.Unmarshal([]byte(raw), &w) == nil {
						weights = append(weights, w)
					}
				}
			}
			c.JSON(http.StatusOK, gin.H{"weights": weights})
		})

		// Market snapshot (latest ticks)
		api.GET("/ticks/:symbol", func(c *gin.Context) {
			sym   := strings.ToLower(strings.ReplaceAll(c.Param("symbol"), "-", ""))
			topic := "market.tick.binance." + sym
			entries, _ := rdb.XRevRange(c.Request.Context(), topic, "+", "-").Result()
			if len(entries) == 0 {
				c.JSON(http.StatusNotFound, gin.H{"error": "no data"})
				return
			}
			if raw, ok := entries[0].Values["data"].(string); ok {
				var tick map[string]any
				_ = json.Unmarshal([]byte(raw), &tick)
				c.JSON(http.StatusOK, tick)
			}
		})
	}
}

// ── Main ───────────────────────────────────────────────────

func main() {
	_ = godotenv.Load()
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	gin.SetMode(gin.ReleaseMode)

	redisURL := getenv("REDIS_URL", "redis://localhost:6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisURL[8:]})

	secret := getenv("JWT_SECRET", "dev-secret-change-in-production")
	port   := getenv("API_PORT", "8080")

	hub := NewWSHub()
	go hub.Run()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go relayStreams(ctx, rdb, hub, logger)

	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:5173", "http://localhost:3000"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Authorization", "Content-Type"},
		AllowCredentials: true,
	}))

	setupRoutes(r, rdb, hub, secret)

	srv := &http.Server{Addr: ":" + port, Handler: r}

	logger.Info("api_gateway_started", zap.String("port", port))

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("server_error", zap.Error(err))
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	shutCtx, shutCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutCancel()
	_ = srv.Shutdown(shutCtx)
	logger.Info("api_gateway_stopped")
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
