[CmdletBinding()]
param(
    [string]$CredentialPath,
    [string]$RollbackBackup,
    [string]$ExpectedCurrent
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$localDir = Join-Path $projectRoot '.local'
$helper = Join-Path $PSScriptRoot 'migrate_linux_hermes_endpoint.py'

if ($RollbackBackup) {
    if (-not $ExpectedCurrent) { throw 'Rollback requires -ExpectedCurrent.' }
    & python $helper --rollback-backup $RollbackBackup --expected-current $ExpectedCurrent
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    exit 0
}

$credentialPath = if ($CredentialPath) { $CredentialPath } else { Join-Path $localDir 'linux-hermes.credential.xml' }
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) { throw 'Could not load the configured encrypted credential.' }
$endpoint = Read-Host 'New Linux Hermes HTTPS origin (no path or credentials)'
try {
    $secure = Import-Clixml -LiteralPath (Resolve-Path -LiteralPath $credentialPath).Path
    $key = $secure.GetNetworkCredential().Password
    if ([string]::IsNullOrWhiteSpace($key)) { throw 'Empty credential.' }
    $key | & python $helper --endpoint $endpoint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
    Write-Error 'Endpoint migration failed. Credential contents were not printed.'
    exit 1
} finally {
    $key = $null
    $secure = $null
}
