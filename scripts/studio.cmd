@echo off
rem Point d entree du pipeline sous Windows (equivalent de scripts/studio).
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\pipeline;%PYTHONPATH%"
set "PYTHONUTF8=1"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m studio %*
) else (
  python -m studio %*
)
exit /b %errorlevel%
