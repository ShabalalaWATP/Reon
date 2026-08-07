#requires -Version 7.4
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$sourcePath = Join-Path $PSScriptRoot "service-request.bpmn"
$validatorPath = Join-Path $PSScriptRoot "validate-bpmn.ps1"

function Assert-InvalidMutation {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Mutate,
        [Parameter(Mandatory)]
        [string]$ExpectedMessage
    )

    [xml]$mutated = Get-Content -Raw -LiteralPath $sourcePath
    & $Mutate $mutated
    $temporaryPath = Join-Path (
        [IO.Path]::GetTempPath()
    ) "istari-bpmn-$([Guid]::NewGuid().ToString('N')).bpmn"
    try {
        $mutated.Save($temporaryPath)
        $actualMessage = $null
        try {
            & $validatorPath -BpmnPath $temporaryPath *> $null
        }
        catch {
            $actualMessage = $_.Exception.Message
        }
        if (-not $actualMessage -or $actualMessage -notlike "*$ExpectedMessage*") {
            throw "BPMN validator accepted an invalid mutation or returned an unexpected error."
        }
    }
    finally {
        [IO.File]::Delete($temporaryPath)
    }
}

Assert-InvalidMutation -ExpectedMessage "Unexpected condition" -Mutate {
    param([xml]$Document)
    $condition = $Document.SelectSingleNode(
        "//*[@id='flow_intake_progress']/*[local-name()='conditionExpression']"
    )
    $condition.InnerText = '= intakeDecision = "unsupported"'
}

Assert-InvalidMutation -ExpectedMessage "Unexpected human assignment" -Mutate {
    param([xml]$Document)
    $assignment = $Document.SelectSingleNode(
        "//*[@id='lead_review']//*[local-name()='assignmentDefinition']"
    )
    $assignment.SetAttribute("candidateGroups", "unapproved-group")
}

Assert-InvalidMutation -ExpectedMessage "Unexpected user-task label" -Mutate {
    param([xml]$Document)
    $task = $Document.SelectSingleNode("//*[@id='delivery_planning']")
    $task.SetAttribute("name", "Unapproved label")
}

Assert-InvalidMutation -ExpectedMessage "Unexpected workflow-variable documentation" -Mutate {
    param([xml]$Document)
    $documentation = $Document.SelectSingleNode(
        "//*[local-name()='process']/*[local-name()='documentation']"
    )
    $documentation.InnerText = $documentation.InnerText.Replace(
        "selectedOpsId",
        "requestTitle"
    )
}

Assert-InvalidMutation -ExpectedMessage "Unexpected human assignment attribute" -Mutate {
    param([xml]$Document)
    $assignment = $Document.SelectSingleNode(
        "//*[@id='intake_review']//*[local-name()='assignmentDefinition']"
    )
    $assignment.SetAttribute("candidateUsers", "unexpected-user")
}

Assert-InvalidMutation -ExpectedMessage "Unexpected endpoints" -Mutate {
    param([xml]$Document)
    $flow = $Document.SelectSingleNode("//*[@id='flow_quality_release']")
    $flow.SetAttribute("targetRef", "completed")
}

Assert-InvalidMutation -ExpectedMessage "Unsupported BPMN activity type: serviceTask" -Mutate {
    param([xml]$Document)
    $process = $Document.SelectSingleNode("//*[local-name()='process']")
    $activity = $Document.CreateElement(
        "bpmn",
        "serviceTask",
        "http://www.omg.org/spec/BPMN/20100524/MODEL"
    )
    $activity.SetAttribute("id", "automated_delivery")
    $null = $process.AppendChild($activity)
}

Assert-InvalidMutation -ExpectedMessage "Unsupported Zeebe extension: ioMapping" -Mutate {
    param([xml]$Document)
    $extensions = $Document.SelectSingleNode(
        "//*[@id='coordination_review']/*[local-name()='extensionElements']"
    )
    $mapping = $Document.CreateElement(
        "zeebe",
        "ioMapping",
        "http://camunda.org/schema/zeebe/1.0"
    )
    $null = $extensions.AppendChild($mapping)
}

Assert-InvalidMutation -ExpectedMessage "Unexpected BPMN user-task child" -Mutate {
    param([xml]$Document)
    $task = $Document.SelectSingleNode("//*[@id='delivery_work']")
    $loop = $Document.CreateElement(
        "bpmn",
        "multiInstanceLoopCharacteristics",
        "http://www.omg.org/spec/BPMN/20100524/MODEL"
    )
    $loop.SetAttribute("isSequential", "false")
    $null = $task.AppendChild($loop)
}

Assert-InvalidMutation -ExpectedMessage "Unexpected BPMN user-task attribute" -Mutate {
    param([xml]$Document)
    $task = $Document.SelectSingleNode("//*[@id='quality_review']")
    $task.SetAttribute("completionQuantity", "2")
}

Assert-InvalidMutation -ExpectedMessage "must not define a default flow" -Mutate {
    param([xml]$Document)
    $gateway = $Document.SelectSingleNode("//*[@id='quality_outcome']")
    $gateway.SetAttribute("default", "flow_quality_release")
}

Write-Output "BPMN validator mutation tests passed."
