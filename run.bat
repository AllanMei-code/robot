@echo off
chcp 65001 >nul
REM 设置终端编码为 UTF-8，避免中文乱码

REM 自动跳转到本脚本所在目录
cd /d %~dp0

echo.
echo [🔍] 检查 Python 是否安装...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ❌ 未检测到 Python，请安装后再运行。
    pause
    exit /b
)
echo ✅ Python 已安装，正在启动 Flask 服务...
python main.py
REM 进入 app 文件夹
cd app

echo.
echo [🚀] 正在启动 Flask 本地服务...
echo ========================
python main.py
echo ========================

echo.
echo [❗] 如果看到报错，请复制错误内容发我，我可以帮你诊断。
pause
