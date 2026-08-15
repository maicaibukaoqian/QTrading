@echo off
REM 一键安装所有 Python 依赖到 quant 环境

echo ========================================
REM A股量化项目 一键安装依赖
echo ========================================
echo.

call conda activate quant
if %errorlevel% neq 0 (
    echo 【错误】无法激活 quant conda 环境，请先确认已创建环境
    echo 如果还没创建环境，请先运行: conda create -n quant python=3.11 -y
    pause
    exit /b 1
)

echo 【安装依赖】pip install -r requirements.txt
echo.
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo ========================================
echo 依赖安装完成。
echo 接下来:
echo   python run_server.py   # 启动 API
echo   python main.py --help  # 查看 CLI 用法
echo ========================================
echo.

pause
