@echo off
chcp 65001 >nul
echo ========================================
echo 教案格式转换服务 - 启动脚本
echo ========================================
echo.

echo [1/3] 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python未安装，请先安装Python 3.8+
    pause
    exit /b 1
)

echo.
echo [2/3] 检查依赖...
if not exist ".env" (
    echo ⚠️  .env文件不存在，使用默认配置
    echo 💡 如需使用Qwen API，请复制.env.example为.env并填入API密钥
)

echo.
echo [3/3] 启动服务...
echo 📡 服务地址: http://localhost:8000
echo 🌐 前端页面: format_converter.html
echo 💡 按 Ctrl+C 停止服务
echo.
echo ========================================
echo.

python run.py
