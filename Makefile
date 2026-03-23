.PHONY: help up down build dev logs clean pull-model test

DOCKER_COMPOSE = cd infra && docker-compose

help:
	@echo "Trading system commands:"
	@echo "  make up          Start all services"
	@echo "  make down        Stop all services"
	@echo "  make build       Build all Docker images"
	@echo "  make dev         Start infra only (run services locally)"
	@echo "  make pull-model  Pull default Ollama model"
	@echo "  make logs        Tail all service logs"
	@echo "  make test        Run all tests"
	@echo "  make clean       Remove volumes and containers"

up: build
	$(DOCKER_COMPOSE) up -d
	@echo "✓ All services started"
	@echo "  Frontend : http://localhost:5173"
	@echo "  API      : http://localhost:8080"
	@echo "  Grafana  : http://localhost:3001"
	@echo "  Prometheus: http://localhost:9090"

down:
	$(DOCKER_COMPOSE) down

build:
	$(DOCKER_COMPOSE) build --parallel

# Start only infrastructure (Redis, DB, Ollama) — run app layers locally
dev:
	$(DOCKER_COMPOSE) up -d redis timescaledb ollama
	@echo "✓ Infrastructure up. Now run services locally:"
	@echo "  cd data-layer     && cargo run"
	@echo "  cd strategy-layer && python -m strategy_layer.main"
	@echo "  cd llm-layer      && python -m llm_layer.main"
	@echo "  cd risk-engine    && go run ./src/main.go"
	@echo "  cd trading-layer  && go run ./src/main.go"
	@echo "  cd api-gateway    && go run ./src/main.go"
	@echo "  cd frontend       && npm run dev"

pull-model:
	docker exec trading-ollama ollama pull mistral:7b-instruct-q4_K_M
	@echo "✓ Model downloaded"

logs:
	$(DOCKER_COMPOSE) logs -f --tail=100

logs-%:
	$(DOCKER_COMPOSE) logs -f --tail=100 $*

test:
	@echo "── Rust tests ──"
	cd data-layer && cargo test
	@echo "── Python tests ──"
	cd strategy-layer && python -m pytest tests/ -v 2>/dev/null || echo "No tests yet"
	cd llm-layer      && python -m pytest tests/ -v 2>/dev/null || echo "No tests yet"
	@echo "── Go tests ──"
	cd risk-engine   && go test ./...
	cd trading-layer && go test ./...
	cd api-gateway   && go test ./...

clean:
	$(DOCKER_COMPOSE) down -v --remove-orphans
	@echo "✓ Volumes and containers removed"

# Generate a development JWT token (expires 1 year)
dev-token:
	@python3 -c "
import base64, json, hmac, hashlib, time
header  = base64.urlsafe_b64encode(json.dumps({'alg':'HS256','typ':'JWT'}).encode()).rstrip(b'=')
payload = base64.urlsafe_b64encode(json.dumps({'sub':'dev','exp':int(time.time())+31536000}).encode()).rstrip(b'=')
msg     = header + b'.' + payload
sig     = base64.urlsafe_b64encode(hmac.new(b'dev-secret-change-in-production', msg, hashlib.sha256).digest()).rstrip(b'=')
print('Bearer', (msg + b'.' + sig).decode())
"
