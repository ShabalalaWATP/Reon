#requires -Version 7.4
[CmdletBinding()]
param(
    [Uri]$BaseUri = "http://127.0.0.1:8080",
    [string]$BpmnPath = (Join-Path $PSScriptRoot "..\workflow\service-request.bpmn"),
    [string]$TenantId
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

[PSCustomObject]@{
    DeploymentKey = $response.deploymentKey
    ProcessId = $process.processDefinitionId
    Version = $process.processDefinitionVersion
    ProcessDefinitionKey = $process.processDefinitionKey
    ResourceName = $process.resourceName
}
