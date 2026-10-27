@echo off
rem Daily digest + backup entry point. Called by Windows scheduled tasks (install-task.bat).
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if not exist work mkdir work
set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" run.py >> work\run.log 2>&1
"%PYTHON%" backup.py >> work\run.log 2>&1
