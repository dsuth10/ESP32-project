@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not exist "tools\compose\.venv\Scripts\python.exe" (
    "%PY%" -m venv "tools\compose\.venv"
    if errorlevel 1 goto failed
)
"tools\compose\.venv\Scripts\python.exe" -m pip install -r "tools\compose\requirements.txt"
if errorlevel 1 goto failed
call "%~dp0start_companion_feature.bat"
exit /b 0
:failed
echo Feature setup failed. Review the message above. The live companion and firmware were not changed.
pause
exit /b 1
