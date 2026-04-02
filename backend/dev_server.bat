@echo off
chcp 65001 >nul
cd /d %~dp0

if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
) else (
  echo [错误] 未找到虚拟环境 .venv 或 venv
  echo 请在 backend 目录运行: python -m venv .venv
  echo 然后: .venv\Scripts\activate.bat ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)

echo.
echo 后端启动: http://127.0.0.1:3002  ^(含 Socket.IO，请使用 app.main:socket_app^)
echo 按 Ctrl+C 停止
echo.

python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 3002 --reload
