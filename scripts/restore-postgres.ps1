[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [string]$ExpectedRevision = '0047_action_view_contexts'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Confirmation -cne 'RESTORE_ISOLATED_DATABASE') {
    throw 'Exact RESTORE_ISOLATED_DATABASE confirmation is required.'
}
if ([string]::IsNullOrWhiteSpace($env:ISTARI_RESTORE_DATABASE_URL)) {
    throw 'Set ISTARI_RESTORE_DATABASE_URL for an empty, isolated target.'
}
foreach ($command in @('psql', 'pg_restore', 'uv')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command is required."
    }
}
. (Join-Path $PSScriptRoot 'lib/PostgresServiceFile.ps1')
. (Join-Path $PSScriptRoot 'lib/BackupManifest.ps1')

$backup = (Resolve-Path -LiteralPath $BackupFile).Path
$manifestPath = "$backup.sha256.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw 'The SHA-256 backup manifest is required.'
}
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
Assert-AuthenticatedBackupManifest -Manifest $manifest -BackupPath $backup
& pg_restore --list $backup | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Backup validation failed before restore.'
}

$previousServiceFile = $env:PGSERVICEFILE
$serviceFile = New-PostgresServiceFile $env:ISTARI_RESTORE_DATABASE_URL
$env:PGSERVICEFILE = $serviceFile
try {

$tableCount = & psql `
    --dbname=service=istari_maintenance `
    --tuples-only `
    --no-align `
    --command="SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
if ($LASTEXITCODE -ne 0) {
    throw 'The restore target could not be inspected.'
}
if ([int]$tableCount.Trim() -ne 0) {
    throw 'The restore target is not empty. No restore was attempted.'
}

& pg_restore `
    --dbname=service=istari_maintenance `
    --exit-on-error `
    --no-owner `
    --no-acl `
    --single-transaction `
    $backup
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed with exit code $LASTEXITCODE."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$evidence = [System.IO.Path]::GetFullPath($EvidenceDirectory)
if (-not (Test-Path -LiteralPath $evidence)) {
    New-Item -ItemType Directory -Path $evidence | Out-Null
}
$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$evidenceFile = Join-Path $evidence "restore-verification-$stamp.json"
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = $env:ISTARI_RESTORE_DATABASE_URL
    $verification = & uv run --directory (Join-Path $repoRoot 'apps/api') `
        istari-maintenance verify-restore `
        --expected-revision $ExpectedRevision
    if ($LASTEXITCODE -ne 0) {
        throw 'Restored database integrity verification failed.'
    }
    $verification | Set-Content -LiteralPath $evidenceFile -Encoding utf8NoBOM
}
finally {
    $env:DATABASE_URL = $previousDatabaseUrl
}
}
finally {
    $env:PGSERVICEFILE = $previousServiceFile
    Remove-Item -LiteralPath $serviceFile -Force -ErrorAction SilentlyContinue
}
Write-Output ([pscustomobject]@{
    restored = $true
    verification = $evidenceFile
})
