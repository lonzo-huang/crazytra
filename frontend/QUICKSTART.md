# 前端快速启动指南

## 前置要求

- **Node.js 18+**
- **npm 或 yarn**

## 快速开始

### 方法 1：自动配置（推荐）

**Windows:**
```powershell
cd frontend
.\setup.ps1
```

**Linux/macOS:**
```bash
cd frontend
chmod +x setup.sh
./setup.sh
```

### 方法 2：手动配置

```bash
cd frontend

# 1. 创建环境变量文件
cp .env.example .env

# 2. 编辑 .env 文件（可选）
# VITE_API_URL=http://localhost:8080
# VITE_WS_URL=ws://localhost:8080/ws

# 3. 安装依赖
npm install

# 4. 启动开发服务器
npm run dev
```

## 访问应用

开发服务器启动后，访问：

**http://localhost:5173**

## 环境变量说明

### `.env` 文件配置

```bash
# API 服务器地址
VITE_API_URL=http://localhost:8080

# WebSocket 服务器地址
VITE_WS_URL=ws://localhost:8080/ws

# 环境（development/production）
VITE_ENV=development

# 功能开关
VITE_ENABLE_MOCK_DATA=false  # 启用模拟数据
VITE_ENABLE_DEBUG=true       # 启用调试模式
```

### 不同环境配置

**本地开发（默认）:**
```bash
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080/ws
```

**连接远程服务器:**
```bash
VITE_API_URL=http://your-server.com:8080
VITE_WS_URL=ws://your-server.com:8080/ws
```

**使用 HTTPS:**
```bash
VITE_API_URL=https://your-server.com
VITE_WS_URL=wss://your-server.com/ws
```

## 可用命令

```bash
# 启动开发服务器（热重载）
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 类型检查
npm run type-check

# 代码格式化
npm run format

# 代码检查
npm run lint
```

## 开发服务器配置

开发服务器默认配置：

- **端口**: 5173
- **主机**: localhost
- **热重载**: 启用
- **HTTPS**: 禁用（可在 vite.config.ts 中配置）

### 修改端口

编辑 `vite.config.ts`:

```typescript
export default defineConfig({
  server: {
    port: 3000, // 自定义端口
  },
});
```

或使用命令行参数：

```bash
npm run dev -- --port 3000
```

## 功能验证

### 1. 检查 API 连接

打开浏览器控制台，应该看到：

```
[WebSocket] Connecting to ws://localhost:8080/ws
[WebSocket] Connected
```

### 2. 检查实时数据

如果后端服务正在运行，你应该看到：

- 实时价格更新
- WebSocket 连接状态
- 图表数据流动

### 3. 模拟数据模式

如果后端未运行，可以启用模拟数据：

```bash
# .env
VITE_ENABLE_MOCK_DATA=true
```

## 故障排查

### 问题 1: 端口被占用

**错误**: `Port 5173 is already in use`

**解决**:
```bash
# 使用不同端口
npm run dev -- --port 3000
```

### 问题 2: 依赖安装失败

**错误**: `npm install` 失败

**解决**:
```bash
# 清除缓存
npm cache clean --force

# 删除 node_modules
rm -rf node_modules package-lock.json

# 重新安装
npm install
```

### 问题 3: WebSocket 连接失败

**错误**: `WebSocket connection failed`

**检查**:
1. API 网关是否运行（`http://localhost:8080`）
2. `.env` 中的 `VITE_WS_URL` 是否正确
3. 防火墙设置

### 问题 4: TypeScript 错误

**错误**: 大量 TypeScript 类型错误

**解决**:
```bash
# 确保依赖已安装
npm install

# 重启 IDE/编辑器
# 重启开发服务器
```

### 问题 5: 样式不显示

**错误**: TailwindCSS 样式不生效

**解决**:
```bash
# 检查 tailwind.config.js
# 重启开发服务器
npm run dev
```

## 目录结构

```
frontend/
├── src/
│   ├── components/      # UI 组件
│   │   ├── PriceChart.tsx
│   │   ├── TickerCard.tsx
│   │   └── OrderBook.tsx
│   ├── hooks/          # React Hooks
│   │   └── useWebSocket.ts
│   ├── pages/          # 页面组件
│   │   ├── Dashboard.tsx
│   │   ├── Orders.tsx
│   │   └── ...
│   ├── services/       # 服务
│   │   └── websocket.ts
│   ├── store/          # 状态管理
│   │   └── tradeStore.ts
│   ├── App.tsx
│   └── main.tsx
├── public/             # 静态资源
├── .env                # 环境变量（本地）
├── .env.example        # 环境变量模板
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## 开发工作流

### 1. 启动后端服务

```bash
# 在项目根目录
docker-compose up -d
```

### 2. 启动前端

```bash
cd frontend
npm run dev
```

### 3. 开发

- 修改代码会自动热重载
- 浏览器控制台查看日志
- 使用 React DevTools 调试

### 4. 构建部署

```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 性能优化建议

### 开发环境

1. **使用快速刷新**: Vite 默认启用
2. **减少不必要的重渲染**: 使用 React.memo
3. **优化 WebSocket 连接**: 避免频繁订阅/取消订阅

### 生产环境

1. **代码分割**: 使用动态 import
2. **图片优化**: 使用 WebP 格式
3. **启用 Gzip**: Nginx 配置已包含
4. **CDN 加速**: 静态资源使用 CDN

## 调试技巧

### 1. React DevTools

安装浏览器扩展：
- Chrome: React Developer Tools
- Firefox: React Developer Tools

### 2. WebSocket 调试

浏览器控制台 → Network → WS 标签

### 3. 状态调试

```typescript
// 在组件中
const state = useTradeStore();
console.log('Current state:', state);
```

### 4. 性能分析

```bash
# 使用 React Profiler
import { Profiler } from 'react';

<Profiler id="Dashboard" onRender={callback}>
  <Dashboard />
</Profiler>
```

## 下一步

- 📖 阅读 [README.md](./README.md) 了解详细功能
- 🔌 查看 [WebSocket 文档](./docs/WEBSOCKET.md)
- 🎨 自定义主题和样式
- 🚀 部署到生产环境

## 获取帮助

- **文档**: `frontend/README.md`
- **WebSocket**: `frontend/docs/WEBSOCKET.md`
- **Issues**: https://github.com/lonzo-huang/crazytra/issues
