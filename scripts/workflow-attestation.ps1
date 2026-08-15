#requires -Version 7.4

function Invoke-WorkflowAvailabilityAttestation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$ProcessId,
        [Parameter(Mandatory)] [int]$ProcessVersion,
        [Parameter(Mandatory)] [string]$ProcessDefinitionKey,
        [Parameter(Mandatory)] [string]$DeploymentKey,
        [Parameter(Mandatory)] [string]$Checksum,
        [Parameter(Mandatory)] [string]$OperatorSubject,
        [Parameter(Mandatory)] [string]$RepositoryRoot,
        [switch]$AttestWithCompose,
        [string]$ComposeProjectName
    )

    $maintenanceArguments = @(
        "attest-workflow",
        "--process-id", $ProcessId,
        "--process-version", $ProcessVersion,
        "--process-definition-key", $ProcessDefinitionKey,
        "--deployment-key", $DeploymentKey,
        "--compatibility-key", "istari-human-route-v1",
        "--checksum", $Checksum,
        "--operator-subject", $OperatorSubject,
        "--apply",
        "--confirm", "ATTEST_WORKFLOW_AVAILABILITY"
    )
    if ($AttestWithCompose) {
        Push-Location $RepositoryRoot
        try {
            $composeArguments = @("compose")
            if ($ComposeProjectName) {
                $composeArguments += @("--project-name", $ComposeProjectName)
            }
            $composeArguments += @(
                "exec", "--no-TTY", "api", "python", "-m",
                "mist_service.maintenance", "attest-workflow"
            )
            $remainingMaintenanceArguments = `
                $maintenanceArguments[1..($maintenanceArguments.Count - 1)]
            & docker @composeArguments @remainingMaintenanceArguments
        }
        finally {
            Pop-Location
        }
    }
    else {
        $apiDirectory = Join-Path $RepositoryRoot "apps/api"
        & uv run --directory $apiDirectory python -m mist_service.maintenance `
            @maintenanceArguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Camunda deployed the workflow, but database attestation failed."
    }
}
