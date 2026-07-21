@echo off
REM ============================================================
REM 一键全栈部署（双击本文件即可）
REM 等价命令：powershell -ExecutionPolicy Bypass -File .\deploy.ps1
REM 会自动：拉起 Docker Desktop -> docker compose up -d --build 全栈
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1"
echo.
echo 按任意键关闭本窗口...
pause >nul
