$ErrorActionPreference = 'Stop'
$projectRoot = (Get-Location).Path
$localDir = Join-Path $projectRoot '.local'
$configPath = Join-Path $localDir 'linux-hermes.json'
$credentialPath = Join-Path $localDir 'linux-hermes.credential.xml'
if (Test-Path -LiteralPath $configPath) { throw 'Hermes runtime config already exists; refusing to overwrite it.' }
if (Test-Path -LiteralPath $credentialPath) { throw 'Hermes credential already exists; refusing to overwrite it.' }
$endpoint = Read-Host 'Linux Hermes API base URL (for example, http://host:port)'
$uri = $null
if (-not [Uri]::TryCreate($endpoint, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -notin @('http','https') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') {
    throw 'Enter only an HTTP(S) origin with optional port; do not include credentials, path, query or fragment.'
}
$secret = Read-Host 'Enter the Linux Hermes bearer key (hidden; do not paste it into chat)' -AsSecureString
if ($secret.Length -eq 0) { throw 'No key was entered; nothing was saved.' }
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
$config = @{ base_url = $uri.GetLeftPart([UriPartial]::Authority) } | ConvertTo-Json
$temporary = Join-Path $localDir ('linux-hermes-' + [Guid]::NewGuid().ToString('N') + '.tmp')
try {
    [System.IO.File]::WriteAllText($temporary, $config, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($temporary, $configPath)
    $credential = [System.Management.Automation.PSCredential]::new('linux-hermes-api', $secret)
    $credential | Export-Clixml -LiteralPath $credentialPath
    Write-Host 'Saved runtime endpoint and a Windows user-bound encrypted credential.'
} catch {
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $configPath -Force -ErrorAction SilentlyContinue
    throw
} finally {
    $secret = $null
    $credential = $null
}
