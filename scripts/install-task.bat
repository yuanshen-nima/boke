@echo off
rem 注册 Windows 定时任务：每日 21:00 自动提交并推送到 GitHub
rem 使用方法：install-task.bat [时间，如 21:00]
set "TASK_TIME=%1"
if "%TASK_TIME%"=="" set "TASK_TIME=21:00"

schtasks /Create /F /TN "BokeAutoGitPushDaily" /SC DAILY /ST %TASK_TIME% /TR "\"%~dp0run_auto_git_sync.bat\""

echo.
echo 定时任务 "BokeAutoGitPushDaily" 已成功注册，将在每日 %TASK_TIME% 自动运行。
echo 查看任务：schtasks /Query /TN BokeAutoGitPushDaily
echo 删除任务：schtasks /Delete /TN BokeAutoGitPushDaily /F
echo.
pause
