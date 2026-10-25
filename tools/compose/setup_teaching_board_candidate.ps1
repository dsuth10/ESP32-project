param(
    [string]$PythonExecutable = ''
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$localRoot = Join-Path $repositoryRoot '.local'
$environmentRoot = Join-Path $localRoot 'teaching-board-renderer-env'
$requirements = Join-Path $PSScriptRoot 'requirements-board.txt'
$setupMarker = Join-Path $environmentRoot '.setup-in-progress'
$setupLock = Join-Path $localRoot '.teaching-board-renderer-env.setup-lock'

if (Test-Path -LiteralPath $localRoot) {
    $localItem = Get-Item -LiteralPath $localRoot -Force
    if (($localItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw '.local is a link or junction. Choose a normal local source checkout; setup did not follow it.'
    }
}

function Get-PythonVersion([string]$Executable, [string[]]$PrefixArguments = @()) {
    try {
        $output = & $Executable @PrefixArguments -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46)); print(sys.executable)' 2>$null
        if ($LASTEXITCODE -ne 0 -or $output.Count -lt 2) { return $null }
        $version = [string]$output[0]
        if ($version -notin @('3.12', '3.13')) { return $null }
        return [pscustomobject]@{ Executable = [string]$output[-1]; Version = $version }
    } catch { return $null }
}

function Resolve-Python {
    if ($PythonExecutable) {
        if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
            throw 'The selected Python executable does not exist. Choose an installed Python 3.12 or 3.13 interpreter.'
        }
        $selected = Get-PythonVersion $PythonExecutable
        if (-not $selected) { throw 'Teaching Board setup requires Python 3.12 or 3.13; the selected interpreter is unsupported.' }
        return $selected
    }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @('3.12', '3.13')) {
            $selected = Get-PythonVersion $launcher.Source @("-$version")
            if ($selected) { return $selected }
        }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $selected = Get-PythonVersion $python.Source
        if ($selected) { return $selected }
    }
    throw 'Python 3.12 or 3.13 was not found. Install one for this Windows account, then rerun this setup script.'
}

if (Test-Path -LiteralPath $environmentRoot) {
    $environmentItem = Get-Item -LiteralPath $environmentRoot -Force
    if (($environmentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Teaching Board environment path is a link or junction. Setup did not follow or change it.'
    }
    $existingPython = Join-Path $environmentRoot 'Scripts/python.exe'
    if (Test-Path -LiteralPath $existingPython -PathType Leaf) {
        & $existingPython -c 'import PySide6, PIL, reportlab, requests, sounddevice, numpy, scipy, faster_whisper' 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Output 'Teaching Board isolated environment is already ready.'
            exit 0
        }
    }
    throw 'A Teaching Board environment already exists but failed its dependency check. No files were replaced. Review .local/teaching-board-renderer-env before retrying.'
}

if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw 'tools/compose/requirements-board.txt is missing from this source package.'
}
$selectedPython = Resolve-Python
New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
$token = [guid]::NewGuid().ToString('N')
$lockStream = $null
$createdEnvironment = $false
try {
    try { $lockStream = [IO.File]::Open($setupLock, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None) }
    catch { throw 'Another or interrupted Teaching Board setup holds the local setup lock. Confirm no setup is running, then remove only .local/.teaching-board-renderer-env.setup-lock and retry.' }
    $lockBytes = [Text.Encoding]::UTF8.GetBytes($token)
    $lockStream.Write($lockBytes, 0, $lockBytes.Length); $lockStream.Flush()
    if (Test-Path -LiteralPath $environmentRoot) {
        throw 'The environment appeared before setup acquired its lock. No existing environment was replaced.'
    }
    [IO.Directory]::CreateDirectory($environmentRoot) | Out-Null
    $environmentItem = Get-Item -LiteralPath $environmentRoot -Force
    if (($environmentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The new environment path is a link or junction. Setup did not follow it.'
    }
    $createdEnvironment = $true
    [IO.File]::WriteAllText($setupMarker, ($token + "`n" + [IO.Path]::GetFullPath($environmentRoot)), [Text.Encoding]::UTF8)
    Write-Output ("Creating an isolated Teaching Board environment with Python " + $selectedPython.Version + '.')
    & $selectedPython.Executable -m venv $environmentRoot
    if ($LASTEXITCODE -ne 0) { throw 'Python could not create the isolated environment.' }
    $environmentPython = Join-Path $environmentRoot 'Scripts/python.exe'
    & $environmentPython -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet or package-index access, then rerun setup; only this new isolated environment will be cleaned up.' }
    & $environmentPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'The installed package set has dependency conflicts. Only this new isolated environment will be cleaned up.' }
    & $environmentPython -c 'import PySide6, PIL, reportlab, requests, sounddevice, numpy, scipy, faster_whisper'
    if ($LASTEXITCODE -ne 0) { throw 'A required Board, PDF or voice module failed to import.' }
    Remove-Item -LiteralPath $setupMarker -Force
    Write-Output 'Teaching Board setup completed in .local/teaching-board-renderer-env.'
    Write-Output 'No Python environment or packages were copied from another computer.'
} finally {
    if ($createdEnvironment -and (Test-Path -LiteralPath $setupMarker -PathType Leaf)) {
        $markerLines = Get-Content -LiteralPath $setupMarker -TotalCount 2
        $safeLocal = [IO.Path]::GetFullPath($localRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        $safeEnvironment = [IO.Path]::GetFullPath($environmentRoot)
        $rootItem = Get-Item -LiteralPath $environmentRoot -Force -ErrorAction SilentlyContinue
        $markerValid = ($markerLines.Count -eq 2) -and ($markerLines[0] -eq $token) -and
            ($markerLines[1] -eq $safeEnvironment) -and
            $safeEnvironment.StartsWith($safeLocal, [StringComparison]::OrdinalIgnoreCase) -and
            $rootItem -and (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0)
        if ($markerValid) {
            Remove-Item -LiteralPath $environmentRoot -Recurse -Force
        } else {
            Write-Warning 'Setup failed, but its ownership marker could not be verified. The environment was left untouched for manual review.'
        }
    }
    if ($lockStream) {
        $lockStream.Dispose()
        $lockOwned = (Test-Path -LiteralPath $setupLock -PathType Leaf) -and ((Get-Content -LiteralPath $setupLock -Raw) -eq $token)
        if ($lockOwned) {
            Remove-Item -LiteralPath $setupLock -Force
        }
    }
}
