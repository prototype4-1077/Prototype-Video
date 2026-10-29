@echo off
setlocal
cd /d "%~dp0"
python -m pipeline.cartoon_working_model %*
if errorlevel 1 (
  echo.
  echo Prototype build did not finish. Existing files were preserved.
  echo See docs\JUNE_WORKING_MODEL.md for local setup and troubleshooting.
  pause
  exit /b 1
)
echo.
echo Finished. The output path is printed above.
pause
exit /b 0
