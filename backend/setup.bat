@echo off
chcp 65001 >nul
echo ============================================
echo   EduSymphony 后端环境安装
echo ============================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 创建 Python 虚拟环境...
if not exist .venv (
    python -m venv .venv
    echo     虚拟环境创建成功
) else (
    echo     虚拟环境已存在，跳过
)

echo.
echo [2/4] 激活虚拟环境并安装依赖...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo [3/4] 配置环境变量...
if not exist .env (
    copy .env.example .env
    echo     已创建 .env 文件，请编辑填入你的 API Key
    echo     文件位置: %cd%\.env
) else (
    echo     .env 文件已存在，跳过
)

echo.
echo [4/4] 创建数据目录...
if not exist database mkdir database
if not exist database\files mkdir database\files
echo     数据目录就绪

echo.
echo ============================================
echo   安装完成！
echo.
echo   启动后端: start.bat 或 dev_server.bat
echo   API文档:  http://localhost:3002/docs
echo.
echo   重要: 请先编辑 .env 文件填入 QWEN_API_KEY
echo ============================================
pause
