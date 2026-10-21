param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ClientArgs)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$localDir = Join-Path $projectRoot '.local'
$credentialPath = Join-Path $localDir 'linux-hermes.credential.xml'
$clientPath = Join-Path $PSScriptRoot 'linux_hermes_client.py'

$filteredArgs = [System.Collections.Generic.List[string]]::new()
$credentialOverrideSeen = $false
for ($i = 0; $i -lt $ClientArgs.Count; $i++) {
    if ($ClientArgs[$i] -ieq '-CredentialPath') {
        if ($credentialOverrideSeen -or $i + 1 -ge $ClientArgs.Count) {
            throw 'Credential path option is repeated or missing its value.'
        }
        $credentialOverrideSeen = $true
        $i++
        $credentialPath = $ClientArgs[$i]
        continue
    }
    $filteredArgs.Add($ClientArgs[$i])
}
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
    throw 'Could not load the configured encrypted credential.'
}
$credentialPath = (Resolve-Path -LiteralPath $credentialPath).Path
try {
    $credential = Import-Clixml -LiteralPath $credentialPath
    $key = $credential.GetNetworkCredential().Password
    if ([string]::IsNullOrWhiteSpace($key)) { throw 'Empty credential.' }
    $key | & python $clientPath @filteredArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
    Write-Error 'Hermes client failed. Credential contents were not printed.'
    exit 1
} finally {
    $key = $null
    $credential = $null
}
