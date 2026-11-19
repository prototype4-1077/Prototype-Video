@echo off
setlocal
cd /d "%~dp0"
python -m pipeline.cartoon_full_short_source %*
if errorlevel 1 (
  echo.
  echo Full-short build did not finish. Existing files were preserved.
  echo See docs\JUNE_FULL_SHORT_SOURCE.md for setup and troubleshooting.
  pause
  exit /b 1
)
echo.
echo Finished. The output path is printed above.
pause
exit /b 0
