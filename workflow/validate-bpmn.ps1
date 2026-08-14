#requires -Version 7.4
[CmdletBinding()]
param(
    [string]$BpmnPath = (Join-Path $PSScriptRoot "service-request.bpmn")
)

$ErrorActionPreference = "Stop"
[xml]$document = Get-Content -Raw (Resolve-Path -LiteralPath $BpmnPath)
$namespaces = [Xml.XmlNamespaceManager]::new($document.NameTable)
$namespaces.AddNamespace("bpmn", "http://www.omg.org/spec/BPMN/20100524/MODEL")
$namespaces.AddNamespace("bpmndi", "http://www.omg.org/spec/BPMN/20100524/DI")
$namespaces.AddNamespace("zeebe", "http://camunda.org/schema/zeebe/1.0")

function Assert-Workflow {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw $Message
    }
}

$processes = $document.SelectNodes("//bpmn:process", $namespaces)
Assert-Workflow ($processes.Count -eq 1) "The BPMN document must contain one process."
$process = $processes[0]
Assert-Workflow ($null -ne $process) "The BPMN document has no process."
Assert-Workflow ($process.isExecutable -eq "true") "The process must be executable."
Assert-Workflow ($process.id -ceq "service-request-v1") "Unexpected process identifier."

$expectedWorkflowVariables = @(
    "requestId", "requesterId", "assignedDeliveryTeamId", "assignedSpecialistId",
    "selectedCommandId", "selectedCommandCandidateGroup", "selectedOpsId",
    "selectedOpsCandidateGroup", "selectedTeamId", "selectedTeamManagerCandidateGroup",
    "selectedTeamAnalystCandidateGroup"
)
$expectedDocumentation = (
    "Workflow variables are restricted to " +
    ($expectedWorkflowVariables -join ", ") +
    " and the named decision values on outgoing gateways. Request and clarification content, reasons " +
    "and security context remain in product storage."
)
$documentation = @($process.SelectNodes("bpmn:documentation", $namespaces))
Assert-Workflow ($documentation.Count -eq 1) "The process must have one variable-contract note."
Assert-Workflow (
    $documentation[0].InnerText -ceq $expectedDocumentation
) "Unexpected workflow-variable documentation."

$activityTypes = @(
    "task", "businessRuleTask", "callActivity", "manualTask", "receiveTask",
    "scriptTask", "sendTask", "serviceTask", "subProcess", "transaction",
    "adHocSubProcess", "userTask"
)
foreach ($activity in $process.ChildNodes) {
    if ($activity.NamespaceURI -eq "http://www.omg.org/spec/BPMN/20100524/MODEL" -and
        $activity.LocalName -in $activityTypes) {
        Assert-Workflow ($activity.LocalName -ceq "userTask") (
            "Unsupported BPMN activity type: $($activity.LocalName) ($($activity.id)). " +
            "Only userTask activities are permitted."
        )
    }
}

$allowedProcessElements = @(
    "documentation", "startEvent", "endEvent", "userTask", "exclusiveGateway",
    "sequenceFlow"
)
foreach ($element in $process.ChildNodes) {
    if ($element.NamespaceURI -eq "http://www.omg.org/spec/BPMN/20100524/MODEL") {
        Assert-Workflow (
            $element.LocalName -in $allowedProcessElements
        ) "Unsupported BPMN process element type: $($element.LocalName)."
    }
}

$allowedZeebeElements = @("assignmentDefinition", "userTask")
foreach ($element in $document.SelectNodes("//zeebe:*", $namespaces)) {
    Assert-Workflow (
        $element.LocalName -in $allowedZeebeElements
    ) "Unsupported Zeebe extension: $($element.LocalName)."
}

$elementsById = @{}
foreach ($element in $document.SelectNodes("//*[@id]")) {
    Assert-Workflow (-not $elementsById.ContainsKey($element.id)) "Duplicate BPMN id: $($element.id)"
    $elementsById[$element.id] = $element
}

$flowsById = @{}
foreach ($flow in $document.SelectNodes("//bpmn:sequenceFlow", $namespaces)) {
    Assert-Workflow $elementsById.ContainsKey($flow.sourceRef) "Missing source for $($flow.id)."
    Assert-Workflow $elementsById.ContainsKey($flow.targetRef) "Missing target for $($flow.id)."
    $flowsById[$flow.id] = $flow
}

