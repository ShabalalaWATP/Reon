[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApplicationBaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [int]$MaximumBackupAgeHours = 26
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ready = Invoke-RestMethod -Method Get -Uri "$($ApplicationBaseUrl.TrimEnd('/'))/ready"
if ($ready.status -ne 'ready') {
    throw 'Application readiness is degraded.'
}
$repoRoot = Split-Path -Parent $PSScriptRoot
$snapshot = & uv run --directory (Join-Path $repoRoot 'apps/api') `
    mist-maintenance health-snapshot
if ($LASTEXITCODE -ne 0) {
    throw "Operational database snapshot raised an alert: $snapshot"
}
$latest = Get-ChildItem -LiteralPath $BackupDirectory -Filter '*.dump' -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if ($null -eq $latest) {
    throw 'No validated PostgreSQL backup is present.'
}
$backupAge = [DateTimeOffset]::UtcNow - $latest.LastWriteTimeUtc
if ($backupAge.TotalHours -gt $MaximumBackupAgeHours) {
    throw "Latest PostgreSQL backup is $([math]::Round($backupAge.TotalHours, 1)) hours old."
}
Write-Output ([pscustomobject]@{
    application = 'ready'
    backupAgeHours = [math]::Round($backupAge.TotalHours, 2)
    database = ($snapshot | ConvertFrom-Json)
})
