@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 前端启动 (开发模式)
echo ============================================
echo.

if not exist node_modules (
    echo [提示] 正在安装依赖...
    call npm install
)

echo 前端启动中... (端口 3001)
echo 访问: http://localhost:3001
echo 按 Ctrl+C 停止服务
echo.

call npm run dev