$expectedFlowEndpoints = @{
    flow_start_intake = "request_submitted|intake_review"
    flow_intake_gateway = "intake_review|intake_outcome"
    flow_intake_information = "intake_outcome|requester_response"
    flow_intake_close = "intake_outcome|closed"
    flow_intake_progress = "intake_outcome|coordination_review"
    flow_information_gateway = "requester_response|requester_outcome"
    flow_information_resubmit = "requester_outcome|intake_review"
    flow_information_withdraw = "requester_outcome|cancelled"
    flow_coordination_gateway = "coordination_review|coordination_outcome"
    flow_coordination_return = "coordination_outcome|intake_review"
    flow_coordination_hold = "coordination_outcome|on_hold"
    flow_coordination_close = "coordination_outcome|closed"
    flow_coordination_allocate = "coordination_outcome|allocation_review"
    flow_hold_gateway = "on_hold|hold_outcome"
    flow_hold_resume = "hold_outcome|coordination_review"
    flow_hold_close = "hold_outcome|closed"
    flow_allocation_gateway = "allocation_review|allocation_outcome"
    flow_allocation_return = "allocation_outcome|coordination_review"
    flow_allocation_plan = "allocation_outcome|delivery_planning"
    flow_planning_gateway = "delivery_planning|planning_outcome"
    flow_planning_reallocate = "planning_outcome|allocation_review"
    flow_planning_delivery = "planning_outcome|delivery_work"
    flow_delivery_gateway = "delivery_work|delivery_outcome"
    flow_delivery_lead = "delivery_outcome|lead_review"
    flow_delivery_clarification = "delivery_outcome|customer_clarification_response"
    flow_clarification_gateway = "customer_clarification_response|clarification_outcome"
    flow_clarification_resume = "clarification_outcome|delivery_work"
    flow_clarification_withdraw = "clarification_outcome|cancelled"
    flow_lead_gateway = "lead_review|lead_review_outcome"
    flow_lead_rework = "lead_review_outcome|delivery_work"
    flow_lead_quality = "lead_review_outcome|quality_review"
    flow_quality_gateway = "quality_review|quality_outcome"
    flow_quality_rework = "quality_outcome|delivery_work"
    flow_quality_release = "quality_outcome|release"
    flow_release_completed = "release|completed"
}
$expectedConditions = @{
    flow_intake_information = '= intakeDecision = "request_information"'
    flow_intake_close = '= intakeDecision = "close"'
    flow_intake_progress = '= intakeDecision = "progress"'
    flow_information_resubmit = '= requesterDecision = "provide_information"'
    flow_information_withdraw = '= requesterDecision = "withdraw"'
    flow_coordination_return = '= coordinationDecision = "return_to_triage"'
    flow_coordination_hold = '= coordinationDecision = "hold"'
    flow_coordination_close = '= coordinationDecision = "close"'
    flow_coordination_allocate = '= coordinationDecision = "send_to_allocation"'
    flow_hold_resume = '= holdDecision = "resume"'
    flow_hold_close = '= holdDecision = "close"'
    flow_allocation_return = '= allocationDecision = "return_to_coordination"'
    flow_allocation_plan = '= allocationDecision = "allocate"'
    flow_planning_reallocate = '= planningDecision = "return_for_reallocation"'
    flow_planning_delivery = '= planningDecision = "assign"'
    flow_delivery_lead = '= deliveryDecision = "submit"'
    flow_delivery_clarification = '= deliveryDecision = "request_clarification"'
    flow_clarification_resume = '= clarificationDecision = "provide_clarification"'
    flow_clarification_withdraw = '= clarificationDecision = "withdraw"'
    flow_lead_rework = '= leadReviewDecision = "changes_required"'
    flow_lead_quality = '= leadReviewDecision = "approve"'
    flow_quality_rework = '= qualityDecision = "changes_required"'
    flow_quality_release = '= qualityDecision = "approve"'
}
Assert-Workflow ($flowsById.Count -eq $expectedFlowEndpoints.Count) "Unexpected sequence-flow count."
foreach ($flowId in $flowsById.Keys) {
    Assert-Workflow $expectedFlowEndpoints.ContainsKey($flowId) "Unexpected sequence flow: $flowId"
    $flow = $flowsById[$flowId]
    $actualEndpoints = "$($flow.sourceRef)|$($flow.targetRef)"
    Assert-Workflow ($actualEndpoints -ceq $expectedFlowEndpoints[$flowId]) "Unexpected endpoints on $flowId."
    $condition = $flow.SelectSingleNode("bpmn:conditionExpression", $namespaces)
    if ($expectedConditions.ContainsKey($flowId)) {
        Assert-Workflow ($null -ne $condition) "Gateway flow $flowId has no condition."
        Assert-Workflow ($condition.InnerText -ceq $expectedConditions[$flowId]) "Unexpected condition on $flowId."
    }
    else {
        Assert-Workflow ($null -eq $condition) "Direct flow $flowId must not have a condition."
    }
}

