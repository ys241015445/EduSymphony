@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 后端启动
echo ============================================

if not exist .venv (
    echo [错误] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo 后端启动中... (端口 8001)
echo API文档: http://localhost:8001/docs
echo 按 Ctrl+C 停止服务
echo.

python -m uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload
