Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$required = @(
    'backup-postgres.ps1',
    'restore-postgres.ps1',
    'check-operational-health.ps1'
)
foreach ($name in $required) {
    $path = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing operations script: $name"
    }
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $path,
        [ref]$tokens,
        [ref]$parseErrors
    ) | Out-Null
    if ($parseErrors.Count -gt 0) {
        throw "PowerShell parse failure in $name`: $($parseErrors[0].Message)"
    }
}

$backup = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'backup-postgres.ps1')
$restore = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'restore-postgres.ps1')
$health = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'check-operational-health.ps1')

foreach ($requiredText in @('--format=custom', 'pg_restore --list', 'SHA256', '.partial')) {
    if (-not $backup.Contains($requiredText)) {
        throw "Backup control is missing: $requiredText"
    }
}
foreach ($requiredText in @('RESTORE_ISOLATED_DATABASE', 'pg_restore --list', 'SHA256', 'verify-restore')) {
    if (-not $restore.Contains($requiredText)) {
        throw "Restore control is missing: $requiredText"
    }
}
if ($restore.Contains('--clean')) {
    throw 'Restore must never clean or overwrite a populated target.'
}
foreach ($requiredText in @('/ready', 'health-snapshot', 'MaximumBackupAgeHours')) {
    if (-not $health.Contains($requiredText)) {
        throw "Health control is missing: $requiredText"
    }
}

Write-Output 'Operations script contract passed.'