foreach ($node in $document.SelectNodes("//bpmn:process/*[@id]", $namespaces)) {
    foreach ($incoming in $node.SelectNodes("bpmn:incoming", $namespaces)) {
        $flow = $flowsById[$incoming.InnerText]
        Assert-Workflow ($null -ne $flow) "Missing incoming flow $($incoming.InnerText)."
        Assert-Workflow ($flow.targetRef -eq $node.id) "Incoming flow target mismatch on $($node.id)."
    }
    foreach ($outgoing in $node.SelectNodes("bpmn:outgoing", $namespaces)) {
        $flow = $flowsById[$outgoing.InnerText]
        Assert-Workflow ($null -ne $flow) "Missing outgoing flow $($outgoing.InnerText)."
        Assert-Workflow ($flow.sourceRef -eq $node.id) "Outgoing flow source mismatch on $($node.id)."
    }
}

$expectedTasks = @(
    "intake_review", "requester_response", "coordination_review", "on_hold",
    "allocation_review", "delivery_planning", "delivery_work",
    "customer_clarification_response", "lead_review", "quality_review", "release"
)
$expectedAssignments = @{
    intake_review = "|crioc-routing"
    requester_response = "= requesterId|"
    coordination_review = "|= selectedCommandCandidateGroup"
    on_hold = "|= selectedCommandCandidateGroup"
    allocation_review = "|= selectedOpsCandidateGroup"
    delivery_planning = "|= selectedTeamManagerCandidateGroup"
    delivery_work = "= assignedSpecialistId|= selectedTeamAnalystCandidateGroup"
    customer_clarification_response = "= requesterId|"
    lead_review = "|= selectedTeamManagerCandidateGroup"
    quality_review = "|qc-reviewers"
    release = "|release-managers"
}
$expectedTaskNames = @{
    intake_review = "CRIOC Routing"
    requester_response = "Provide requested information"
    coordination_review = "Request Coordination"
    on_hold = "Resolve coordination hold"
    allocation_review = "Ops Routing"
    delivery_planning = "Team Assignment"
    delivery_work = "Product Production"
    customer_clarification_response = "Provide production information"
    lead_review = "Manager Review"
    quality_review = "QC Review"
    release = "Dissemination"
}
$allowedAssignmentAttributes = @("assignee", "candidateGroups")
$allowedTaskAttributes = @("id", "name")
$allowedTaskChildren = @("extensionElements", "incoming", "outgoing")
$tasks = $document.SelectNodes("//bpmn:userTask", $namespaces)
Assert-Workflow ($tasks.Count -eq $expectedTasks.Count) "Unexpected user-task count."
foreach ($task in $tasks) {
    Assert-Workflow ($task.id -in $expectedTasks) "Unexpected user task: $($task.id)"
    Assert-Workflow (
        $task.name -ceq $expectedTaskNames[$task.id]
    ) "Unexpected user-task label on $($task.id)."
    foreach ($attribute in $task.Attributes) {
        Assert-Workflow (
            $attribute.NamespaceURI -eq "" -and
            $attribute.LocalName -in $allowedTaskAttributes
        ) "Unexpected BPMN user-task attribute on $($task.id): $($attribute.Name)."
    }
    foreach ($child in $task.ChildNodes) {
        if ($child.NamespaceURI -eq "http://www.omg.org/spec/BPMN/20100524/MODEL") {
            Assert-Workflow (
                $child.LocalName -in $allowedTaskChildren
            ) "Unexpected BPMN user-task child on $($task.id): $($child.LocalName)."
        }
    }
    $extensions = @($task.SelectNodes("bpmn:extensionElements/*", $namespaces))
    Assert-Workflow (
        $extensions.Count -eq 2
    ) "$($task.id) must have exactly two approved Camunda extensions."
    $implementation = $task.SelectSingleNode("bpmn:extensionElements/zeebe:userTask", $namespaces)
    $assignment = $task.SelectSingleNode("bpmn:extensionElements/zeebe:assignmentDefinition", $namespaces)
    Assert-Workflow ($null -ne $implementation) "$($task.id) is not a Camunda user task."
    Assert-Workflow ($null -ne $assignment) "$($task.id) has no human assignment."
    Assert-Workflow (
        $implementation.Attributes.Count -eq 0
    ) "Unexpected Camunda user-task metadata on $($task.id)."
    foreach ($attribute in $assignment.Attributes) {
        Assert-Workflow (
            $attribute.NamespaceURI -eq "" -and
            $attribute.LocalName -in $allowedAssignmentAttributes
        ) "Unexpected human assignment attribute on $($task.id): $($attribute.Name)."
    }
    $assignee = if ($assignment.HasAttribute("assignee")) { $assignment.assignee } else { "" }
    $candidateGroups = if ($assignment.HasAttribute("candidateGroups")) { $assignment.candidateGroups } else { "" }
    $actualAssignment = "$assignee|$candidateGroups"
    Assert-Workflow ($actualAssignment -ceq $expectedAssignments[$task.id]) "Unexpected human assignment on $($task.id)."
}

