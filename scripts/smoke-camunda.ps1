#requires -Version 7.4
[CmdletBinding()]
param(
    [Uri]$BaseUri = "http://127.0.0.1:8080",
    [ValidateRange(1, 60)]
    [int]$MaxAttempts = 30,
    [ValidateRange(1, 10)]
    [int]$RetryDelaySeconds = 2
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "camunda-smoke-support.ps1")

Assert-SmokeEndpoint -Endpoint $BaseUri
$deploymentOutput = @(
    & (Join-Path $PSScriptRoot "deploy-workflow.ps1") `
        -BaseUri $BaseUri `
        -SkipAvailabilityAttestation
)
$deployment = $deploymentOutput |
    Where-Object { $_.PSObject.Properties["ProcessDefinitionKey"] } |
    Select-Object -Last 1
Assert-SmokeResult ($null -ne $deployment) "Workflow deployment returned no process definition."

$jiocActorId = "00000000-0000-4000-8000-000000000101"
$commandActorId = "00000000-0000-4000-8000-000000000102"
$opsActorId = "00000000-0000-4000-8000-000000000103"
$osgManagerActorId = "00000000-0000-4000-8000-000000000104"
$osgAnalystActorId = "00000000-0000-4000-8000-000000000105"
$qcManagerActorId = "00000000-0000-4000-8000-000000000106"
$beaconManagerActorId = "00000000-0000-4000-8000-000000000107"
$beaconAnalystActorId = "00000000-0000-4000-8000-000000000108"

$staffedRoute = @(
    @{
        ElementId = "intake_review"; Name = "JIOC Routing"; Group = "jioc-routing"
        Actor = $jiocActorId; Action = "progress"; Claim = $true
        Variables = @{
            intakeDecision = "progress"; selectedCommandId = "DIGOC"
            selectedCommandCandidateGroup = @("digoc-routing")
        }
    }
    @{
        ElementId = "coordination_review"; Name = "Request Coordination"; Group = "digoc-routing"
        Actor = $commandActorId; Action = "send_to_allocation"; Claim = $true
        Variables = @{
            coordinationDecision = "send_to_allocation"; selectedOpsId = "NCGI_A_OPS"
            selectedOpsCandidateGroup = @("ncgi-a-ops-routing")
        }
    }
    @{
        ElementId = "allocation_review"; Name = "Ops Routing"; Group = "ncgi-a-ops-routing"
        Actor = $opsActorId; Action = "allocate"; Claim = $true
        Variables = @{
            allocationDecision = "allocate"; selectedTeamId = "OSG_TEAM"
            selectedTeamManagerCandidateGroup = @("osg-team-managers")
            selectedTeamAnalystCandidateGroup = @("osg-team-analysts")
        }
    }
    @{
        ElementId = "delivery_planning"; Name = "Team Assignment"; Group = "osg-team-managers"
        Actor = $osgManagerActorId; Action = "assign"; Claim = $true
        Variables = @{ planningDecision = "assign"; assignedSpecialistId = $osgAnalystActorId }
    }
    @{
        ElementId = "delivery_work"; Name = "Product Production"; Group = "osg-team-analysts"
        Actor = $osgAnalystActorId; Assignee = $osgAnalystActorId; Action = "request_clarification"; Claim = $false
        Variables = @{ deliveryDecision = "request_clarification" }
    }
    @{
        ElementId = "customer_clarification_response"; Name = "Provide production information"; Group = ""
        Actor = ""; Assignee = ""; Action = "provide_clarification"; Claim = $false
        Variables = @{ clarificationDecision = "provide_clarification" }
    }
    @{
        ElementId = "delivery_work"; Name = "Product Production"; Group = "osg-team-analysts"
        Actor = $osgAnalystActorId; Assignee = $osgAnalystActorId; Action = "request_clarification"; Claim = $false
        Variables = @{ deliveryDecision = "request_clarification" }
    }
    @{
        ElementId = "customer_clarification_response"; Name = "Provide production information"; Group = ""
        Actor = ""; Assignee = ""; Action = "provide_clarification"; Claim = $false
        Variables = @{ clarificationDecision = "provide_clarification" }
    }
    @{
        ElementId = "delivery_work"; Name = "Product Production"; Group = "osg-team-analysts"
        Actor = $osgAnalystActorId; Assignee = $osgAnalystActorId; Action = "submit"; Claim = $false
        Variables = @{ deliveryDecision = "submit" }
    }
    @{
        ElementId = "lead_review"; Name = "Manager Review"; Group = "osg-team-managers"
        Actor = $osgManagerActorId; Action = "approve"; Claim = $true
        Variables = @{ leadReviewDecision = "approve" }
    }
    @{
        ElementId = "quality_review"; Name = "QC Review"; Group = "qc-managers"
        Actor = $qcManagerActorId; Action = "approve"; Claim = $true
        Variables = @{ qualityDecision = "approve" }
    }
    @{
        ElementId = "release"; Name = "Dissemination"; Group = "qc-managers"
        Actor = $qcManagerActorId; Action = "disseminate"; Claim = $true
        Variables = @{}
    }
)

