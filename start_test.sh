#!/bin/bash

###
# EduSymphony 快速测试启动脚本
###

set -e

echo "🚀 启动 EduSymphony 测试环境..."

# 设置测试环境变量
export MYSQL_ROOT_PASSWORD=rootpassword123
export MYSQL_PASSWORD=edusymphony123
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123
export JWT_SECRET=test_jwt_secret_key_for_development_only_please_change
export OPENAI_API_KEY=${OPENAI_API_KEY:-sk-test-placeholder}
export QWEN_API_KEY=${QWEN_API_KEY:-sk-test-placeholder}

echo "📝 环境变量已设置"
echo ""
echo "⚠️  注意: 当前使用测试密钥，AI功能需要配置真实API密钥"
echo "   如需使用AI功能，请设置环境变量:"
echo "   export OPENAI_API_KEY=your_real_key"
echo "   export QWEN_API_KEY=your_real_key"
echo ""

# 创建必要目录
mkdir -p mysql_data minio_data logs backend/logs

# 停止旧容器
echo "🛑 停止旧容器..."
docker compose down 2>/dev/null || true

# 构建镜像
echo "🔨 构建Docker镜像..."
docker compose build

# 启动服务
echo "🎬 启动服务..."
docker compose up -d

# 等待服务就绪
echo "⏳ 等待服务启动（30秒）..."
sleep 30

# 检查服务状态
echo ""
echo "🔍 检查服务状态..."
docker compose ps

echo ""
echo "✅ 服务启动完成！"
echo ""
echo "📌 访问地址："
echo "   前端: http://localhost:3000"
echo "   后端API: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo "   MinIO控制台: http://localhost:9001 (minioadmin/minioadmin123)"
echo ""
echo "📝 查看日志："
echo "   docker compose logs -f backend"
echo "   docker compose logs -f frontend"
echo ""
echo "🛑 停止服务："
echo "   docker compose down"
echo ""
echo "⚠️  首次启动可能需要几分钟来初始化数据库和下载依赖"
echo ""

