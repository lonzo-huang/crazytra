# Crazytra 多租户 SaaS 架构设计

## 📋 目录

- [架构概览](#架构概览)
- [租户隔离方案](#租户隔离方案)
- [数据隔离策略](#数据隔离策略)
- [认证和授权](#认证和授权)
- [资源配额管理](#资源配额管理)
- [云端部署方案](#云端部署方案)
- [定价模型](#定价模型)
- [技术实现](#技术实现)

## 架构概览

### 单租户 vs 多租户

**当前（单租户）**：
```
用户 → 独立部署 → 独立数据库 → 独立 Redis
```

**多租户 SaaS**：
```
用户A ──┐
用户B ──┼→ 共享服务 → 逻辑隔离 → 共享基础设施
用户C ──┘
```

### 系统架构图

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (Cloudflare)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  API Gateway    │
                    │  + Auth Service │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ Tenant A│         │ Tenant B│         │ Tenant C│
   │ Namespace│        │ Namespace│        │ Namespace│
   └────┬────┘         └────┬────┘         └────┬────┘
        │                    │                    │
   ┌────▼─────────────────────▼────────────────────▼────┐
   │           Shared Infrastructure                     │
   │  Redis | TimescaleDB | Ollama | Kafka              │
   └─────────────────────────────────────────────────────┘
```

## 租户隔离方案

### 方案 1: 命名空间隔离（推荐）

**优点**：
- ✅ 成本效益高
- ✅ 资源利用率高
- ✅ 易于管理
- ✅ 快速扩展

**实现**：
```
Redis Key: tenant:{tenant_id}:market.tick.btcusdt
Database: tenant_a.positions, tenant_b.positions
Kafka Topic: tenant-a-signals, tenant-b-signals
```

### 方案 2: 数据库隔离

**优点**：
- ✅ 更强的数据隔离
- ✅ 更容易备份和恢复
- ✅ 符合某些合规要求

**实现**：
```sql
-- 每个租户独立数据库
CREATE DATABASE tenant_a_trading;
CREATE DATABASE tenant_b_trading;
```

### 方案 3: 完全隔离（企业级）

**优点**：
- ✅ 最强隔离
- ✅ 独立资源
- ✅ 自定义配置

**实现**：
```
Kubernetes Namespace per Tenant
独立的 Pod、Service、Ingress
```

## 数据隔离策略

### Redis 数据隔离

```go
// 租户前缀
func getTenantKey(tenantID, key string) string {
    return fmt.Sprintf("tenant:%s:%s", tenantID, key)
}

// 示例
tenant:abc123:market.tick.btcusdt
tenant:abc123:strategy.signal
tenant:abc123:order.event
tenant:xyz789:market.tick.btcusdt
```

### PostgreSQL 数据隔离

**方案 A: Schema 隔离**
```sql
-- 每个租户一个 Schema
CREATE SCHEMA tenant_abc123;
CREATE SCHEMA tenant_xyz789;

-- 表结构相同，数据隔离
CREATE TABLE tenant_abc123.positions (...);
CREATE TABLE tenant_xyz789.positions (...);
```

**方案 B: 行级隔离（RLS）**
```sql
-- 单表，用 tenant_id 区分
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    symbol VARCHAR(20),
    quantity DECIMAL,
    ...
);

-- 行级安全策略
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON positions
    USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

### Kafka/Redis Streams 隔离

```
# 方案 A: Topic 前缀
tenant-abc123-market-tick
tenant-abc123-signals
tenant-xyz789-market-tick

# 方案 B: 消费者组隔离
market.tick.btcusdt
  ├─ tenant-abc123-cg
  └─ tenant-xyz789-cg
```

## 认证和授权

### 认证流程

```
1. 用户登录
   ↓
2. 验证凭证（Email + Password / OAuth）
   ↓
3. 生成 JWT Token
   {
     "user_id": "user123",
     "tenant_id": "tenant_abc",
     "role": "admin",
     "permissions": ["trade", "view_reports"]
   }
   ↓
4. 返回 Token
   ↓
5. 后续请求携带 Token
   ↓
6. 中间件验证并提取 tenant_id
```

### JWT Token 结构

```json
{
  "sub": "user_123456",
  "tenant_id": "tenant_abc123",
  "tenant_name": "Acme Trading Co.",
  "role": "admin",
  "permissions": [
    "trade.execute",
    "strategy.manage",
    "reports.view",
    "settings.edit"
  ],
  "plan": "professional",
  "exp": 1700000000,
  "iat": 1699900000
}
```

### 权限模型

```
角色层级:
├─ Super Admin (平台管理员)
├─ Tenant Admin (租户管理员)
├─ Trader (交易员)
├─ Analyst (分析师)
└─ Viewer (只读用户)

权限矩阵:
                    Super  Tenant  Trader  Analyst  Viewer
                    Admin  Admin
创建租户              ✓      ✗       ✗       ✗       ✗
管理用户              ✓      ✓       ✗       ✗       ✗
执行交易              ✓      ✓       ✓       ✗       ✗
查看策略              ✓      ✓       ✓       ✓       ✗
修改策略              ✓      ✓       ✓       ✗       ✗
查看报告              ✓      ✓       ✓       ✓       ✓
修改配置              ✓      ✓       ✗       ✗       ✗
```

## 资源配额管理

### 配额类型

```go
type TenantQuota struct {
    TenantID          string
    Plan              string // free, starter, professional, enterprise
    
    // 交易配额
    MaxDailyTrades    int    // 每日最大交易次数
    MaxPositions      int    // 最大持仓数量
    MaxOrderValue     decimal.Decimal // 单笔订单最大金额
    
    // 数据配额
    MaxHistoryDays    int    // 历史数据保留天数
    MaxStrategies     int    // 最大策略数量
    MaxSymbols        int    // 可交易的交易对数量
    
    // 计算配额
    MaxCPU            float64 // CPU 核心数
    MaxMemory         int64   // 内存 MB
    MaxStorage        int64   // 存储 GB
    
    // API 配额
    MaxAPICallsPerMin int    // API 调用频率限制
    MaxWebSocketConns int    // WebSocket 连接数
    
    // 功能开关
    EnableLLM         bool   // 是否启用 LLM
    EnableBacktest    bool   // 是否启用回测
    EnableTelegram    bool   // 是否启用 Telegram Bot
}
```

### 配额检查中间件

```go
func QuotaMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        tenantID := r.Context().Value("tenant_id").(string)
        
        // 检查 API 调用配额
        if !checkAPIQuota(tenantID) {
            http.Error(w, "API quota exceeded", http.StatusTooManyRequests)
            return
        }
        
        // 检查并发连接配额
        if !checkConcurrentConnections(tenantID) {
            http.Error(w, "Connection limit exceeded", http.StatusTooManyRequests)
            return
        }
        
        next.ServeHTTP(w, r)
    })
}
```

## 云端部署方案

### 推荐云平台

#### 1. AWS 部署

```yaml
服务映射:
- ECS/EKS: 容器编排
- RDS PostgreSQL: 数据库
- ElastiCache Redis: 缓存和消息队列
- MSK (Kafka): 消息流
- S3: 对象存储
- CloudFront: CDN
- Route53: DNS
- ALB: 负载均衡
- Cognito: 用户认证
```

**成本估算（100 租户）**：
```
ECS Fargate: $200/月
RDS (db.t3.large): $150/月
ElastiCache (cache.t3.medium): $80/月
MSK (kafka.t3.small): $100/月
S3 + CloudFront: $50/月
ALB: $20/月
总计: ~$600/月
```

#### 2. Google Cloud Platform

```yaml
服务映射:
- GKE: Kubernetes
- Cloud SQL: PostgreSQL
- Memorystore: Redis
- Pub/Sub: 消息队列
- Cloud Storage: 对象存储
- Cloud CDN: CDN
- Cloud Load Balancing: 负载均衡
- Identity Platform: 认证
```

#### 3. Azure

```yaml
服务映射:
- AKS: Kubernetes
- Azure Database for PostgreSQL: 数据库
- Azure Cache for Redis: Redis
- Event Hubs: 消息流
- Blob Storage: 对象存储
- Azure CDN: CDN
- Application Gateway: 负载均衡
- Azure AD B2C: 认证
```

### Kubernetes 部署架构

```yaml
# 命名空间隔离
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-abc123
  labels:
    tenant: abc123
    plan: professional

---
# 资源配额
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: tenant-abc123
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    persistentvolumeclaims: "10"

---
# 网络策略
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-abc123
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: api-gateway
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: shared-services
```

## 定价模型

### 订阅计划

#### Free Plan（免费）
```
价格: $0/月
- 1 个策略
- 10 个交易对
- 7 天历史数据
- 100 次/天 API 调用
- 基础图表
- 社区支持
```

#### Starter Plan（入门）
```
价格: $29/月
- 3 个策略
- 50 个交易对
- 30 天历史数据
- 1,000 次/天 API 调用
- 高级图表
- Telegram 通知
- 邮件支持
```

#### Professional Plan（专业）
```
价格: $99/月
- 10 个策略
- 无限交易对
- 90 天历史数据
- 10,000 次/天 API 调用
- LLM 情感分析
- 回测功能
- Telegram Bot
- 优先支持
```

#### Enterprise Plan（企业）
```
价格: 定制
- 无限策略
- 无限交易对
- 无限历史数据
- 无限 API 调用
- 专属 LLM 实例
- 白标定制
- 独立部署
- 7x24 支持
- SLA 保证
```

### 计费模型

```go
type Billing struct {
    // 订阅费用
    SubscriptionFee decimal.Decimal
    
    // 使用量计费
    APICallsOverage decimal.Decimal // 超出配额的 API 调用
    StorageOverage  decimal.Decimal // 超出配额的存储
    
    // 附加服务
    AdditionalStrategies int         // 额外策略
    AdditionalUsers      int         // 额外用户
    
    // 总费用
    TotalMonthly decimal.Decimal
}

// 计费示例
func calculateBilling(tenant *Tenant, usage *Usage) *Billing {
    base := tenant.Plan.BasePrice
    
    // API 超量费用（每 1000 次 $0.10）
    apiOverage := decimal.Zero
    if usage.APICalls > tenant.Quota.MaxAPICallsPerMin * 30 * 24 * 60 {
        excess := usage.APICalls - tenant.Quota.MaxAPICallsPerMin * 30 * 24 * 60
        apiOverage = decimal.NewFromInt(excess / 1000).Mul(decimal.NewFromFloat(0.10))
    }
    
    return &Billing{
        SubscriptionFee: base,
        APICallsOverage: apiOverage,
        TotalMonthly:    base.Add(apiOverage),
    }
}
```

## 技术实现

### 租户管理服务

```go
// tenant-service/main.go
package main

type Tenant struct {
    ID            string          `json:"id"`
    Name          string          `json:"name"`
    Email         string          `json:"email"`
    Plan          string          `json:"plan"`
    Status        string          `json:"status"` // active, suspended, cancelled
    CreatedAt     time.Time       `json:"created_at"`
    SubscriptionEnd time.Time     `json:"subscription_end"`
    Quota         TenantQuota     `json:"quota"`
    Settings      TenantSettings  `json:"settings"`
}

type TenantSettings struct {
    TradingMode       string   `json:"trading_mode"` // paper, live
    DefaultExchange   string   `json:"default_exchange"`
    RiskLevel         string   `json:"risk_level"`
    NotificationEmail string   `json:"notification_email"`
    TelegramChatID    int64    `json:"telegram_chat_id"`
    Timezone          string   `json:"timezone"`
}

// 创建租户
func CreateTenant(req *CreateTenantRequest) (*Tenant, error) {
    tenant := &Tenant{
        ID:     generateTenantID(),
        Name:   req.Name,
        Email:  req.Email,
        Plan:   req.Plan,
        Status: "active",
        CreatedAt: time.Now(),
        SubscriptionEnd: time.Now().AddDate(0, 1, 0),
    }
    
    // 分配配额
    tenant.Quota = getQuotaForPlan(req.Plan)
    
    // 初始化租户资源
    if err := initializeTenantResources(tenant); err != nil {
        return nil, err
    }
    
    // 保存到数据库
    if err := db.Create(tenant).Error; err != nil {
        return nil, err
    }
    
    return tenant, nil
}

// 初始化租户资源
func initializeTenantResources(tenant *Tenant) error {
    // 创建 Redis 命名空间
    // 创建数据库 Schema
    // 创建 Kafka Topics
    // 分配存储空间
    // 发送欢迎邮件
    return nil
}
```

### 认证中间件

```go
// middleware/auth.go
func AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // 提取 JWT Token
        token := extractToken(r)
        if token == "" {
            http.Error(w, "Unauthorized", http.StatusUnauthorized)
            return
        }
        
        // 验证 Token
        claims, err := validateToken(token)
        if err != nil {
            http.Error(w, "Invalid token", http.StatusUnauthorized)
            return
        }
        
        // 检查租户状态
        tenant, err := getTenant(claims.TenantID)
        if err != nil || tenant.Status != "active" {
            http.Error(w, "Tenant inactive", http.StatusForbidden)
            return
        }
        
        // 注入上下文
        ctx := context.WithValue(r.Context(), "tenant_id", claims.TenantID)
        ctx = context.WithValue(ctx, "user_id", claims.UserID)
        ctx = context.WithValue(ctx, "role", claims.Role)
        
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### 数据访问层

```go
// dal/repository.go
type TenantAwareRepository struct {
    db *gorm.DB
}

func (r *TenantAwareRepository) Find(ctx context.Context, dest interface{}, conditions ...interface{}) error {
    tenantID := ctx.Value("tenant_id").(string)
    
    // 自动添加租户过滤
    return r.db.Where("tenant_id = ?", tenantID).
        Where(conditions...).
        Find(dest).Error
}

// 使用示例
positions := []Position{}
repo.Find(ctx, &positions, "symbol = ?", "BTC-USDT")
// SQL: SELECT * FROM positions WHERE tenant_id = 'abc123' AND symbol = 'BTC-USDT'
```

## 监控和运维

### 租户级别监控

```yaml
指标:
- 每租户 CPU/内存使用率
- 每租户 API 调用量
- 每租户交易量
- 每租户错误率
- 每租户响应时间

告警:
- 配额即将用尽（80%）
- 异常交易活动
- 服务降级
- 账单逾期
```

### 日志隔离

```json
{
  "timestamp": "2026-03-24T23:38:00Z",
  "tenant_id": "abc123",
  "user_id": "user456",
  "level": "INFO",
  "message": "Order executed",
  "order_id": "order789",
  "symbol": "BTC-USDT"
}
```

## 安全考虑

### 数据安全

1. **传输加密**: TLS 1.3
2. **存储加密**: AES-256
3. **密钥管理**: AWS KMS / HashiCorp Vault
4. **敏感数据**: API Key 加密存储

### 合规性

- **GDPR**: 数据删除、导出
- **SOC 2**: 审计日志
- **PCI DSS**: 支付信息隔离

## 迁移路径

### 从单租户到多租户

```
阶段 1: 准备
- 设计多租户架构
- 创建租户管理服务
- 实现认证系统

阶段 2: 数据迁移
- 添加 tenant_id 字段
- 迁移现有数据
- 更新查询逻辑

阶段 3: 部署
- 灰度发布
- 监控性能
- 优化调整

阶段 4: 上线
- 开放注册
- 营销推广
- 持续优化
```

## 总结

多租户 SaaS 化的优势：

✅ **成本优化**: 共享基础设施，降低单用户成本
✅ **快速扩展**: 新用户即开即用，无需部署
✅ **统一管理**: 集中式运维，降低管理成本
✅ **持续收入**: 订阅模式，稳定现金流
✅ **数据洞察**: 跨租户分析，优化产品

下一步建议：
1. 实现租户管理服务
2. 添加认证和授权系统
3. 配置云端基础设施
4. 设计定价和计费系统
5. 准备上线和营销