$staffed = Start-SmokeProcess -Endpoint $BaseUri -Deployment $deployment
$staffedRoute[5].Actor = $staffed.RequesterId
$staffedRoute[5].Assignee = $staffed.RequesterId
$staffedRoute[7].Actor = $staffed.RequesterId
$staffedRoute[7].Assignee = $staffed.RequesterId
Assert-DuplicateBusinessIdRejected -Endpoint $BaseUri -StartBody $staffed.StartBody
$staffedTasks = @(Invoke-HumanRoute `
    -Endpoint $BaseUri `
    -ProcessInstanceKey $staffed.ProcessInstanceKey `
    -Route $staffedRoute `
    -Attempts $MaxAttempts `
    -DelaySeconds $RetryDelaySeconds)
$completed = Get-CompletedProcess `
    -Endpoint $BaseUri `
    -ProcessInstanceKey $staffed.ProcessInstanceKey `
    -Attempts $MaxAttempts `
    -DelaySeconds $RetryDelaySeconds

$alternativeRoute = @(
    @{
        ElementId = "intake_review"; Name = "JIOC Routing"; Group = "jioc-routing"
        Actor = $jiocActorId; Action = "progress"; Claim = $true
        Variables = @{
            intakeDecision = "progress"; selectedCommandId = "SYGOC"
            selectedCommandCandidateGroup = @("sygoc-routing")
        }
    }
    @{
        ElementId = "coordination_review"; Name = "Request Coordination"; Group = "sygoc-routing"
        Actor = $commandActorId; Action = "send_to_allocation"; Claim = $true
        Variables = @{
            coordinationDecision = "send_to_allocation"; selectedOpsId = "NIMBUS_OPS"
            selectedOpsCandidateGroup = @("nimbus-ops-routing")
        }
    }
    @{
        ElementId = "allocation_review"; Name = "Ops Routing"; Group = "nimbus-ops-routing"
        Actor = $opsActorId; Action = "allocate"; Claim = $true
        Variables = @{
            allocationDecision = "allocate"; selectedTeamId = "BEACON_TEAM"
            selectedTeamManagerCandidateGroup = @("beacon-team-managers")
            selectedTeamAnalystCandidateGroup = @("beacon-team-analysts")
        }
    }
    @{
        ElementId = "delivery_planning"; Name = "Team Assignment"; Group = "beacon-team-managers"
        Actor = $beaconManagerActorId; Action = "assign"; Claim = $true
        Variables = @{ planningDecision = "assign"; assignedSpecialistId = $beaconAnalystActorId }
    }
    @{
        ElementId = "delivery_work"; Name = "Product Production"; Group = "beacon-team-analysts"
        Actor = $beaconAnalystActorId; Assignee = $beaconAnalystActorId; Action = "submit"; Claim = $false
        Variables = @{ deliveryDecision = "submit" }
    }
    @{
        ElementId = "lead_review"; Name = "Manager Review"; Group = "beacon-team-managers"
        Actor = $beaconManagerActorId; Action = "approve"; Claim = $true
        Variables = @{ leadReviewDecision = "approve" }
    }
    @{
        ElementId = "quality_review"; Name = "QC Review"; Group = "qc-managers"
        Actor = $qcManagerActorId; Action = "approve"; Claim = $true
        Variables = @{ qualityDecision = "approve" }
    }
    @{
        ElementId = "release"; Name = "Dissemination"; Group = "qc-managers"
        Actor = $qcManagerActorId; Action = "disseminate"; Claim = $true
        Variables = @{}
    }
)

$alternative = Start-SmokeProcess -Endpoint $BaseUri -Deployment $deployment
$alternativeTasks = @(Invoke-HumanRoute `
    -Endpoint $BaseUri `
    -ProcessInstanceKey $alternative.ProcessInstanceKey `
    -Route $alternativeRoute `
    -Attempts $MaxAttempts `
    -DelaySeconds $RetryDelaySeconds)
$alternativeCompleted = Get-CompletedProcess `
    -Endpoint $BaseUri `
    -ProcessInstanceKey $alternative.ProcessInstanceKey `
    -Attempts $MaxAttempts `
    -DelaySeconds $RetryDelaySeconds

[PSCustomObject]@{
    ProcessDefinitionId = $deployment.ProcessId
    ProcessDefinitionVersion = $deployment.Version
    BusinessIdUniqueness = "verified"
    StaffedProcessInstanceKey = $staffed.ProcessInstanceKey
    StaffedPath = "DIGOC -> NCGI-A Ops -> OSG Team"
    StaffedFirstTask = $staffedTasks[0].elementId
    StaffedLastTask = $staffedTasks[-1].elementId
    StaffedClarificationLoops = 2
    StaffedSpecialistRetained = $osgAnalystActorId
    StaffedState = $completed.state
    AlternativeProcessInstanceKey = $alternative.ProcessInstanceKey
    AlternativePath = "SYGOC -> Nimbus Ops -> Beacon Team"
    AlternativeFirstTask = $alternativeTasks[0].elementId
    AlternativeLastTask = $alternativeTasks[-1].elementId
    AlternativeManagerGroup = "beacon-team-managers"
    AlternativeAnalystGroup = "beacon-team-analysts"
    AlternativeState = $alternativeCompleted.state
}
