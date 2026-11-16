@echo off
rem Point d entree du pipeline sous Windows (equivalent de scripts/studio). Exige Python 3.11+.
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\pipeline;%PYTHONPATH%"
set "PYTHONUTF8=1"
set "PYEXE="
if defined STUDIO_PYTHON set "PYEXE=%STUDIO_PYTHON%"
if not defined PYEXE for %%V in (3.13 3.12 3.11) do (
  if not defined PYEXE (
    py -%%V -c "import sys" >NUL 2>&1 && set "PYEXE=py -%%V"
  )
)
if not defined PYEXE (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >NUL 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
  echo [studio] Python 3.11 ou plus recent est requis ^(Python 3.12 conseille^).
  echo [studio] Installez-le :  winget install --id Python.Python.3.12 -e
  echo [studio] puis :           py -3.12 -m pip install -r requirements.txt
  exit /b 1
)
%PYEXE% -m studio %*
exit /b %errorlevel%
