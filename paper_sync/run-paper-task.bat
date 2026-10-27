@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

"%PYTHON%" -m paper_sync sync >> "%PAPER_SYNC_DATA_DIR%\logs\task.log" 2>&1
