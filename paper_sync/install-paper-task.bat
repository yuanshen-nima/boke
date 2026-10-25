@echo off
rem Register daily paper-sync task (sync only, never auto-publish). Default 21:00.
rem Usage: install-paper-task.bat [HH:MM]
set "TASK_TIME=%1"
if "%TASK_TIME%"=="" set "TASK_TIME=21:00"
schtasks /Create /F /TN "PaperSyncDaily" /SC DAILY /ST %TASK_TIME% /TR "\"%~dp0run-paper-task.bat\""
echo Scheduled task "PaperSyncDaily" registered at %TASK_TIME%.
pause
