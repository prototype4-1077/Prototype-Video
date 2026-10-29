@echo off
setlocal
cd /d "%~dp0"
python -m pipeline.cartoon_dialogue_scene --scene "concept/scenes/june-rest-your-hands-v1.json" %*
if errorlevel 1 (
  echo.
  echo New scene did not finish. Existing files were preserved.
  echo See docs\JUNE_DIALOGUE_SCENES.md.
  pause
  exit /b 1
)
echo.
echo New scene command finished. Review the details above.
pause
exit /b 0
