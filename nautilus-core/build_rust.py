#!/usr/bin/env python3
"""
构建 Rust 模块脚本
编译 Rust 代码为 Python 可导入的模块
"""

import os
import subprocess
import sys
from pathlib import Path

def build_rust_module():
    """构建 Rust 模块"""
    rust_dir = Path(__file__).parent / "rust"
    
    if not rust_dir.exists():
        print("❌ Rust 目录不存在")
        return False
    
    print("🔨 开始构建 Rust 模块...")
    
    # 切换到 Rust 目录
    original_cwd = os.getcwd()
    os.chdir(rust_dir)
    
    try:
        # 检查是否安装了 maturin
        try:
            subprocess.run(["maturin", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("📦 安装 maturin...")
            subprocess.run([sys.executable, "-m", "pip", "install", "maturin"], check=True)
        
        # 构建 Rust 模块
        print("🔧 编译 Rust 代码...")
        result = subprocess.run([
            "maturin", "build", "--release", "--out", "../target/wheels"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Rust 模块构建成功!")
        print(f"📦 输出: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    
    finally:
        os.chdir(original_cwd)

def install_rust_module():
    """安装 Rust 模块"""
    print("📦 安装 Rust 模块...")
    
    wheel_dir = Path(__file__).parent / "target" / "wheels"
    if not wheel_dir.exists():
        print("❌ 找不到编译好的 wheel 文件")
        return False
    
    # 查找 wheel 文件
    wheel_files = list(wheel_dir.glob("*.whl"))
    if not wheel_files:
        print("❌ 没有找到 wheel 文件")
        return False
    
    wheel_file = wheel_files[0]
    print(f"📦 安装: {wheel_file}")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", str(wheel_file), "--force-reinstall"
        ], check=True)
        print("✅ Rust 模块安装成功!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 MirrorQuant Rust 模块构建器")
    print("=" * 50)
    
    # 构建 Rust 模块
    if not build_rust_module():
        print("❌ 构建失败")
        return 1
    
    # 安装 Rust 模块
    if not install_rust_module():
        print("❌ 安装失败")
        return 1
    
    print("\n🎉 Rust 模块构建和安装完成!")
    print("💡 现在可以在 Python 中导入: from nautilus_core.rust import PolymarketDataEngine")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
