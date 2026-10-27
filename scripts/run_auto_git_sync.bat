@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

"%PYTHON%" scripts\auto_git_sync.py
