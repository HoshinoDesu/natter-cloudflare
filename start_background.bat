@echo off
chcp 65001 >nul
title Natter CloudFlare SRV Updater (后台模式)

echo ========================================
echo   后台启动 Natter CloudFlare Updater
echo ========================================
echo.

REM 检查配置文件
if not exist config.yaml (
    echo [错误] 未找到 config.yaml 配置文件
    echo 请先运行 start.bat 进行初始化
    pause
    exit /b 1
)

REM 后台启动
start /b pythonw natter_cloudflare.py

echo [完成] Natter CloudFlare Updater 已在后台启动
echo.
echo 提示:
echo - 脚本正在后台运行，无窗口显示
echo - 要停止脚本，请在任务管理器中结束 pythonw.exe 进程
echo - 或者重启计算机
echo.

timeout /t 3 >nul
