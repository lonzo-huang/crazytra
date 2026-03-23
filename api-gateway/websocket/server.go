package websocket

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
	"go.uber.org/zap"
)

// Server WebSocket 服务器
type Server struct {
	redis      *redis.Client
	logger     *zap.SugaredLogger
	clients    map[*Client]bool
	clientsMux sync.RWMutex
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
}

// Client WebSocket 客户端
type Client struct {
	server *Server
	conn   *websocket.Conn
	send   chan []byte
	subs   map[string]bool // 订阅的 topic
	subsMux sync.RWMutex
}

// NewServer 创建 WebSocket 服务器
func NewServer(redisClient *redis.Client, logger *zap.SugaredLogger) *Server {
	return &Server{
		redis:      redisClient,
		logger:     logger,
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// Run 运行 WebSocket 服务器
func (s *Server) Run(ctx context.Context) {
	s.logger.Info("websocket_server_started")

	// 启动 Redis 订阅
	go s.subscribeRedis(ctx)

	for {
		select {
		case <-ctx.Done():
			s.logger.Info("websocket_server_stopping")
			return

		case client := <-s.register:
			s.clientsMux.Lock()
			s.clients[client] = true
			s.clientsMux.Unlock()
			s.logger.Infow("client_registered", "total_clients", len(s.clients))

		case client := <-s.unregister:
			s.clientsMux.Lock()
			if _, ok := s.clients[client]; ok {
				delete(s.clients, client)
				close(client.send)
			}
			s.clientsMux.Unlock()
			s.logger.Infow("client_unregistered", "total_clients", len(s.clients))

		case message := <-s.broadcast:
			s.broadcastToClients(message)
		}
	}
}

// subscribeRedis 订阅 Redis Streams
func (s *Server) subscribeRedis(ctx context.Context) {
	// 订阅所有相关的 Redis topics
	topics := []string{
		"market.tick.*",
		"order.event",
		"position.update",
		"account.state",
		"risk.alert",
	}

	pubsub := s.redis.PSubscribe(ctx, topics...)
	defer pubsub.Close()

	s.logger.Infow("redis_subscribed", "topics", topics)

	ch := pubsub.Channel()
	for {
		select {
		case <-ctx.Done():
			return

		case msg := <-ch:
			s.handleRedisMessage(msg)
		}
	}
}

// handleRedisMessage 处理 Redis 消息
func (s *Server) handleRedisMessage(msg *redis.Message) {
	s.logger.Debugw("redis_message_received",
		"channel", msg.Channel,
		"payload_size", len(msg.Payload),
	)

	// 构造 WebSocket 消息
	wsMsg := map[string]interface{}{
		"type":    "data",
		"channel": msg.Channel,
		"data":    json.RawMessage(msg.Payload),
		"ts":      time.Now().UnixNano(),
	}

	data, err := json.Marshal(wsMsg)
	if err != nil {
		s.logger.Errorw("json_marshal_failed", "error", err)
		return
	}

	// 广播到所有订阅了该 channel 的客户端
	s.broadcastToSubscribers(msg.Channel, data)
}

// broadcastToClients 广播到所有客户端
func (s *Server) broadcastToClients(message []byte) {
	s.clientsMux.RLock()
	defer s.clientsMux.RUnlock()

	for client := range s.clients {
		select {
		case client.send <- message:
		default:
			// 客户端发送缓冲区满，关闭连接
			close(client.send)
			delete(s.clients, client)
		}
	}
}

// broadcastToSubscribers 广播到订阅了特定 channel 的客户端
func (s *Server) broadcastToSubscribers(channel string, message []byte) {
	s.clientsMux.RLock()
	defer s.clientsMux.RUnlock()

	sent := 0
	for client := range s.clients {
		if client.isSubscribed(channel) {
			select {
			case client.send <- message:
				sent++
			default:
				close(client.send)
				delete(s.clients, client)
			}
		}
	}

	s.logger.Debugw("message_broadcasted",
		"channel", channel,
		"clients", sent,
	)
}

// HandleWebSocket 处理 WebSocket 连接
func (s *Server) HandleWebSocket(conn *websocket.Conn) {
	client := &Client{
		server: s,
		conn:   conn,
		send:   make(chan []byte, 256),
		subs:   make(map[string]bool),
	}

	s.register <- client

	// 启动读写协程
	go client.writePump()
	go client.readPump()
}

// readPump 读取客户端消息
func (c *Client) readPump() {
	defer func() {
		c.server.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				c.server.logger.Errorw("websocket_read_error", "error", err)
			}
			break
		}

		c.handleMessage(message)
	}
}

// writePump 写入消息到客户端
func (c *Client) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			// 批量发送队列中的消息
			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				return
			}

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// handleMessage 处理客户端消息
func (c *Client) handleMessage(message []byte) {
	var msg map[string]interface{}
	if err := json.Unmarshal(message, &msg); err != nil {
		c.server.logger.Errorw("json_unmarshal_failed", "error", err)
		return
	}

	msgType, ok := msg["type"].(string)
	if !ok {
		return
	}

	switch msgType {
	case "subscribe":
		c.handleSubscribe(msg)
	case "unsubscribe":
		c.handleUnsubscribe(msg)
	case "ping":
		c.handlePing()
	}
}

// handleSubscribe 处理订阅请求
func (c *Client) handleSubscribe(msg map[string]interface{}) {
	channels, ok := msg["channels"].([]interface{})
	if !ok {
		return
	}

	c.subsMux.Lock()
	defer c.subsMux.Unlock()

	for _, ch := range channels {
		if channel, ok := ch.(string); ok {
			c.subs[channel] = true
			c.server.logger.Infow("client_subscribed", "channel", channel)
		}
	}

	// 发送确认
	response := map[string]interface{}{
		"type":     "subscribed",
		"channels": channels,
	}
	data, _ := json.Marshal(response)
	c.send <- data
}

// handleUnsubscribe 处理取消订阅
func (c *Client) handleUnsubscribe(msg map[string]interface{}) {
	channels, ok := msg["channels"].([]interface{})
	if !ok {
		return
	}

	c.subsMux.Lock()
	defer c.subsMux.Unlock()

	for _, ch := range channels {
		if channel, ok := ch.(string); ok {
			delete(c.subs, channel)
			c.server.logger.Infow("client_unsubscribed", "channel", channel)
		}
	}

	// 发送确认
	response := map[string]interface{}{
		"type":     "unsubscribed",
		"channels": channels,
	}
	data, _ := json.Marshal(response)
	c.send <- data
}

// handlePing 处理 ping
func (c *Client) handlePing() {
	response := map[string]interface{}{
		"type": "pong",
		"ts":   time.Now().UnixNano(),
	}
	data, _ := json.Marshal(response)
	c.send <- data
}

// isSubscribed 检查是否订阅了指定 channel
func (c *Client) isSubscribed(channel string) bool {
	c.subsMux.RLock()
	defer c.subsMux.RUnlock()

	// 检查精确匹配
	if c.subs[channel] {
		return true
	}

	// 检查通配符匹配
	for sub := range c.subs {
		if matchPattern(sub, channel) {
			return true
		}
	}

	return false
}

// matchPattern 简单的通配符匹配
func matchPattern(pattern, str string) bool {
	// 简化实现，只支持 * 通配符
	if pattern == "*" {
		return true
	}

	// TODO: 实现完整的通配符匹配
	return pattern == str
}
