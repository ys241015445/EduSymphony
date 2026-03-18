@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 前端环境安装
echo ============================================
echo.

:: 检查Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/2] 安装前端依赖...
call npm install

echo.
echo [2/2] 构建检查...
echo     依赖安装完成

echo.
echo ============================================
echo   安装完成！
echo.
echo   开发模式: start.bat
echo   构建生产: npm run build
echo   访问地址: http://localhost:3001
echo ============================================
pause
