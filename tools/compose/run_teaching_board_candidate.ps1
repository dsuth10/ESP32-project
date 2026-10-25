param(
    [string]$DataRoot = '',
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
    throw 'The isolated Teaching Board Python environment is unavailable. No packages were installed. See the candidate guide.'
}
$entryPath = Join-Path $PSScriptRoot 'board_candidate.py'
$candidateArguments = @($entryPath, '--data-root', $DataRoot)
if ($Demo) { $candidateArguments += '--demo' }
if ($Smoke) { $candidateArguments += '--smoke' }
& $pythonPath @candidateArguments
if ($LASTEXITCODE -ne 0) { throw "Teaching Board candidate exited with code $LASTEXITCODE." }
