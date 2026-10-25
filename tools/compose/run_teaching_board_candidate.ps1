param(
    [string]$DataRoot = '',
    [string]$SettingsRoot = '',
    [string]$LibraryRoot = '',
    [string]$PythonExecutable = '',
    [switch]$Demo,
    [switch]$Smoke
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$candidateRoot = Join-Path $repositoryRoot '.local/teaching-board-candidate'
if (-not $DataRoot) {
    $folderName = if ($Smoke) { 'smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8) } else { 'review' }
    $DataRoot = Join-Path $candidateRoot $folderName
} elseif (-not [IO.Path]::IsPathRooted($DataRoot)) {
    $DataRoot = Join-Path $repositoryRoot $DataRoot
}
$pythonPath = Join-Path $repositoryRoot '.local/teaching-board-renderer-env/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    $setupPath = Join-Path $PSScriptRoot 'setup_teaching_board_candidate.ps1'
    $setupArguments = @('-NoProfile', '-File', $setupPath)
    if ($PythonExecutable) { $setupArguments += @('-PythonExecutable', $PythonExecutable) }
    & powershell.exe @setupArguments
    if ($LASTEXITCODE -ne 0) { throw 'Teaching Board setup failed. The existing Board lesson data was not changed.' }
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw 'Teaching Board setup reported success but its isolated Python executable is missing.'
    }
}
$entryPath = Join-Path $PSScriptRoot 'board_candidate.py'
$candidateArguments = @($entryPath, '--data-root', $DataRoot)
if ($Demo) { $candidateArguments += '--demo' }
if ($Smoke) { $candidateArguments += '--smoke' }
if ($SettingsRoot) {
    if (-not [IO.Path]::IsPathRooted($SettingsRoot)) { $SettingsRoot = Join-Path $repositoryRoot $SettingsRoot }
    $candidateArguments += @('--settings-root', $SettingsRoot)
}
if ($LibraryRoot) {
    if (-not [IO.Path]::IsPathRooted($LibraryRoot)) { $LibraryRoot = Join-Path $repositoryRoot $LibraryRoot }
    $candidateArguments += @('--library-root', $LibraryRoot)
}
& $pythonPath @candidateArguments
if ($LASTEXITCODE -ne 0) { throw "Teaching Board candidate exited with code $LASTEXITCODE." }
