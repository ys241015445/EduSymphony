#!/bin/bash

###
# EduSymphony 前端开发模式启动脚本
###

echo "🎨 启动前端开发服务器..."

# 进入前端目录
cd frontend

# 设置环境变量
export NEXT_PUBLIC_API_URL="http://localhost:8000"
export NEXT_PUBLIC_WS_URL="ws://localhost:8000"

# 使用轮询模式避免文件监视器问题（macOS）
export WATCHPACK_POLLING=true

echo "✅ 环境变量已设置"
echo ""
echo "📝 提示："
echo "   - 前端地址: http://localhost:3000"
echo "   - 修改代码后会自动热重载"
echo "   - 确保后端服务已启动在 http://localhost:8000"
echo ""

# 启动Next.js开发服务器
echo "🔧 启动Next.js开发服务器..."
npm run dev

