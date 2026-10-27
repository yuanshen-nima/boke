@echo off
title PaperSync 本地接收服务 (端口: 8765)
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
echo ========================================================
echo  启动 PaperSync 本地接收服务（供 ChatGPT 油猴脚本推送）
echo  端点: http://127.0.0.1:8765/api/inbox
echo  关闭窗口即可停止服务
echo ========================================================
"%PYTHON%" -m paper_sync serve --port 8765
pause
