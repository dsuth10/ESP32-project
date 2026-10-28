param(
    [string]$DataRoot = '',
    [string]$CompanionDataRoot = '',
    [string]$BoardSettingsRoot = '',
    [string]$LibraryRoot = '',
    [string]$PythonExecutable = '',
    [string]$CompanionPythonExecutable = '',
    [switch]$Demo,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
function Test-PythonImports([string]$Executable, [string]$Expression) {
    try {
        $probeOutput = & $Executable -c $Expression 2>&1
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $repositoryRoot '.local/teaching-board-renderer-env/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw 'Run tools/compose/setup_unified_desktop.ps1 first. Normal launch does not install packages or download models.'
}
if (-not $CompanionPythonExecutable) {
    # Reuse an already installed companion interpreter when the Board environment
    # has only its own dependencies. This keeps normal launch read-only.
    $candidates = @($PythonExecutable, (Join-Path $PSScriptRoot '.venv/Scripts/python.exe'),
                    'C:\Python312\python.exe', 'C:\Python313\python.exe')
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($systemPython) { $candidates += $systemPython.Source }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        if (Test-PythonImports $candidate 'import tkinter, win32gui, win32clipboard, uiautomation, sounddevice, numpy, scipy, faster_whisper, requests, groq, serial, PIL') {
            $CompanionPythonExecutable = $candidate; break
        }
    }
    if (-not $CompanionPythonExecutable) { throw 'Voice dependencies are missing. Run tools/compose/setup_unified_desktop.ps1.' }
}
if (-not (Test-Path -LiteralPath $CompanionPythonExecutable -PathType Leaf)) {
    throw 'The selected voice companion Python executable is missing.'
}
if (-not (Test-PythonImports $PythonExecutable 'import PySide6, PIL, reportlab, requests')) {
    throw 'Board dependencies are missing. Run tools/compose/setup_unified_desktop.ps1.'
}
if (-not (Test-PythonImports $CompanionPythonExecutable 'import tkinter, win32gui, win32clipboard, uiautomation, sounddevice, numpy, scipy, faster_whisper, requests, groq, serial, PIL')) {
    throw 'Voice dependencies are missing. Run tools/compose/setup_unified_desktop.ps1. Existing data was not changed.'
}
if ($CheckOnly) {
    Write-Output 'Teaching Board dependencies ready. Voice companion dependencies ready. No application or listeners started.'
    exit 0
}
$launchArguments = @((Join-Path $PSScriptRoot 'unified_desktop.py'), '--companion-python', $CompanionPythonExecutable)
foreach ($pair in @(@('--data-root', $DataRoot), @('--companion-data-root', $CompanionDataRoot),
                    @('--board-settings-root', $BoardSettingsRoot), @('--library-root', $LibraryRoot))) {
    if ($pair[1]) {
        $selectedPath = $pair[1]
        if (-not [IO.Path]::IsPathRooted($selectedPath)) { $selectedPath = Join-Path $repositoryRoot $selectedPath }
        $launchArguments += @($pair[0], $selectedPath)
    }
}
if ($Demo) { $launchArguments += '--demo' }
& $PythonExecutable @launchArguments
if ($LASTEXITCODE -ne 0) { throw "Classroom Companion exited with code $LASTEXITCODE." }