$gatewayVariables = @{
    intake_outcome = "intakeDecision"
    requester_outcome = "requesterDecision"
    coordination_outcome = "coordinationDecision"
    hold_outcome = "holdDecision"
    allocation_outcome = "allocationDecision"
    planning_outcome = "planningDecision"
    delivery_outcome = "deliveryDecision"
    clarification_outcome = "clarificationDecision"
    lead_review_outcome = "leadReviewDecision"
    quality_outcome = "qualityDecision"
}
$gateways = $document.SelectNodes("//bpmn:exclusiveGateway", $namespaces)
Assert-Workflow ($gateways.Count -eq $gatewayVariables.Count) "Unexpected gateway count."
foreach ($gateway in $gateways) {
    Assert-Workflow $gatewayVariables.ContainsKey($gateway.id) "Unexpected gateway: $($gateway.id)"
    Assert-Workflow (
        -not $gateway.HasAttribute("default")
    ) "Exclusive gateway $($gateway.id) must not define a default flow."
}

$shapeElements = @($document.SelectNodes("//bpmndi:BPMNShape", $namespaces) | ForEach-Object bpmnElement)
$visualNodes = $document.SelectNodes("//bpmn:startEvent | //bpmn:endEvent | //bpmn:userTask | //bpmn:exclusiveGateway", $namespaces)
foreach ($node in $visualNodes) {
    Assert-Workflow ($node.id -in $shapeElements) "Missing diagram shape for $($node.id)."
}

$edgeElements = @($document.SelectNodes("//bpmndi:BPMNEdge", $namespaces) | ForEach-Object bpmnElement)
foreach ($flowId in $flowsById.Keys) {
    Assert-Workflow ($flowId -in $edgeElements) "Missing diagram edge for $flowId."
}

$terminalIds = @($document.SelectNodes("//bpmn:endEvent", $namespaces) | ForEach-Object id)
Assert-Workflow ($terminalIds.Count -eq 3) "The workflow must have three terminal outcomes."
foreach ($terminalId in @("completed", "closed", "cancelled")) {
    Assert-Workflow ($terminalId -in $terminalIds) "Missing terminal outcome: $terminalId"
}
$startIds = @($document.SelectNodes("//bpmn:startEvent", $namespaces) | ForEach-Object id)
Assert-Workflow (
    $startIds.Count -eq 1 -and $startIds[0] -ceq "request_submitted"
) "The workflow must have the request_submitted start event."

Write-Output "BPMN validation passed: $($tasks.Count) user tasks, $($gatewayVariables.Count) gateways, $($flowsById.Count) flows, complete diagram data."
