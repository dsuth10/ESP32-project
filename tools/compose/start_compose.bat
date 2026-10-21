@echo off
title ESP32 and Windows Compose Companion
cd /d "%~dp0"

echo =======================================================
echo   Starting the ESP32 classroom companion
echo   This window also starts the voice receiver.
echo =======================================================

rem Work PC keeps its packages on Python 3.12. This machine uses 3.13.
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY set "PY=python"

"%PY%" compose_gui.py

if errorlevel 1 (
    echo Companion failed. Review the error above.
    pause
)
exit /b 0
