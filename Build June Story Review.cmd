@echo off
setlocal
cd /d "%~dp0"
python -m pipeline.cartoon_story_review %*
set "JUNE_STORY_STATUS=%errorlevel%"
if not "%JUNE_STORY_STATUS%"=="0" echo Story review did not finish. Existing output was preserved.
if "%~1"=="" pause
exit /b %JUNE_STORY_STATUS%
