# MirrorQuant API Gateway

Go-based API Gateway for MirrorQuant trading system.

## Features

- ✅ WebSocket support for real-time data
- ✅ Redis integration for data streaming
- ✅ JWT authentication
- ✅ CORS support
- ✅ Polymarket endpoints
- ✅ RESTful API

## Endpoints

### Public Endpoints

- `GET /health` - Health check
- `GET /ws` - WebSocket connection
- `GET /api/v1/polymarket/markets` - Get Polymarket markets
- `GET /api/v1/polymarket/markets/:id` - Get single market
- `GET /api/v1/polymarket/stats` - Get Polymarket stats

### Protected Endpoints (require JWT)

- `GET /api/v1/strategies` - List strategies
- `GET /api/v1/orders` - List orders
- `GET /api/v1/alerts` - List risk alerts
- `GET /api/v1/weights` - Get LLM weights
- `GET /api/v1/ticks/:symbol` - Get latest tick for symbol

## Build and Run

### Prerequisites

- Go 1.22+
- Redis running on localhost:6379

### Install Dependencies

```bash
cd api-gateway
go mod download
```

### Build

```bash
go build -o bin/api-gateway ./src
```

### Run

```bash
# Development mode
go run ./src/main.go

# Production mode
./bin/api-gateway
```

### Environment Variables

Create a `.env` file:

```env
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key-change-in-production
API_PORT=8080
```

## Development

### Project Structure

```
api-gateway/
├── src/
│   └── main.go          # Main application
├── handlers/
│   └── polymarket.go    # Polymarket handlers
├── websocket/
│   └── server.go        # WebSocket server
├── go.mod               # Go dependencies
└── README.md            # This file
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test Polymarket markets
curl http://localhost:8080/api/v1/polymarket/markets

# Test with authentication
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8080/api/v1/strategies
```

## Docker

Build and run with Docker:

```bash
# Build
docker build -t mirrorquant-api-gateway .

# Run
docker run -p 8080:8080 \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  mirrorquant-api-gateway
```

## Notes

- Polymarket endpoints are currently public (no auth required)
- WebSocket endpoint is also public for development
- Add authentication in production
- JWT secret should be changed in production
