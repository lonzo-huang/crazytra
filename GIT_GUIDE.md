# Git 提交指南

## 快速提交

### 方式 A: 使用提交脚本（推荐）

**Linux/macOS:**
```bash
chmod +x scripts/git_commit.sh
./scripts/git_commit.sh
```

**Windows PowerShell:**
```powershell
.\scripts\git_commit.ps1
```

### 方式 B: 手动提交

```bash
# 1. 查看状态
git status

# 2. 添加所有文件
git add .

# 3. 提交
git commit -m "feat: Nautilus Trader 整合完成"

# 4. 推送到远程（如果已配置）
git push origin main
```

## 首次设置 GitHub 远程仓库

### 1. 在 GitHub 创建仓库

访问 https://github.com/new 创建新仓库：
- 仓库名: `MirrorQuant`
- 描述: `智能自动交易系统 - Nautilus Trader 整合`
- 可见性: Private（推荐）或 Public
- **不要**勾选 "Initialize this repository with a README"

### 2. 添加远程仓库

```bash
# 添加远程仓库
git remote add origin https://github.com/your-username/MirrorQuant.git

# 验证
git remote -v

# 推送到远程
git push -u origin main
```

### 3. 使用 SSH（可选，更安全）

```bash
# 生成 SSH 密钥（如果还没有）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 添加到 ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# 复制公钥到 GitHub
cat ~/.ssh/id_ed25519.pub
# 在 GitHub Settings > SSH and GPG keys 中添加

# 使用 SSH URL
git remote set-url origin git@github.com:your-username/MirrorQuant.git
```

## 本次提交内容

本次提交包含 **Nautilus Trader 完整整合**：

### 新增文件

**Nautilus 核心:**
- `nautilus-core/` - 完整的 Nautilus 整合模块
  - `actors/redis_bridge.py` - Nautilus → Redis 桥接
  - `actors/llm_weight_actor.py` - LLM 权重注入
  - `strategies/base_strategy.py` - MirrorQuantStrategy 基类
  - `strategies/ma_cross_llm.py` - 示例策略（均线+LLM）
  - `main.py` - 主入口
  - `config.py` - Nautilus 配置
  - `tests/test_integration.py` - 集成测试

**脚本:**
- `nautilus-core/scripts/verify_integration.py` - 自动化验证脚本
- `nautilus-core/scripts/run_verification.sh` - Linux/macOS 启动器
- `nautilus-core/scripts/run_verification.ps1` - Windows 启动器
- `scripts/git_commit.sh` - Git 提交助手（Linux/macOS）
- `scripts/git_commit.ps1` - Git 提交助手（Windows）

**文档:**
- `nautilus-core/README.md` - Nautilus 整合详细文档
- `nautilus-core/QUICKSTART.md` - 5分钟快速开始
- `nautilus-core/TESTING.md` - 完整测试指南
- `INSTALLATION.md` - 完整安装指南
- `GIT_GUIDE.md` - 本文件

**配置:**
- `.gitignore` - Git 忽略规则
- `nautilus-core/.env.example` - 环境变量模板
- `nautilus-core/requirements.txt` - Python 依赖

### 更新文件

- `README.md` - 更新为 Nautilus 整合架构
- `ARCHITECTURE.md` - 添加 Nautilus 整合章节
- `INSTALLATION.md` - 添加验证步骤

### 关键特性

✅ **Nautilus Trader 1.204.0** - 专业级交易引擎  
✅ **RedisBridgeActor** - 确保前端零修改  
✅ **LLMWeightActor** - LLM 权重实时注入  
✅ **MirrorQuantStrategy** - 支持 LLM 增强的策略基类  
✅ **完整测试系统** - 6 项自动化验证  
✅ **详细文档** - 安装、测试、快速开始  

## 提交信息模板

```
feat: Nautilus Trader 整合完成

- 整合 Nautilus Trader 1.204.0 作为核心交易引擎
- 实现 RedisBridgeActor 桥接 Nautilus 与 Redis
- 实现 LLMWeightActor 支持 LLM 权重注入
- 创建 MirrorQuantStrategy 基类支持 LLM 增强
- 添加完整的测试验证系统
- 更新所有文档（ARCHITECTURE.md, INSTALLATION.md, README.md）
- 保持 Redis Streams 作为外部系统桥接
- 前端和 API 网关零修改

详细文档:
- nautilus-core/README.md - Nautilus 整合文档
- nautilus-core/QUICKSTART.md - 5分钟快速开始
- nautilus-core/TESTING.md - 测试指南
- INSTALLATION.md - 完整安装指南
```

## 常见问题

### Q: 如何查看提交历史？

```bash
git log --oneline --graph --all
```

### Q: 如何撤销最后一次提交？

```bash
# 保留更改
git reset --soft HEAD~1

# 丢弃更改
git reset --hard HEAD~1
```

### Q: 如何创建新分支？

```bash
# 创建并切换到新分支
git checkout -b feature/new-feature

# 推送新分支到远程
git push -u origin feature/new-feature
```

### Q: 如何合并分支？

```bash
# 切换到主分支
git checkout main

# 合并功能分支
git merge feature/new-feature

# 推送
git push origin main
```

## 下一步

提交完成后：

1. **验证整合** - 运行 `python nautilus-core/scripts/verify_integration.py`
2. **测试系统** - 启动 Nautilus 节点并测试
3. **继续开发** - 实现 Polymarket 适配器或 LLM 层

---

**最后更新**: 2026-03-23  
**版本**: v1.0.0 (Nautilus 整合版)
