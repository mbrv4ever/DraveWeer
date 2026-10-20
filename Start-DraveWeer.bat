@echo off
rem === Start-DraveWeer.bat - start de weer-app ===
cd /d "%~dp0"

set "PY="
for %%V in (3.11 3.12 3.10 3.13) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY ( echo Geen Python gevonden. Installeer Python 3.11 of 3.12. & pause & exit /b 1 )

rem PyQt6 aanwezig? anders installeren
%PY% -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
  echo PyQt6 installeren ^(eenmalig^)...
  %PY% -m pip install PyQt6
)

start "" %PY% "%~dp0draveweer.py"
