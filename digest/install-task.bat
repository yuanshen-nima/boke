@echo off
rem Register Windows scheduled tasks:
rem   - BlogDailyDigest       daily 23:30  (main digest)
rem   - BlogDailyDigestRetry  daily 08:00  (catch-up push / retry)
rem Usage: install-task.bat [HH:MM for main task]
set "TASK_TIME=%1"
if "%TASK_TIME%"=="" set "TASK_TIME=23:30"
schtasks /Create /F /TN "BlogDailyDigest" /SC DAILY /ST %TASK_TIME% /TR "\"%~dp0run_daily.bat\""
schtasks /Create /F /TN "BlogDailyDigestRetry" /SC DAILY /ST 08:00 /TR "\"%~dp0run_daily.bat\""
echo.
echo Tasks registered: BlogDailyDigest at %TASK_TIME%, BlogDailyDigestRetry at 08:00.
echo Verify:   schtasks /Query /TN BlogDailyDigest  ^&  schtasks /Query /TN BlogDailyDigestRetry
echo Remove:   schtasks /Delete /TN BlogDailyDigest /F  ^&  schtasks /Delete /TN BlogDailyDigestRetry /F
pause
