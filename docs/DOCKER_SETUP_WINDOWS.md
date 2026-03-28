# Docker Desktop 安装指南（Windows）

## 检测结果

✅ WSL 已安装
❌ Docker 未安装

## 安装步骤

### 第一步：下载 Docker Desktop

**官方下载地址**：
https://www.docker.com/products/docker-desktop/

或者直接下载：
https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe

### 第二步：安装 Docker Desktop

1. **运行安装程序**
   - 双击 `Docker Desktop Installer.exe`
   - 如果弹出 UAC 提示，点击"是"

2. **配置选项**
   - ✅ 勾选 "Use WSL 2 instead of Hyper-V"（推荐）
   - ✅ 勾选 "Add shortcut to desktop"
   - 点击 "OK" 开始安装

3. **等待安装完成**
   - 安装时间约 5-10 分钟
   - 安装完成后会提示重启电脑

4. **重启电脑**
   - 点击 "Close and restart"

### 第三步：首次启动 Docker Desktop

1. **启动 Docker Desktop**
   - 从桌面或开始菜单启动
   - 首次启动会进行初始化配置

2. **接受服务条款**
   - 阅读并接受 Docker 服务条款

3. **登录（可选）**
   - 可以跳过登录，直接使用
   - 或者创建 Docker Hub 账号

4. **完成设置**
   - 等待 Docker Engine 启动
   - 状态栏显示 "Docker Desktop is running" 即可

### 第四步：验证安装

打开 PowerShell，运行以下命令：

```powershell
# 检查 Docker 版本
docker --version

# 检查 Docker Compose 版本
docker compose version

# 运行测试容器
docker run hello-world
```

**预期输出**：
```
Docker version 24.0.x, build xxxxx
Docker Compose version v2.x.x

Hello from Docker!
This message shows that your installation appears to be working correctly.
```

## 常见问题

### 问题 1：WSL 2 未安装或未启用

**症状**：
```
WSL 2 installation is incomplete.
```

**解决方案**：

1. 启用 WSL 功能：
```powershell
# 以管理员身份运行 PowerShell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

2. 重启电脑

3. 下载并安装 WSL 2 内核更新包：
https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi

4. 设置 WSL 2 为默认版本：
```powershell
wsl --set-default-version 2
```

### 问题 2：虚拟化未启用

**症状**：
```
Hardware assisted virtualization and data execution protection must be enabled in the BIOS.
```

**解决方案**：

1. 重启电脑，进入 BIOS（通常按 F2, F10, Del 键）
2. 找到虚拟化选项：
   - Intel: Intel VT-x 或 Intel Virtualization Technology
   - AMD: AMD-V 或 SVM Mode
3. 启用虚拟化
4. 保存并退出 BIOS

### 问题 3：Hyper-V 冲突

**症状**：
```
Hyper-V is not available on Home editions.
```

**解决方案**：

使用 WSL 2 后端（推荐）：
1. 卸载 Docker Desktop
2. 重新安装，确保选择 "Use WSL 2 instead of Hyper-V"

### 问题 4：Docker Desktop 无法启动

**症状**：
Docker Desktop 一直显示 "Starting..."

**解决方案**：

1. 完全退出 Docker Desktop
2. 打开 PowerShell（管理员），运行：
```powershell
# 停止所有 Docker 服务
Stop-Service docker
Stop-Service com.docker.service

# 清理 Docker 数据
Remove-Item -Path "$env:APPDATA\Docker" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:LOCALAPPDATA\Docker" -Recurse -Force -ErrorAction SilentlyContinue

