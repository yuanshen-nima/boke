@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON=D:\develop_tool\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================================
echo  Starting PaperSync Local Server on port 8765...
echo  Endpoint: http://127.0.0.1:8765/api/inbox
echo  Close this window to stop the server.
echo ========================================================

"%PYTHON%" -m paper_sync serve --port 8765
if errorlevel 1 (
    echo.
    echo [ERROR] Server stopped with exit code %ERRORLEVEL%.
    pause
)
