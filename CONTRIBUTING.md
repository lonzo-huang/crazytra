# MirrorQuant - 开发者贡献指南

欢迎为 MirrorQuant 项目做出贡献！

---

## 🎯 贡献方式

### 1. 报告 Bug
- 使用 GitHub Issues
- 提供详细的复现步骤
- 包含错误日志和截图

### 2. 提出新功能
- 先在 Issues 中讨论
- 说明功能的价值和用例
- 提供设计方案（可选）

### 3. 提交代码
- Fork 项目
- 创建功能分支
- 提交 Pull Request

---

## 🛠️ 开发环境设置

### 必需工具

```bash
# 检查版本
python --version  # 3.11+
node --version    # 18+
go version        # 1.22+
docker --version  # 最新版
```

### 克隆项目

```bash
git clone https://github.com/your-username/mirrorquant.git
cd mirrorquant
```

### 安装依赖

```bash
# Python 依赖
cd nautilus-core
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install

# Go 依赖
cd ../api-gateway
go mod download
```

---

## 📝 代码规范

### Python (PEP 8)

```python
# 好的示例
def fetch_market_data(market_id: str, limit: int = 100) -> List[Dict]:
    """
    获取市场数据
    
    Args:
        market_id: 市场 ID
        limit: 返回数量限制
        
    Returns:
        市场数据列表
    """
    pass

# 避免
def fetchData(id,lim=100):  # 不符合 PEP 8
    pass
```

### TypeScript/React

```typescript
// 好的示例
interface Market {
  id: string;
  question: string;
  volume: number;
}

export function MarketCard({ market }: { market: Market }) {
  return <div>{market.question}</div>;
}

// 避免
function card(m: any) {  // 缺少类型，命名不清晰
  return <div>{m.q}</div>;
}
```

### Go

```go
// 好的示例
type Handler struct {
    redisClient *redis.Client
}

func (h *Handler) GetMarkets(c *gin.Context) {
    // 实现
}

// 避免
func getmarkets(c *gin.Context) {  // 命名不符合 Go 规范
    // 实现
}
```

---

## 🔀 Git 工作流

### 分支命名

```bash
# 功能分支
feature/add-binance-integration
feature/improve-search

# 修复分支
fix/polymarket-data-format
fix/websocket-connection

# 文档分支
docs/update-readme
docs/add-api-guide
```

### 提交信息

```bash
# 格式：<type>: <subject>

# 类型
feat: 新功能
fix: 修复
docs: 文档
style: 格式
refactor: 重构
test: 测试
chore: 构建/工具

# 示例
feat: add Binance market integration
fix: resolve Polymarket data parsing error
docs: update installation guide
refactor: simplify market data adapter
```

### 提交流程

```bash
# 1. 创建分支
git checkout -b feature/your-feature

# 2. 开发和提交
git add .
git commit -m "feat: add your feature"

# 3. 推送
git push origin feature/your-feature

# 4. 创建 Pull Request
# 在 GitHub 上创建 PR
```

---

## 🧪 测试

### Python 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_polymarket_adapter.py

# 生成覆盖率报告
pytest --cov=nautilus-core
```

### 前端测试

```bash
# 运行测试
npm test

# 运行 E2E 测试
npm run test:e2e
```

### Go 测试

```bash
# 运行测试
go test ./...

# 运行特定包测试
go test ./handlers
```

---

## 📦 添加新功能

### 1. 添加新的市场集成

#### 步骤

1. **创建适配器**
   ```python
   # nautilus-core/adapters/new_market_adapter.py
   class NewMarketAdapter:
       def __init__(self, redis_url: str):
           self.redis_client = redis.from_url(redis_url)
       
       async def fetch_markets(self):
           # 实现
           pass
   ```

2. **添加 API 端点**
   ```go
   // api-gateway/handlers/new_market.go
   func (h *Handler) GetNewMarkets(c *gin.Context) {
       // 实现
   }
   ```

3. **创建前端组件**
   ```typescript
   // frontend/src/components/NewMarketPanel.tsx
   export function NewMarketPanel() {
       // 实现
   }
   ```

4. **更新文档**
   - 更新 README.md
   - 创建集成指南
   - 更新 ARCHITECTURE.md

### 2. 添加新的策略

```python
# nautilus-core/strategies/my_strategy.py
from nautilus_trader.trading.strategy import Strategy