# 重启 Docker Desktop
```

3. 重新启动 Docker Desktop

## Docker Desktop 配置优化

### 资源配置

1. 打开 Docker Desktop
2. 点击右上角设置图标 ⚙️
3. 进入 "Resources" → "Advanced"

**推荐配置**：
```
CPUs: 4（根据你的 CPU 核心数调整）
Memory: 8 GB（至少 4 GB）
Swap: 2 GB
Disk image size: 60 GB
```

### WSL 2 集成

1. 进入 "Resources" → "WSL Integration"
2. 启用你想使用的 WSL 发行版
3. 点击 "Apply & Restart"

### Docker Compose

Docker Desktop 已内置 Docker Compose V2，无需额外安装。

验证：
```powershell
docker compose version
```

## 下一步：启动 MirrorQuant

安装完成后，你可以启动 MirrorQuant 项目：

### 方案 1：使用一键启动脚本（推荐）

```powershell
# Windows PowerShell
cd d:\projects\MirrorQuant
.\start-dev.ps1
```

### 方案 2：手动启动

```powershell
# 1. 启动后端服务
docker compose up -d

# 2. 启动前端（新终端）
cd frontend
npm run dev
```

### 方案 3：只启动前端

```powershell
.\start-frontend.ps1
```

## 验证 MirrorQuant 环境

启动后，访问以下地址验证：

- **前端**: http://localhost:5173
- **API 网关**: http://localhost:8080/health
- **Redis**: localhost:6379
- **TimescaleDB**: localhost:5432

## 常用 Docker 命令

```powershell
# 查看运行中的容器
docker ps

# 查看所有容器（包括停止的）
docker ps -a

# 查看容器日志
docker logs <container_name>

# 进入容器
docker exec -it <container_name> sh

# 停止所有容器
docker compose down

# 停止并删除所有数据
docker compose down -v

# 重启容器
docker compose restart

# 查看资源使用情况
docker stats
```

## 故障排查

### 检查 Docker 服务状态

```powershell
# 检查 Docker Desktop 是否运行
Get-Process "Docker Desktop" -ErrorAction SilentlyContinue

# 检查 Docker Engine 状态
docker info
```

### 查看 Docker Desktop 日志

1. 打开 Docker Desktop
2. 点击右上角 🐛 图标
3. 选择 "Troubleshoot"
4. 查看日志

### 重置 Docker Desktop

如果遇到严重问题：

1. 打开 Docker Desktop
2. 设置 → "Troubleshoot"
3. 点击 "Reset to factory defaults"
4. 确认重置

**警告**：这会删除所有容器、镜像和数据！

## 性能优化建议

### 1. 使用 WSL 2 后端

WSL 2 比 Hyper-V 性能更好：
- 启动更快
- 资源占用更少
- 文件系统性能更好

### 2. 将项目放在 WSL 文件系统中

如果使用 WSL 2，将项目放在 WSL 文件系统中性能更好：

```bash
# 在 WSL 中
cd ~
git clone https://github.com/lonzo-huang/mirrorquant.git
cd mirrorquant
```

然后在 Windows 中访问：
```
\\wsl$\Ubuntu\home\<username>\mirrorquant
```

### 3. 配置 Docker 镜像加速

编辑 Docker Desktop 设置：
```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

## 卸载 Docker Desktop

如果需要卸载：

1. 打开 "设置" → "应用"
2. 找到 "Docker Desktop"
3. 点击 "卸载"
4. 删除残留文件：
```powershell
Remove-Item -Path "$env:APPDATA\Docker" -Recurse -Force
Remove-Item -Path "$env:LOCALAPPDATA\Docker" -Recurse -Force
```

## 参考资料

- [Docker Desktop 官方文档](https://docs.docker.com/desktop/windows/install/)
- [WSL 2 安装指南](https://docs.microsoft.com/en-us/windows/wsl/install)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [MirrorQuant 项目文档](../README.md)

## 获取帮助

如果遇到问题：

1. 查看 Docker Desktop 日志
2. 搜索 Docker 官方论坛
3. 查看 MirrorQuant 项目 Issues
4. 联系技术支持

---

**安装完成后，请运行验证命令，然后告诉我结果！**
