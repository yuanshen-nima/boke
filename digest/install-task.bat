@echo off
rem Register the Windows scheduled task. Default 23:30 daily.
rem Usage: install-task.bat [HH:MM]
set "TASK_TIME=%1"
if "%TASK_TIME%"=="" set "TASK_TIME=23:30"
schtasks /Create /F /TN "BlogDailyDigest" /SC DAILY /ST %TASK_TIME% /TR "\"%~dp0run_daily.bat\""
echo.
echo Scheduled task "BlogDailyDigest" registered at %TASK_TIME% every day.
echo Verify:   schtasks /Query /TN BlogDailyDigest
echo Remove:   schtasks /Delete /TN BlogDailyDigest /F
pause
