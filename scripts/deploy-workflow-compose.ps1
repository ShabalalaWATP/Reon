#requires -Version 7.4
[CmdletBinding()]
param(
    [string]$ComposeProjectName = "istari-service-local",
    [string]$BpmnPath = (Join-Path $PSScriptRoot "../workflow/service-request.bpmn"),
    [string]$ExpectedProcessId = "service-request-v1",
    [int]$ExpectedProcessVersion = 1,
    [string]$OperatorSubject
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "workflow-attestation.ps1")

if ($ComposeProjectName -notmatch "^[a-z0-9][a-z0-9_-]{0,62}$") {
    throw "ComposeProjectName must be a bounded lower-case Compose project name."
}
if ($ExpectedProcessId -notmatch "^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$") {
    throw "ExpectedProcessId is invalid."
}
if ($ExpectedProcessVersion -lt 1) {
    throw "ExpectedProcessVersion must be positive."
}
if ([string]::IsNullOrWhiteSpace($OperatorSubject)) {
    throw "OperatorSubject is required."
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$resolvedBpmnPath = (Resolve-Path -LiteralPath $BpmnPath).Path
if ([IO.Path]::GetExtension($resolvedBpmnPath) -ne ".bpmn") {
    throw "BpmnPath must reference a .bpmn file."
}
& (Join-Path $repositoryRoot "workflow/validate-bpmn.ps1") `
    -BpmnPath $resolvedBpmnPath

$checksum = (Get-FileHash -LiteralPath $resolvedBpmnPath -Algorithm SHA256).Hash.ToLowerInvariant()
$bpmnBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($resolvedBpmnPath))

function Invoke-ComposeApiPython {
    param([Parameter(Mandatory)] [string]$Source)

    Push-Location $repositoryRoot
    try {
        $output = $Source | & docker compose `
            --project-name $ComposeProjectName `
            exec --no-TTY api python -
        if ($LASTEXITCODE -ne 0) {
            throw "The Compose API-container operation failed."
        }
        return (($output -join "`n") | ConvertFrom-Json)
    }
    finally {
        Pop-Location
    }
}

$readinessSource = @'
import json
import urllib.error
import urllib.request

try:
    response = urllib.request.urlopen("http://127.0.0.1:8000/ready", timeout=5)
    status = response.status
    payload = json.load(response)
except urllib.error.HTTPError as exc:
    status = exc.code
    payload = json.load(exc)
payload["httpStatus"] = status
print(json.dumps(payload, sort_keys=True))
'@

$inspectionSource = @"
import base64
import hashlib
import json
import urllib.request

expected_id = "$ExpectedProcessId"
expected_version = $ExpectedProcessVersion
expected_xml = base64.b64decode("$bpmnBase64")
body = json.dumps({
    "filter": {"processDefinitionId": expected_id},
    "page": {"limit": 100},
}).encode()
request = urllib.request.Request(
    "http://orchestration:8080/v2/process-definitions/search",
    data=body,
    headers={"Accept": "application/json", "Content-Type": "application/json"},
)
result = json.load(urllib.request.urlopen(request, timeout=15))
items = result.get("items", [])
if result.get("page", {}).get("hasMoreTotalItems"):
    raise RuntimeError("too many process definitions to validate safely")
matches = []
for item in items:
    key = item.get("processDefinitionKey")
    xml = urllib.request.urlopen(
        f"http://orchestration:8080/v2/process-definitions/{key}/xml", timeout=15
    ).read()
    item["checksum"] = hashlib.sha256(xml).hexdigest()
    if (
        item.get("processDefinitionId") == expected_id
        and item.get("version") == expected_version
        and item.get("state") == "ACTIVE"
        and xml == expected_xml
    ):
        matches.append(item)
print(json.dumps({"items": items, "matches": matches}, sort_keys=True))
"@

$inspection = Invoke-ComposeApiPython -Source $inspectionSource
$readiness = Invoke-ComposeApiPython -Source $readinessSource
$definitions = @($inspection.items)
$matches = @($inspection.matches)

function Wait-ForApplicationReadiness {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $result = Invoke-ComposeApiPython -Source $readinessSource
        if ($result.status -eq "ready") {
            return $result
        }
        Start-Sleep -Seconds 1
    }
    throw "Application readiness did not recover after workflow validation."
}

if ($definitions.Count -gt 0) {
    if ($definitions.Count -ne 1 -or $matches.Count -ne 1) {
        throw "Camunda contains a conflicting process definition; no deployment or attestation was changed."
    }
    if ($readiness.checks.configuration -ne "ok") {
        throw "The exact process exists but configuration is not ready; use the governed recovery runbook."
    }
    $null = Wait-ForApplicationReadiness
    [PSCustomObject]@{
        Mode = "reused"
        ProcessId = $matches[0].processDefinitionId
        Version = $matches[0].version
        ProcessDefinitionKey = $matches[0].processDefinitionKey
        Checksum = $checksum
        AvailabilityAttested = $true
    }
    return
}

$deploymentSource = @"
import base64
import json
import secrets
import urllib.request

content = base64.b64decode("$bpmnBase64")
boundary = "istari-" + secrets.token_hex(16)
separator = ("--" + boundary + "\r\n").encode()
body = b"".join([
    separator,
    b'Content-Disposition: form-data; name="resources"; filename="service-request.bpmn"\r\n',
    b"Content-Type: application/octet-stream\r\n\r\n",
    content,
    ("\r\n--" + boundary + "--\r\n").encode(),
])
request = urllib.request.Request(
    "http://orchestration:8080/v2/deployments",
    data=body,
    headers={
        "Accept": "application/json",
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    },
)
print(json.dumps(json.load(urllib.request.urlopen(request, timeout=60)), sort_keys=True))
"@

$deployment = Invoke-ComposeApiPython -Source $deploymentSource
$process = @($deployment.deployments.processDefinition)[0]
if (-not $process -or
    $process.processDefinitionId -ne $ExpectedProcessId -or
    $process.processDefinitionVersion -ne $ExpectedProcessVersion -or
    -not $deployment.deploymentKey -or
    -not $process.processDefinitionKey) {
    throw "Camunda returned an unexpected or incomplete deployment identity."
}

Invoke-WorkflowAvailabilityAttestation `
    -ProcessId $process.processDefinitionId `
    -ProcessVersion $process.processDefinitionVersion `
    -ProcessDefinitionKey $process.processDefinitionKey `
    -DeploymentKey $deployment.deploymentKey `
    -Checksum $checksum `
    -OperatorSubject $OperatorSubject `
    -RepositoryRoot $repositoryRoot `
    -AttestWithCompose `
    -ComposeProjectName $ComposeProjectName

$null = Wait-ForApplicationReadiness

[PSCustomObject]@{
    Mode = "deployed"
    DeploymentKey = $deployment.deploymentKey
    ProcessId = $process.processDefinitionId
    Version = $process.processDefinitionVersion
    ProcessDefinitionKey = $process.processDefinitionKey
    Checksum = $checksum
    AvailabilityAttested = $true
}
