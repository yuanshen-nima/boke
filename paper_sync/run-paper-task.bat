@echo off
rem Runs paper sync only (no publish). Drafts wait for manual approve+publish.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" -m paper_sync sync >> "%PAPER_SYNC_DATA_DIR%\logs\task.log" 2>&1
