@echo off
setlocal
title Classroom Companion
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0tools\compose\run_unified_desktop.ps1" %*
if errorlevel 1 (
    echo Classroom Companion could not start. Review the message above.
    pause
    exit /b 1
)
exit /b 0
