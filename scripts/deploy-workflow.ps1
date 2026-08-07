#requires -Version 7.4
[CmdletBinding()]
param(
    [Uri]$BaseUri = "http://127.0.0.1:8080",
    [string]$BpmnPath = (Join-Path $PSScriptRoot "..\workflow\service-request.bpmn"),
    [string]$TenantId,
    [string]$ExpectedProcessId = "service-request-v1",
    [string]$OperatorSubject,
    [switch]$SkipAvailabilityAttestation
)

$ErrorActionPreference = "Stop"

$parsedAddress = $null
$isLoopback = $BaseUri.DnsSafeHost -ieq "localhost"
if ([Net.IPAddress]::TryParse($BaseUri.DnsSafeHost, [ref]$parsedAddress)) {
    $isLoopback = [Net.IPAddress]::IsLoopback($parsedAddress)
}
if ($BaseUri.Scheme -ne "http" -or -not $isLoopback) {
    throw "This unauthenticated development script only deploys to a loopback HTTP endpoint."
}
if (-not $SkipAvailabilityAttestation -and [string]::IsNullOrWhiteSpace($OperatorSubject)) {
    throw "OperatorSubject is required unless availability attestation is explicitly skipped."
}

$resolvedBpmnPath = (Resolve-Path -LiteralPath $BpmnPath).Path
if ([IO.Path]::GetExtension($resolvedBpmnPath) -ne ".bpmn") {
    throw "BpmnPath must reference a .bpmn file."
}

& (Join-Path $PSScriptRoot "..\workflow\validate-bpmn.ps1") -BpmnPath $resolvedBpmnPath

$deploymentUri = [Uri]::new($BaseUri, "/v2/deployments")
$form = @{ resources = Get-Item -LiteralPath $resolvedBpmnPath }
if ($TenantId) {
    $form.tenantId = $TenantId
}

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $deploymentUri `
    -Headers @{ Accept = "application/json" } `
    -Form $form `
    -TimeoutSec 60

$process = $response.deployments.processDefinition | Select-Object -First 1
if (-not $process) {
    throw "Camunda accepted the deployment but returned no process definition."
}
if ($process.processDefinitionId -ne $ExpectedProcessId) {
    throw "Camunda returned an unexpected process ID."
}
if (-not $response.deploymentKey -or -not $process.processDefinitionKey) {
    throw "Camunda returned incomplete deployment identity."
}

$checksum = (Get-FileHash -LiteralPath $resolvedBpmnPath -Algorithm SHA256).Hash.ToLowerInvariant()
$availabilityAttested = $false
if (-not $SkipAvailabilityAttestation) {
    $apiDirectory = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\apps\api")).Path
    & uv run --directory $apiDirectory python -m istari_service.maintenance `
        attest-workflow `
        --process-id $process.processDefinitionId `
        --process-version $process.processDefinitionVersion `
        --process-definition-key $process.processDefinitionKey `
        --deployment-key $response.deploymentKey `
        --compatibility-key "istari-human-route-v1" `
        --checksum $checksum `
        --operator-subject $OperatorSubject `
        --apply `
        --confirm "ATTEST_WORKFLOW_AVAILABILITY"
    if ($LASTEXITCODE -ne 0) {
        throw "Camunda deployed the workflow, but database attestation failed."
    }
    $availabilityAttested = $true
}

[PSCustomObject]@{
    DeploymentKey = $response.deploymentKey
    ProcessId = $process.processDefinitionId
    Version = $process.processDefinitionVersion
    ProcessDefinitionKey = $process.processDefinitionKey
    ResourceName = $process.resourceName
    Checksum = $checksum
    AvailabilityAttested = $availabilityAttested
}
