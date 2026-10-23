@echo off
rem === bouw-exe.bat - bouwt DraveWeer naar dist\DraveWeer\DraveWeer.exe ===
setlocal
cd /d "%~dp0"

set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY ( echo Geen Python gevonden. Installeer Python 3.11 of 3.12. & pause & exit /b 1 )

if not exist ".venv" ( %PY% -m venv .venv )
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install PyQt6 pyinstaller

echo.
echo === Bouwen met PyInstaller... ===
pyinstaller --noconfirm draveweer.spec

echo.
echo Klaar! Start:  dist\DraveWeer\DraveWeer.exe
echo (Maak hiervan een snelkoppeling op je bureaublad als je wilt.)
echo.
pause
endlocal
