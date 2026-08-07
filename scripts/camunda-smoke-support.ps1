#requires -Version 7.4

Set-StrictMode -Version Latest

$script:AllowedSmokeVariables = @(
    "intakeDecision", "selectedCommandId", "selectedCommandCandidateGroup",
    "coordinationDecision", "selectedOpsId", "selectedOpsCandidateGroup",
    "allocationDecision", "selectedTeamId", "selectedTeamManagerCandidateGroup",
    "selectedTeamAnalystCandidateGroup", "planningDecision", "assignedSpecialistId",
    "deliveryDecision", "clarificationDecision", "leadReviewDecision", "qualityDecision"
)
$script:AllowedSmokeActions = @(
    "progress", "send_to_allocation", "allocate", "assign", "submit", "approve",
    "disseminate", "request_clarification", "provide_clarification"
)

function Assert-SmokeResult {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) { throw $Message }
}

function Assert-SmokeEndpoint {
    param([Uri]$Endpoint)

    $parsedAddress = $null
    $isLoopback = $Endpoint.DnsSafeHost -ieq "localhost"
    if ([Net.IPAddress]::TryParse($Endpoint.DnsSafeHost, [ref]$parsedAddress)) {
        $isLoopback = [Net.IPAddress]::IsLoopback($parsedAddress)
    }
    Assert-SmokeResult (
        $Endpoint.Scheme -ceq "http" -and $isLoopback
    ) "This unauthenticated smoke test only targets a loopback HTTP endpoint."
}

function Start-SmokeProcess {
    param(
        [Uri]$Endpoint,
        [object]$Deployment
    )

    $requestId = [Guid]::NewGuid().ToString()
    $requesterId = [Guid]::NewGuid().ToString()
    $startBody = @{
        processDefinitionId = $Deployment.ProcessId
        processDefinitionVersion = [int]$Deployment.Version
        variables = @{
            requestId = $requestId
            requesterId = $requesterId
        }
        businessId = $requestId
    } | ConvertTo-Json -Depth 4 -Compress
    $started = Invoke-RestMethod `
        -Method Post `
        -Uri ([Uri]::new($Endpoint, "/v2/process-instances")) `
        -Headers @{ Accept = "application/json" } `
        -ContentType "application/json" `
        -Body $startBody `
        -TimeoutSec 30
    $processInstanceKey = [string]$started.processInstanceKey
    Assert-SmokeResult (
        $processInstanceKey -match "^[0-9]+$"
    ) "Camunda returned no valid process key."
    [PSCustomObject]@{
        ProcessInstanceKey = $processInstanceKey
        RequestId = $requestId
        RequesterId = $requesterId
        StartBody = $startBody
    }
}

function Assert-DuplicateBusinessIdRejected {
    param(
        [Uri]$Endpoint,
        [string]$StartBody
    )

    try {
        $null = Invoke-RestMethod `
            -Method Post `
            -Uri ([Uri]::new($Endpoint, "/v2/process-instances")) `
            -Headers @{ Accept = "application/json" } `
            -ContentType "application/json" `
            -Body $StartBody `
            -TimeoutSec 30
        throw "Camunda accepted a duplicate active business ID."
    }
    catch {
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        if ($null -eq $responseProperty -or
            [int]$responseProperty.Value.StatusCode -ne 409) {
            throw
        }
    }
}

