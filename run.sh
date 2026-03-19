#!/bin/bash
# ETH Monitor 启动脚本

echo "🚀 启动 ETH Monitor..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt -q

# 启动应用
echo "✅ 启动 Streamlit 应用..."
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
