@echo off
chcp 65001 >nul
echo ========================================
echo 教案格式转换服务 - 安装脚本
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python未安装
    echo 💡 请从 https://www.python.org/downloads/ 下载安装Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python环境正常
echo.

echo [2/4] 升级pip...
python -m pip install --upgrade pip
echo.

echo [3/4] 安装Python依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    echo 💡 如果WeasyPrint安装失败，可以先跳过，后续再安装
    echo.
    pause
)
echo ✅ 依赖安装完成
echo.

echo [4/4] 创建配置文件...
if not exist ".env" (
    copy .env.example .env
    echo ✅ 已创建.env文件
    echo.
    echo ⚠️  请编辑.env文件，填入Qwen API密钥:
    echo    QWEN_API_KEY=sk-your-api-key-here
    echo.
) else (
    echo ℹ️  .env文件已存在，跳过创建
    echo.
)

echo ========================================
echo ✅ 安装完成！
echo ========================================
echo.
echo 下一步:
echo 1. 编辑 .env 文件，填入Qwen API密钥
echo 2. 运行 start.bat 启动服务
echo 3. 打开浏览器访问 format_converter.html
echo.
pause