function Get-CreatedTask {
    param(
        [Uri]$Endpoint,
        [string]$ProcessInstanceKey,
        [string]$ElementId,
        [string]$ExpectedName,
        [string]$ExpectedCandidateGroup,
        [AllowEmptyString()]
        [string]$ExpectedAssignee = "",
        [int]$Attempts,
        [int]$DelaySeconds
    )

    $searchBody = @{
        filter = @{
            state = "CREATED"
            processInstanceKey = $ProcessInstanceKey
            elementId = $ElementId
        }
        page = @{ limit = 2 }
    } | ConvertTo-Json -Depth 4 -Compress
    $lastSearchError = $null
    for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
        try {
            $response = Invoke-RestMethod `
                -Method Post `
                -Uri ([Uri]::new($Endpoint, "/v2/user-tasks/search")) `
                -Headers @{ Accept = "application/json" } `
                -ContentType "application/json" `
                -Body $searchBody `
                -TimeoutSec 5
            $lastSearchError = $null
        }
        catch {
            $lastSearchError = $_.Exception.Message
            if ($attempt -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
            continue
        }

        $tasks = @($response.items)
        Assert-SmokeResult (
            $tasks.Count -le 1
        ) "Camunda returned duplicate $ElementId tasks for one process."
        if ($tasks.Count -eq 1) {
            $task = $tasks[0]
            Assert-SmokeResult ($task.elementId -ceq $ElementId) "Unexpected task element."
            Assert-SmokeResult ($task.name -ceq $ExpectedName) "Unexpected task label."
            Assert-SmokeResult ($task.state -ceq "CREATED") "$ElementId is not in CREATED state."
            Assert-SmokeResult (
                [string]$task.processInstanceKey -ceq $ProcessInstanceKey
            ) "$ElementId belongs to a different process instance."
            $candidateGroups = @($task.candidateGroups)
            if ([string]::IsNullOrWhiteSpace($ExpectedCandidateGroup)) {
                Assert-SmokeResult (
                    $candidateGroups.Count -eq 0
                ) "$ElementId unexpectedly grants candidate-group access."
            }
            else {
                Assert-SmokeResult (
                    $candidateGroups.Count -eq 1 -and
                    $candidateGroups[0] -ceq $ExpectedCandidateGroup
                ) "$ElementId has an unexpected candidate-group assignment."
            }
            Assert-SmokeResult (
                @($task.candidateUsers).Count -eq 0
            ) "$ElementId unexpectedly grants direct candidate-user access."
            $actualAssignee = [string]$task.assignee
            if ([string]::IsNullOrWhiteSpace($ExpectedAssignee)) {
                Assert-SmokeResult (
                    [string]::IsNullOrWhiteSpace($actualAssignee)
                ) "$ElementId must remain unassigned until a human claims it."
            }
            else {
                Assert-SmokeResult (
                    $actualAssignee -ceq $ExpectedAssignee
                ) "$ElementId has an unexpected direct assignee."
            }
            return $task
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }

    $detail = if ($lastSearchError) { " Last search error: $lastSearchError" } else { "" }
    throw "Camunda did not expose $ElementId within the bounded retry window.$detail"
}

function Complete-HumanTask {
    param(
        [Uri]$Endpoint,
        [object]$Task,
        [string]$ActorId,
        [string]$Action,
        [hashtable]$Variables,
        [bool]$ShouldClaim
    )

    $parsedActor = [Guid]::Empty
    Assert-SmokeResult (
        [Guid]::TryParse($ActorId, [ref]$parsedActor)
    ) "Smoke actors must use synthetic UUID values."
    Assert-SmokeResult (
        $Action -cin $script:AllowedSmokeActions
    ) "The smoke attempted an unsupported workflow action."
    foreach ($variableName in $Variables.Keys) {
        Assert-SmokeResult (
            $variableName -cin $script:AllowedSmokeVariables
        ) "The smoke attempted to send an unapproved workflow variable."
    }

    if ($ShouldClaim) {
        $assignmentBody = @{
            assignee = $ActorId
            allowOverride = $false
            action = "claim"
        } | ConvertTo-Json -Compress
        $null = Invoke-RestMethod `
            -Method Post `
            -Uri ([Uri]::new($Endpoint, "/v2/user-tasks/$($Task.userTaskKey)/assignment")) `
            -Headers @{ Accept = "application/json" } `
            -ContentType "application/json" `
            -Body $assignmentBody `
            -TimeoutSec 10
    }
    else {
        Assert-SmokeResult (
            [string]$Task.assignee -ceq $ActorId
        ) "Only the pre-assigned human may complete $($Task.elementId)."
    }

    $completionBody = @{
        action = $Action
        variables = $Variables
    } | ConvertTo-Json -Depth 4 -Compress
    $null = Invoke-RestMethod `
        -Method Post `
        -Uri ([Uri]::new($Endpoint, "/v2/user-tasks/$($Task.userTaskKey)/completion")) `
        -Headers @{ Accept = "application/json" } `
        -ContentType "application/json" `
        -Body $completionBody `
        -TimeoutSec 10
}

function Invoke-HumanRoute {
    param(
        [Uri]$Endpoint,
        [string]$ProcessInstanceKey,
        [object[]]$Route,
        [int]$Attempts,
        [int]$DelaySeconds
    )

    foreach ($stage in $Route) {
        $expectedAssignee = if ($stage.ContainsKey("Assignee")) { [string]$stage.Assignee } else { "" }
        $task = Get-CreatedTask `
            -Endpoint $Endpoint `
            -ProcessInstanceKey $ProcessInstanceKey `
            -ElementId $stage.ElementId `
            -ExpectedName $stage.Name `
            -ExpectedCandidateGroup $stage.Group `
            -ExpectedAssignee $expectedAssignee `
            -Attempts $Attempts `
            -DelaySeconds $DelaySeconds
        Complete-HumanTask `
            -Endpoint $Endpoint `
            -Task $task `
            -ActorId $stage.Actor `
            -Action $stage.Action `
            -Variables $stage.Variables `
            -ShouldClaim $stage.Claim
        $task
    }
}

function Get-CompletedProcess {
    param(
        [Uri]$Endpoint,
        [string]$ProcessInstanceKey,
        [int]$Attempts,
        [int]$DelaySeconds
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
        try {
            $process = Invoke-RestMethod `
                -Method Get `
                -Uri ([Uri]::new($Endpoint, "/v2/process-instances/$ProcessInstanceKey")) `
                -Headers @{ Accept = "application/json" } `
                -TimeoutSec 5
            Assert-SmokeResult (
                [string]$process.processInstanceKey -ceq $ProcessInstanceKey
            ) "Camunda returned a different process instance."
            if ($process.state -ceq "COMPLETED") {
                Assert-SmokeResult (
                    -not [string]::IsNullOrWhiteSpace([string]$process.endDate)
                ) "The completed process has no end date."
                return $process
            }
        }
        catch {
            if ($attempt -eq $Attempts) { throw }
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }
    throw "Camunda did not complete the process within the bounded retry window."
}
