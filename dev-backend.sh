#!/bin/bash

###
# EduSymphony 后端开发模式启动脚本
###

echo "🚀 启动后端开发服务器..."

# 进入后端目录
cd backend

# 设置环境变量
export DATABASE_URL="mysql+aiomysql://edusymphony:edusymphony123@localhost:3306/edusymphony"
export REDIS_URL="redis://localhost:6379/0"
export CHROMA_HOST="localhost"
export CHROMA_PORT="8001"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin123"
export JWT_SECRET="test_jwt_secret_key_for_development"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-test}"
export QWEN_API_KEY="${QWEN_API_KEY:-sk-test}"
export APP_ENV="development"
export APP_DEBUG="true"
export LOG_LEVEL="DEBUG"
export CORS_ORIGINS="http://localhost,http://localhost:3000"

echo "✅ 环境变量已设置"
echo ""
echo "📝 提示："
echo "   - API地址: http://localhost:8000"
echo "   - API文档: http://localhost:8000/docs"
echo "   - 修改代码后会自动重载"
echo ""
echo "🔑 如需使用AI功能，请设置真实的API密钥："
echo "   export OPENAI_API_KEY=your_real_key"
echo "   export QWEN_API_KEY=your_real_key"
echo ""

# 激活conda环境并启动
echo "🔧 启动uvicorn服务器（开发模式）..."
conda run -n edusymphony uvicorn app.main:application --reload --host 0.0.0.0 --port 8000

