#!/bin/bash

###
# EduSymphony 部署脚本
# 一键部署整个系统
###

set -e

echo "🚀 开始部署 EduSymphony..."

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装Docker，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    echo "❌ 未安装Docker Compose，请先安装"
    exit 1
fi

# 检查env文件
if [ ! -f ".env" ]; then
    echo "📝 创建.env文件..."
    cp env.example .env
    echo "⚠️  请编辑.env文件，配置必要的环境变量（API密钥等）"
    read -p "按回车继续..."
fi

# 停止现有容器
echo "🛑 停止现有容器..."
docker-compose down 2>/dev/null || true

# 构建镜像
echo "🔨 构建Docker镜像..."
docker-compose build

# 启动服务
echo "🎬 启动服务..."
docker-compose up -d

# 等待服务就绪
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
docker-compose ps

# 初始化数据库
echo "🗄️  初始化数据库..."
docker-compose exec -T backend python -c "
from app.core.database import engine, Base
import asyncio

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✅ 数据库表创建完成')

asyncio.run(init_db())
" || echo "⚠️  数据库可能已初始化"

# 初始化教学模型
echo "📚 初始化教学模型..."
docker-compose exec -T backend python app/scripts/init_teaching_models.py || echo "⚠️  教学模型可能已初始化"

# 初始化参考资料（需要Chroma服务）
echo "📖 初始化参考资料..."
sleep 5  # 等待Chroma启动
docker-compose exec -T backend python app/scripts/init_references.py || echo "⚠️  参考资料初始化失败，请稍后手动运行"

echo ""
echo "✅ 部署完成！"
echo ""
echo "📌 服务访问地址："
echo "   前端: http://localhost:3000"
echo "   后端API: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo "   MinIO控制台: http://localhost:9001 (默认账号: minioadmin/minioadmin123)"
echo ""
echo "📝 查看日志："
echo "   docker-compose logs -f"
echo ""
echo "🛑 停止服务："
echo "   docker-compose down"
echo ""
