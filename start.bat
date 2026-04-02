@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 一键启动
echo ============================================
echo.
echo 将同时启动后端(3002)和前端(3000，与 vite.config 一致)
echo.

:: 启动后端（支持 .venv 或 venv，必须使用 socket_app 以启用 WebSocket）
start "EduSymphony-Backend" cmd /k "cd /d %~dp0backend && call dev_server.bat"

:: 等待后端启动
echo 等待后端启动...
timeout /t 5 /nobreak >nul

:: 启动前端（端口以 frontend\vite.config.ts 为准，默认 3000）
start "EduSymphony-Frontend" cmd /k "cd /d %~dp0frontend && npx vite"

echo.
echo ============================================
echo   服务已启动！
echo.
echo   前端: http://localhost:3000
echo   后端: http://localhost:3002
echo   API文档: http://localhost:3002/docs
echo ============================================
echo.
echo 提示: 关闭此窗口不会影响已启动的服务
echo 要停止服务，请关闭对应的命令行窗口
pause
