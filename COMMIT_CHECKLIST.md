# 提交前检查清单

在提交到 GitHub 之前，请确认以下事项：

## ✅ 必须检查项

### 1. 敏感信息检查

- [ ] 确认 `.env` 文件已在 `.gitignore` 中
- [ ] 确认没有 API keys 在代码中硬编码
- [ ] 确认没有密码或私钥在代码中
- [ ] 检查 `.gitignore` 文件存在且正确

**验证命令：**
```bash
# 检查是否有敏感文件会被提交
git status | grep -E "\.env|\.key|\.pem|secret"

# 查看 .gitignore
cat .gitignore | grep -E "\.env|\.key|secret"
```

### 2. 文件完整性检查

- [ ] 所有新增的 Python 文件都有正确的导入
- [ ] 所有配置文件都有 `.example` 版本
- [ ] README.md 已更新
- [ ] ARCHITECTURE.md 已更新
- [ ] INSTALLATION.md 已更新

**验证命令：**
```bash
# 检查新增文件
git status

# 检查是否有 .env.example
ls -la nautilus-core/.env.example
```

### 3. 代码质量检查

- [ ] Python 代码没有语法错误
- [ ] 导入语句正确
- [ ] 没有未使用的导入

**验证命令：**
```bash
# Python 语法检查
python -m py_compile nautilus-core/main.py
python -m py_compile nautilus-core/actors/redis_bridge.py
python -m py_compile nautilus-core/actors/llm_weight_actor.py

# 或使用 flake8（如果安装）
# flake8 nautilus-core/ --count --select=E9,F63,F7,F82 --show-source
```

### 4. 文档检查

- [ ] 所有 Markdown 文件格式正确
- [ ] 代码示例可以运行
- [ ] 链接没有断开

**验证命令：**
```bash
# 检查 Markdown 文件
ls -la *.md nautilus-core/*.md

# 检查链接（手动）
grep -r "\[.*\](.*)" *.md
```

## ✅ 推荐检查项

### 5. 测试验证

- [ ] 验证脚本可以运行
- [ ] 单元测试通过（如果有）

**验证命令：**
```bash
cd nautilus-core

# 检查验证脚本语法
python -m py_compile scripts/verify_integration.py

# 运行测试（如果 Redis 在运行）
# python scripts/verify_integration.py
```

### 6. 依赖文件检查

- [ ] requirements.txt 存在且完整
- [ ] 版本号固定（避免依赖冲突）

**验证命令：**
```bash
cat nautilus-core/requirements.txt
```

### 7. 脚本权限检查

- [ ] Shell 脚本有执行权限（Linux/macOS）

**验证命令：**
```bash
# 添加执行权限
chmod +x scripts/git_commit.sh
chmod +x nautilus-core/scripts/run_verification.sh
chmod +x nautilus-core/scripts/start.sh
```

## 📋 提交步骤

### 步骤 1: 初始化 Git（如果还没有）

```bash
git init
```

### 步骤 2: 检查状态

```bash
git status
```

### 步骤 3: 添加文件

```bash
# 添加所有文件
git add .

# 或使用脚本
./scripts/git_commit.sh  # Linux/macOS
# 或
.\scripts\git_commit.ps1  # Windows
```

### 步骤 4: 提交

```bash
git commit -m "feat: Nautilus Trader 整合完成

- 整合 Nautilus Trader 1.204.0 作为核心交易引擎
- 实现 RedisBridgeActor 桥接 Nautilus 与 Redis
- 实现 LLMWeightActor 支持 LLM 权重注入
- 创建 CrazytraStrategy 基类支持 LLM 增强
- 添加完整的测试验证系统
- 更新所有文档
"
```

### 步骤 5: 添加远程仓库（首次）

```bash
# 在 GitHub 创建仓库后
git remote add origin https://github.com/your-username/Crazytra.git

# 验证
git remote -v
```

### 步骤 6: 推送

```bash
# 首次推送
git push -u origin main

# 后续推送
git push
```

## 🚨 常见错误处理

### 错误 1: "fatal: not a git repository"

```bash
# 解决：初始化 Git
git init
```

### 错误 2: "error: failed to push some refs"

```bash
# 解决：先拉取远程更改
git pull origin main --rebase
git push origin main
```

### 错误 3: ".env 文件被提交"

```bash
# 解决：从 Git 中移除但保留本地文件
git rm --cached .env
git rm --cached nautilus-core/.env

# 确保 .gitignore 包含 .env
echo ".env" >> .gitignore

# 重新提交
git add .gitignore
git commit -m "fix: 移除 .env 文件"
```

### 错误 4: "large files warning"

```bash
# 解决：使用 Git LFS（如果有大文件）
git lfs install
git lfs track "*.parquet"
git lfs track "*.db"
git add .gitattributes
```

## 📊 提交后验证

```bash
# 查看提交历史
git log --oneline -5

# 查看远程状态
git remote -v

# 查看分支
git branch -a

# 在 GitHub 上验证
# 访问 https://github.com/your-username/Crazytra
```

## 🎯 下一步

提交完成后：

1. ✅ 在 GitHub 上查看仓库
2. ✅ 添加仓库描述和标签
3. ✅ 设置仓库可见性（Private/Public）
4. ✅ 添加 LICENSE 文件（推荐 MIT）
5. ✅ 启用 GitHub Actions（可选）

---

**准备好了吗？运行提交脚本：**

```bash
# Linux/macOS
./scripts/git_commit.sh

# Windows
.\scripts\git_commit.ps1
```

或手动执行上述步骤。
