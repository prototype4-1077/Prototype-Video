@echo off
setlocal
cd /d "%~dp0"
python -m pipeline.cartoon_current_review %*
set "JUNE_BUILD_STATUS=%errorlevel%"
if not "%JUNE_BUILD_STATUS%"=="0" echo Build did not finish. Existing output was preserved.
if "%~1"=="" pause
exit /b %JUNE_BUILD_STATUS%
