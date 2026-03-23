# Shared Dockerfile for Go services
# Build context should be the specific service directory (risk-engine, trading-layer, api-gateway)
FROM golang:1.22-bookworm AS builder

WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o service ./src/main.go

# ── Runtime ─────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/service /service
ENTRYPOINT ["/service"]
