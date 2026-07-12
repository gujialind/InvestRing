#!/bin/bash

echo "============================================="
echo "        InvestRing 一键启动脚本"
echo "============================================="

# 检查是否安装了 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 未检测到 Node.js，请先安装 Node.js"
    exit 1
fi

# 检查是否安装了 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未检测到 Python3，请先安装 Python"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 启动后端服务
echo ""
echo "🚀 启动后端服务..."
cd backend

# 创建并激活虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# 安装依赖
echo "📦 安装后端依赖..."
pip install -q -r requirements.txt

# 加载 .env 环境变量并启动 uvicorn
if [ -f ".env" ]; then
    echo "📋 加载环境变量..."
    export $(grep -v '^#' .env | xargs)
fi

# 验证环境变量
if [ -n "$TUSHARE_TOKEN" ]; then
    echo "✅ Tushare Token 已配置"
else
    echo "⚠️ Tushare Token 未配置"
fi

# 启动 uvicorn
env TUSHARE_TOKEN="$TUSHARE_TOKEN" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &> ../logs/backend.log &
BACKEND_PID=$!
echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"
echo "📝 后端日志: logs/backend.log"
echo "🌐 后端地址: http://localhost:8000"

deactivate 2>/dev/null || true

cd ..

# 等待后端启动
sleep 3

# 启动前端服务
echo ""
echo "🚀 启动前端服务..."
cd frontend

# 检查并安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install -q
fi

# 启动 Next.js
npm run dev &> ../logs/frontend.log &
FRONTEND_PID=$!
echo "✅ 前端服务已启动 (PID: $FRONTEND_PID)"
echo "📝 前端日志: logs/frontend.log"
echo "🌐 前端地址: http://localhost:3000"

cd ..

echo ""
echo "============================================="
echo "        服务启动完成！"
echo "============================================="
echo ""
echo "后端服务: http://localhost:8000"
echo "前端服务: http://localhost:3000"
echo "API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
wait $FRONTEND_PID $BACKEND_PID
