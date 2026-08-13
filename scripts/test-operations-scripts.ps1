Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$required = @(
    'backup-postgres.ps1',
    'restore-postgres.ps1',
    'check-operational-health.ps1',
    'deploy-workflow.ps1',
    'workflow-attestation.ps1',
    'smoke-camunda.ps1',
    'start-local.ps1'
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
$deployWorkflow = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'deploy-workflow.ps1')
$workflowAttestation = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'workflow-attestation.ps1')
$smokeCamunda = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'smoke-camunda.ps1')
$startLocal = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'start-local.ps1')

foreach ($requiredText in @('--format=custom', 'pg_restore --list', 'SHA256', '.partial')) {
    if (-not $backup.Contains($requiredText)) {
        throw "Backup control is missing: $requiredText"
    }
}
foreach ($requiredText in @('BackupManifest.ps1', 'New-AuthenticatedBackupManifest')) {
    if (-not $backup.Contains($requiredText)) {
        throw "Authenticated backup control is missing: $requiredText"
    }
}
foreach ($requiredText in @('RESTORE_ISOLATED_DATABASE', 'pg_restore --list', 'verify-restore')) {
    if (-not $restore.Contains($requiredText)) {
        throw "Restore control is missing: $requiredText"
    }
}
foreach ($requiredText in @('BackupManifest.ps1', 'Assert-AuthenticatedBackupManifest')) {
    if (-not $restore.Contains($requiredText)) {
        throw "Authenticated restore control is missing: $requiredText"
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
foreach ($requiredText in @('OperatorSubject is required')) {
    if (-not $deployWorkflow.Contains($requiredText)) {
        throw "Workflow attestation control is missing: $requiredText"
    }
}
foreach ($requiredText in @('attest-workflow', 'ATTEST_WORKFLOW_AVAILABILITY')) {
    if (-not $workflowAttestation.Contains($requiredText)) {
        throw "Workflow attestation helper is missing: $requiredText"
    }
}
if (-not $deployWorkflow.Contains('AttestWithCompose') -or
    -not $deployWorkflow.Contains('Invoke-WorkflowAvailabilityAttestation')) {
    throw 'Local workflow attestation must run through the Compose API container.'
}
if (-not $smokeCamunda.Contains('-SkipAvailabilityAttestation')) {
    throw 'The Camunda-only smoke must explicitly declare its attestation exception.'
}
if (-not $startLocal.Contains('-OperatorSubject') -or
    -not $startLocal.Contains('-AttestWithCompose')) {
    throw 'Local startup must identify the operator and attest inside Compose.'
}

. (Join-Path $PSScriptRoot 'workflow-attestation.ps1')
$startingLocation = (Get-Location).Path
$dockerCalls = [Collections.Generic.List[object]]::new()
function docker {
    $dockerCalls.Add(@($args))
    $global:LASTEXITCODE = 0
}
Invoke-WorkflowAvailabilityAttestation `
    -ProcessId 'service-request-v1' `
    -ProcessVersion 7 `
    -ProcessDefinitionKey 'process-key' `
    -DeploymentKey 'deployment-key' `
    -Checksum ('a' * 64) `
    -OperatorSubject 'local:contract-test' `
    -RepositoryRoot (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path `
    -AttestWithCompose
if ($dockerCalls.Count -ne 1 -or
    ($dockerCalls[0] -join ' ') -notmatch '^compose exec --no-TTY api python -m istari_service\.maintenance attest-workflow ') {
    throw 'Compose attestation did not invoke the expected API-container command.'
}
if ((Get-Location).Path -ne $startingLocation) {
    throw 'Compose attestation did not restore the operator working directory.'
}

function docker { $global:LASTEXITCODE = 17 }
$failureObserved = $false
try {
    Invoke-WorkflowAvailabilityAttestation `
        -ProcessId 'service-request-v1' `
        -ProcessVersion 7 `
        -ProcessDefinitionKey 'process-key' `
        -DeploymentKey 'deployment-key' `
        -Checksum ('a' * 64) `
        -OperatorSubject 'local:contract-test' `
        -RepositoryRoot (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path `
        -AttestWithCompose
}
catch {
    $failureObserved = $_.Exception.Message -like '*database attestation failed*'
}
if (-not $failureObserved -or (Get-Location).Path -ne $startingLocation) {
    throw 'Compose attestation must propagate failure and restore the working directory.'
}
Remove-Item function:docker

Write-Output 'Operations script contract passed.'
