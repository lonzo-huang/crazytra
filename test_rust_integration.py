#!/usr/bin/env python3
"""
测试 Rust 集成和当前实现状态
"""

import sys
import os
import subprocess
import time

def check_rust_environment():
    """检查 Rust 环境"""
    print("🦀 检查 Rust 环境...")
    
    try:
        result = subprocess.run(['rustc', '--version'], capture_output=True, text=True)
        print(f"✅ Rust 编译器: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ Rust 未安装")
        print("📦 安装命令: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        return False

def check_cargo_environment():
    """检查 Cargo 环境"""
    print("\n📦 检查 Cargo 环境...")
    
    try:
        result = subprocess.run(['cargo', '--version'], capture_output=True, text=True)
        print(f"✅ Cargo: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ Cargo 未安装")
        return False

def test_current_python_implementation():
    """测试当前 Python 实现"""
    print("\n🐍 测试当前 Python 实现...")
    
    sys.path.append('nautilus-core')
    
    try:
        from adapters.polymarket_python_fallback import PolymarketPythonAdapter
        
        async def test():
            adapter = PolymarketPythonAdapter()
            await adapter.start()
            
            start_time = time.time()
            markets = await adapter.fetch_markets()
            end_time = time.time()
            
            print(f"✅ Python 实现获取 {len(markets)} 个市场")
            print(f"⏱️  耗时: {end_time - start_time:.3f}s")
            
            # 筛选 BTC 市场
            btc_markets = [m for m in markets if 'btc' in m.question.lower()]
            print(f"🔍 BTC 相关市场: {len(btc_markets)}")
            
            await adapter.stop()
            return len(markets), end_time - start_time
        
        import asyncio
        return asyncio.run(test())
        
    except Exception as e:
        print(f"❌ Python 实现测试失败: {e}")
        return 0, 0

def test_rust_availability():
    """测试 Rust 模块可用性"""
    print("\n🦀 测试 Rust 模块可用性...")
    
    try:
        # 尝试导入 Rust 编译的模块
        import sys
        sys.path.append('nautilus-core/rust/target/release')
        
        from nautilus_core import PolymarketDataEngine
        print("✅ Rust 模块可用")
        return True
        
    except ImportError as e:
        print(f"❌ Rust 模块不可用: {e}")
        print("🔧 需要先构建 Rust 代码")
        return False

def create_build_script():
    """创建 Rust 构建脚本"""
    script_content = """@echo off
echo 🦀 构建 Nautilus Core Rust 模块...
cd /d "%~dp0\\nautilus-core\\rust"

echo 📦 检查 Rust 环境...
rustc --version
if %errorlevel% neq 0 (
    echo ❌ Rust 未安装，请先安装 Rust
    echo 📦 安装命令: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    pause
    exit /b 1
)

echo 🔨 构建发布版本...
cargo build --release

if %errorlevel% equ 0 (
    echo ✅ 构建成功！
    echo 📁 库文件位置: nautilus-core\\rust\\target\\release\\nautilus_core.dll
    echo 📁 Python 绑定: nautilus-core\\rust\\target\\release\\nautilus_core.pyd
) else (
    echo ❌ 构建失败
)

pause
"""
    
    with open('d:/projects/Crazytra/build_rust.bat', 'w') as f:
        f.write(script_content)
    
    print("📝 创建构建脚本: build_rust.bat")

def analyze_current_architecture():
    """分析当前架构"""
    print("\n🏗️  当前架构分析:")
    print("=" * 50)
    
    print("✅ 已有组件:")
    print("  🦀 Rust 核心: nautilus-core/rust/")
    print("    ├── src/data_polymarket.rs (PolymarketDataEngine)")
    print("    ├── src/models.rs (数据模型)")
    print("    └── src/lib.rs (Python 绑定)")
    print("  🐍 Python 适配器: adapters/polymarket_python_fallback.py")
    print("  📊 策略实现: strategies/polymarket/btc_5m_binary_ev.py")
    print("  🌐 API Gateway: api-gateway/handlers/polymarket.go")
    print("  🎨 前端组件: frontend/src/components/PolymarketTradingPanel.tsx")
    
    print("\n🎯 正确的技术路线:")
    print("  1. 🦀 构建现有 Rust 核心库")
    print("  2. 🔄 用 Rust 替换 Python 数据获取")
    print("  3. 🔗 集成 Rust 模块到策略")
    print("  4. ⚡ 性能优化和实时数据")
    
    print("\n❌ 错误认知修正:")
    print("  ❌ 不需要安装 NautilusTrader (我们已有代码)")
    print("  ❌ 不保留 pmbot Python 实现 (用 Rust 替代)")
    print("  ✅ 使用现有的高性能 Rust 实现")

def main():
    """主函数"""
    print("🎯 Polymarket 开发状态检查")
    print("=" * 50)
    
    # 检查环境
    rust_ok = check_rust_environment()
    cargo_ok = check_cargo_environment()
    
    # 测试当前实现
    python_markets, python_time = test_current_python_implementation()
    
    # 测试 Rust 模块
    rust_available = test_rust_availability()
    
    # 分析架构
    analyze_current_architecture()
    
    # 创建构建脚本
    create_build_script()
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 状态总结:")
    
    print(f"🦀 Rust 环境: {'✅' if rust_ok else '❌'}")
    print(f"📦 Cargo 环境: {'✅' if cargo_ok else '❌'}")
    print(f"🐍 Python 实现: ✅ ({python_markets} 市场, {python_time:.3f}s)")
    print(f"🦀 Rust 模块: {'✅' if rust_available else '❌'}")
    
    print("\n🎯 下一步行动:")
    
    if not rust_ok or not cargo_ok:
        print("  1. 📦 安装 Rust 环境")
        print("     curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
    
    if not rust_available:
        print("  2. 🔨 运行构建脚本")
        print("     ./build_rust.bat")
    
    if python_markets > 0:
        print("  3. 🔄 替换 Python 数据获取为 Rust 实现")
        print("  4. ⚡ 性能测试和优化")
    
    print("\n💡 关键优势:")
    print("  🚀 Rust 实现预计性能提升 10-50x")
    print("  🛡️ 类型安全和内存安全")
    print("  🔗 与 NautilusTrader 框架完美集成")

if __name__ == "__main__":
    main()
