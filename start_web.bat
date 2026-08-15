@echo off
REM A股量化交易 API 一键启动脚本

echo ========================================
echo    A股量化交易 API 启动
echo ========================================
echo.

REM 启动 FastAPI 服务
python run_server.py

pause
