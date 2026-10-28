param([string]$PythonExecutable = '')
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$setupArguments = @{}
if ($PythonExecutable) { $setupArguments.PythonExecutable = $PythonExecutable }
& (Join-Path $PSScriptRoot 'setup_teaching_board_candidate.ps1') @setupArguments
if ($LASTEXITCODE -ne 0) { throw 'Board environment setup failed; voice dependencies were not changed.' }
$environmentRoot = Join-Path $repositoryRoot '.local/teaching-board-renderer-env'
$pythonPath = Join-Path $environmentRoot 'Scripts/python.exe'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'The isolated Board environment is missing.' }
# The Board setup validates links and its own environment. This explicit setup
# adds the voice dependencies there; ordinary launch performs no installation.
Write-Output 'Installing Voice Companion dependencies into the isolated desktop environment.'
& $pythonPath -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'The isolated environment could not prepare pip. Existing user data was preserved.' }
& $pythonPath -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Voice dependency installation failed. Existing lesson and companion data was preserved; check package-index access and rerun setup.' }
& $pythonPath -m pip check
if ($LASTEXITCODE -ne 0) { throw 'The isolated package set needs attention. Existing user data was preserved.' }
& $pythonPath -c 'import PySide6, tkinter, PIL, reportlab, win32gui, win32clipboard, uiautomation, sounddevice, numpy, scipy, faster_whisper, requests, groq, serial'
if ($LASTEXITCODE -ne 0) { throw 'A desktop dependency could not be imported. Existing user data was preserved.' }
Write-Output 'Classroom Companion is ready. Open start_companion.bat for the shared teacher window.'
