@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 一键启动
echo ============================================
echo.
echo 将同时启动后端(8001)和前端(3002)
echo.

:: 启动后端
start "EduSymphony-Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && python -m uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload"

:: 等待后端启动
echo 等待后端启动...
timeout /t 5 /nobreak >nul

:: 启动前端
start "EduSymphony-Frontend" cmd /k "cd /d %~dp0frontend && npx vite --port 3002"

echo.
echo ============================================
echo   服务已启动！
echo.
echo   前端: http://localhost:3002
echo   后端: http://localhost:8001
echo   API文档: http://localhost:8001/docs
echo ============================================
echo.
echo 提示: 关闭此窗口不会影响已启动的服务
echo 要停止服务，请关闭对应的命令行窗口
pause
