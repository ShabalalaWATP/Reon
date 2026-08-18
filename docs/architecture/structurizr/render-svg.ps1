[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($ValidateOnly -and $Check) {
    throw 'Choose either -ValidateOnly or -Check, not both.'
}

$structurizrImage = 'structurizr/structurizr@sha256:251905a1a2d73195e84b784966babc71b329223fdbb25368261a9e3ba39041c4'
$plantUmlImage = 'plantuml/plantuml@sha256:47870c1f76cfb3747bc7090bfe83013a4e3105b5a0bb1515e2baf5d3e2b3ee9d'
$workspacePath = (Resolve-Path (Join-Path $PSScriptRoot 'workspace.dsl')).Path
$assetDirectory = (Resolve-Path (Join-Path $PSScriptRoot '../../assets/architecture')).Path
$workspaceInContainer = '/workspace/workspace.dsl'
$containerUser = if ($IsWindows) {
    '65532:65532'
}
else {
    '{0}:{1}' -f (& id -u), (& id -g)
}
$sandboxArguments = @(
    '--network', 'none',
    '--read-only',
    '--cap-drop', 'ALL',
    '--security-opt', 'no-new-privileges',
    '--pids-limit', '256',
    '--memory', '1g',
    '--cpus', '2',
    '--user', $containerUser,
    '--env', 'HOME=/tmp',
    '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=67108864'
)

$views = [ordered]@{
    SystemContext          = '01-system-context.svg'
    Containers             = '02-container-view.svg'
    RoutingWorkflow        = '03-routing-workflow.svg'
    DeliveryWorkflow       = '04-delivery-workflow.svg'
    DurableWorkflowCommand = '05-durable-workflow-command.svg'
    OrganisationRouting    = '06-organisation-routing.svg'
    ScannerSupplyChain     = '07-scanner-supply-chain.svg'
}

function Invoke-CheckedDocker {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE."
    }
}

Invoke-CheckedDocker -Arguments (@(
    'run', '--rm'
) + $sandboxArguments + @(
    '--mount', "type=bind,source=${workspacePath},target=${workspaceInContainer},readonly",
    $structurizrImage,
    'validate', '-w', $workspaceInContainer
))

if ($ValidateOnly) {
    return
}

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$workingDirectory = Join-Path $tempRoot (
    'mist-architecture-' + [guid]::NewGuid().ToString('N')
)
$resolvedWorkingDirectory = [System.IO.Path]::GetFullPath($workingDirectory)
if (-not $resolvedWorkingDirectory.StartsWith(
        $tempRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
    throw 'Refusing to create architecture output outside the temporary directory.'
}

New-Item -ItemType Directory -Path $resolvedWorkingDirectory | Out-Null
try {
    Invoke-CheckedDocker -Arguments (@(
        'run', '--rm'
    ) + $sandboxArguments + @(
        '--mount', "type=bind,source=${workspacePath},target=${workspaceInContainer},readonly",
        '--mount', "type=bind,source=${resolvedWorkingDirectory},target=/output",
        $structurizrImage,
        'export',
        '-w', $workspaceInContainer,
        '-f', 'plantuml/structurizr',
        '-o', '/output'
    ))

    $renderArguments = @('run', '--rm') + $sandboxArguments + @(
        '--mount', "type=bind,source=${resolvedWorkingDirectory},target=/data",
        $plantUmlImage,
        '-tsvg'
    )
    foreach ($viewKey in $views.Keys) {
        $renderArguments += "/data/structurizr-${viewKey}.puml"
    }
    Invoke-CheckedDocker -Arguments $renderArguments

    foreach ($entry in $views.GetEnumerator()) {
        $generated = Join-Path (
            $resolvedWorkingDirectory
        ) "structurizr-$($entry.Key).svg"
        if (-not (Test-Path -LiteralPath $generated -PathType Leaf)) {
            throw "Structurizr view $($entry.Key) did not render."
        }
        $committed = Join-Path $assetDirectory $entry.Value
        if ($Check) {
            if (-not (Test-Path -LiteralPath $committed -PathType Leaf)) {
                throw "Committed Structurizr view is missing: $($entry.Value)."
            }
            $generatedHash = (Get-FileHash -LiteralPath $generated -Algorithm SHA256).Hash
            $committedHash = (Get-FileHash -LiteralPath $committed -Algorithm SHA256).Hash
            if ($generatedHash -ne $committedHash) {
                throw "Committed Structurizr view is stale: $($entry.Value)."
            }
        }
        else {
            Copy-Item -LiteralPath $generated -Destination $committed -Force
        }
    }
}
finally {
    if (Test-Path -LiteralPath $resolvedWorkingDirectory) {
        Remove-Item -LiteralPath $resolvedWorkingDirectory -Recurse -Force
    }
}
