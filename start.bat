@echo off
chcp 65001 >nul
title Natter CloudFlare SRV Updater

echo ========================================
echo   Natter CloudFlare SRV 自动更新器
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 config.yaml 是否存在
if not exist config.yaml (
    echo [警告] 未找到 config.yaml 配置文件
    echo.
    echo 请按照以下步骤操作:
    echo 1. 复制 config.example.yaml 为 config.yaml
    echo 2. 编辑 config.yaml 并填入你的配置
    echo 3. 重新运行本脚本
    echo.
    pause
    exit /b 1
)

REM 检查 natter.py 是否存在
if not exist natter.py (
    echo [错误] 未找到 natter.py
    echo 请确保 natter.py 在当前目录下
    pause
    exit /b 1
)

REM 检查 requests 库
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖: requests
    pip install requests
    if errorlevel 1 (
        echo [错误] 安装依赖失败
        pause
        exit /b 1
    )
)

REM 检查 pyyaml 库
python -c "import yaml" >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖: pyyaml
    pip install pyyaml
    if errorlevel 1 (
        echo [错误] 安装依赖失败
        pause
        exit /b 1
    )
)

echo [启动] 正在启动 Natter CloudFlare Updater...
echo.
python natter_cloudflare.py

pause