class MyStrategy(Strategy):
    def on_start(self):
        # 初始化
        pass
    
    def on_data(self, data):
        # 处理数据
        pass
    
    def on_stop(self):
        # 清理
        pass
```

---

## 🎨 UI/UX 指南

### 设计原则

1. **一致性** - 使用统一的颜色、字体、间距
2. **简洁性** - 避免不必要的元素
3. **响应式** - 支持各种屏幕尺寸
4. **可访问性** - 支持键盘导航和屏幕阅读器

### 颜色方案

```css
/* 主色调 */
--primary: #a855f7;      /* 紫色 */
--secondary: #3b82f6;    /* 蓝色 */
--success: #10b981;      /* 绿色 */
--danger: #ef4444;       /* 红色 */
--warning: #f59e0b;      /* 橙色 */

/* 背景色 */
--bg-primary: #030712;   /* 深灰 */
--bg-secondary: #111827; /* 灰色 */
--bg-tertiary: #1f2937;  /* 浅灰 */

/* 文字色 */
--text-primary: #f9fafb;   /* 白色 */
--text-secondary: #9ca3af; /* 灰色 */
```

### 组件示例

```typescript
// 按钮组件
<button className="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-lg transition-colors">
  Click Me
</button>

// 输入框
<input 
  className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
  placeholder="Search..."
/>

// 卡片
<div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
  Content
</div>
```

---

## 📚 文档规范

### 代码注释

```python
def complex_function(param1: str, param2: int) -> Dict:
    """
    简短描述函数功能
    
    详细说明函数的行为、参数和返回值
    
    Args:
        param1: 参数1的说明
        param2: 参数2的说明
        
    Returns:
        返回值的说明
        
    Raises:
        ValueError: 什么情况下抛出
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'key': 'value'}
    """
    pass
```

### README 结构

```markdown
# 项目名称

简短描述

## 功能特性

- 功能1
- 功能2

## 快速开始

安装和使用说明

## API 文档

端点说明

## 贡献

如何贡献

## 许可

许可信息
```

---

## 🔍 代码审查清单

### 提交 PR 前检查

- [ ] 代码符合规范
- [ ] 添加了必要的测试
- [ ] 测试全部通过
- [ ] 更新了相关文档
- [ ] 没有引入新的警告
- [ ] 提交信息清晰
- [ ] 分支基于最新的 main

### 审查者检查

- [ ] 代码逻辑正确
- [ ] 性能可接受
- [ ] 安全性考虑
- [ ] 错误处理完善
- [ ] 代码可维护
- [ ] 文档完整

---

## 🚀 发布流程

### 版本号规范

遵循语义化版本 (Semantic Versioning)：

- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

示例：`v1.2.3`

### 发布步骤

1. **更新版本号**
   ```bash
   # 更新 package.json, setup.py 等
   ```

2. **更新 CHANGELOG**
   ```markdown
   ## [1.2.3] - 2026-03-28
   
   ### Added
   - 新功能
   
   ### Fixed
   - 修复的问题
   
   ### Changed
   - 变更的内容
   ```

3. **创建标签**
   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

4. **构建和发布**
   ```bash
   # Docker 镜像
   docker build -t mirrorquant:v1.2.3 .
   docker push mirrorquant:v1.2.3
   ```

---

## 💡 最佳实践

### 1. 保持简单
- 优先选择简单的解决方案
- 避免过度设计
- 代码应该易于理解

### 2. 测试驱动
- 先写测试，后写代码
- 保持高测试覆盖率
- 测试应该快速且可靠

### 3. 持续集成
- 频繁提交小的改动
- 保持主分支稳定
- 自动化测试和部署

### 4. 文档优先
- 代码即文档
- 保持文档更新
- 提供清晰的示例

### 5. 安全第一
- 验证所有输入
- 使用参数化查询
- 加密敏感数据
- 定期更新依赖

---

## 📞 获取帮助

### 社区资源

- **GitHub Issues** - 报告问题和讨论
- **文档** - 查看项目文档
- **示例** - 参考示例代码

### 联系方式

- 项目维护者：[GitHub Profile]
- 邮件：support@mirrorquant.com

---

## 📄 许可

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

**感谢你的贡献！** 🎉
