Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$approvedPatterns = @(
    'Apache',
    'BSD',
    'ISC',
    'MIT',
    'Mozilla Public License 2.0',
    'MPL-2.0',
    'PSF',
    'Python Software Foundation',
    'Unlicense'
)
$reviewedUnknown = @{
    'camunda-orchestration-sdk' = 'Camunda License 1.0, selected workflow dependency'
    'mist-service-api' = 'Private first-party application'
}
# These two locked wheels publish incomplete licence metadata. Their installed
# licence files were reviewed as Apache-2.0 (fastembed) and MIT
# (py-rust-stemmers). Match the reported value exactly so a metadata change
# returns the package to manual review instead of silently widening policy.
$reviewedMetadata = @{
    'fastembed' = 'Other/Proprietary License'
    'py_rust_stemmers' = 'UNKNOWN'
}

function Test-ApprovedLicence([string]$Licence) {
    foreach ($pattern in $approvedPatterns) {
        if ($Licence.Contains($pattern, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

$nodeRaw = & corepack pnpm licenses list --prod --json
if ($LASTEXITCODE -ne 0) {
    throw 'Could not enumerate production Node licences.'
}
$node = $nodeRaw | ConvertFrom-Json -AsHashtable
$failures = [System.Collections.Generic.List[string]]::new()
foreach ($licence in $node.Keys) {
    if (-not (Test-ApprovedLicence ([string]$licence))) {
        $failures.Add("Node licence is not approved: $licence")
    }
}

$pythonRaw = & uv run --directory apps/api pip-licenses --format=json --from=mixed
if ($LASTEXITCODE -ne 0) {
    throw 'Could not enumerate Python licences.'
}
$python = $pythonRaw | ConvertFrom-Json
foreach ($package in $python) {
    $name = [string]$package.Name
    $licence = [string]$package.License
    if (Test-ApprovedLicence $licence) {
        continue
    }
    if ($licence -eq 'UNKNOWN' -and $reviewedUnknown.ContainsKey($name)) {
        continue
    }
    if (
        $reviewedMetadata.ContainsKey($name) -and
        $licence -eq $reviewedMetadata[$name]
    ) {
        continue
    }
    $failures.Add("Python package $name has unapproved licence: $licence")
}

if ($failures.Count -gt 0) {
    throw ($failures -join [Environment]::NewLine)
}
Write-Output (
    "Licence gate passed for {0} Node licence groups and {1} Python packages." -f `
        $node.Count,
        $python.Count
)
