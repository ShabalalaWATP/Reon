Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$approvedLicences = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
@(
    '3-Clause BSD License',
    'Apache Software License',
    'Apache Software License; BSD License',
    'Apache-2.0',
    'Apache-2.0 OR BSD-2-Clause',
    'BSD License',
    'BSD-2-Clause',
    'BSD-3-Clause',
    'BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0',
    'ISC',
    'ISC License (ISCL)',
    'MIT',
    'MIT AND PSF-2.0',
    'MIT License',
    'MIT-0',
    'MIT-CMU',
    'Mozilla Public License 2.0',
    'Mozilla Public License 2.0 (MPL 2.0)',
    'MPL-2.0 AND MIT',
    'MPL-2.0',
    'PSF',
    'PSF-2.0',
    'Python Software Foundation',
    'Python Software Foundation License',
    'The Unlicense (Unlicense)',
    'Unlicense'
) | ForEach-Object { [void]$approvedLicences.Add($_) }
$reviewedUnknown = @{
    'camunda-orchestration-sdk' = @{
        Version = '9.0.1'
        ReportedLicence = 'UNKNOWN'
    }
    'mist-service-api' = @{
        Version = '0.1.0'
        ReportedLicence = 'UNKNOWN'
    }
}
# These two locked wheels publish incomplete licence metadata. Their installed
# licence files were reviewed as Apache-2.0 (fastembed) and MIT
# (py-rust-stemmers). Match the reported value exactly so a metadata change
# returns the package to manual review instead of silently widening policy.
$reviewedMetadata = @{
    'fastembed' = @{
        Version = '0.8.0'
        ReportedLicence = 'Other/Proprietary License'
        LicenceFileSha256 = 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'
    }
    'py_rust_stemmers' = @{
        Version = '0.1.8'
        ReportedLicence = 'UNKNOWN'
        LicenceFileSha256 = '9449057776c984e88e29ea1ee135caeba2347756d0c74480f7afc4f16f636f68'
    }
}

function Test-ApprovedLicence([string]$Licence) {
    return $approvedLicences.Contains($Licence.Trim())
}

function Test-ReviewedPackage(
    [object]$Package,
    [hashtable]$Review,
    [switch]$RequireLicenceFile
) {
    if (
        [string]$Package.Version -ne $Review.Version -or
        [string]$Package.License -ne $Review.ReportedLicence
    ) {
        return $false
    }
    if (-not $RequireLicenceFile) {
        return $true
    }
    $licencePath = [string]$Package.LicenseFile
    return (
        (Test-Path -LiteralPath $licencePath -PathType Leaf) -and
        (Get-FileHash -LiteralPath $licencePath -Algorithm SHA256).Hash -eq
            $Review.LicenceFileSha256
    )
}

foreach ($unapprovedFixture in @('NOT MIT', 'Apache-2.0 WITH unreviewed-exception')) {
    if (Test-ApprovedLicence $unapprovedFixture) {
        throw "Licence policy regression accepted: $unapprovedFixture"
    }
}
$driftFixture = [pscustomobject]@{
    Version = '9.0.2'
    License = 'UNKNOWN'
    LicenseFile = ''
}
if (Test-ReviewedPackage $driftFixture $reviewedUnknown['camunda-orchestration-sdk']) {
    throw 'Licence policy regression accepted a version-drifted exception.'
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

$pythonRaw = & uv run --directory apps/api pip-licenses --format=json --from=mixed --with-license-file
if ($LASTEXITCODE -ne 0) {
    throw 'Could not enumerate Python licences.'
}
$python = $pythonRaw | ConvertFrom-Json
foreach ($package in $python) {
    $name = [string]$package.Name
    $version = [string]$package.Version
    $licence = [string]$package.License
    if (Test-ApprovedLicence $licence) {
        continue
    }
    if ($reviewedUnknown.ContainsKey($name)) {
        $review = $reviewedUnknown[$name]
        if (Test-ReviewedPackage $package $review) {
            continue
        }
    }
    if ($reviewedMetadata.ContainsKey($name)) {
        $review = $reviewedMetadata[$name]
        if (Test-ReviewedPackage $package $review -RequireLicenceFile) {
            continue
        }
    }
    $failures.Add("Python package $name $version has unapproved licence: $licence")
}

if ($failures.Count -gt 0) {
    throw ($failures -join [Environment]::NewLine)
}
Write-Output (
    "Licence gate passed for {0} Node licence groups and {1} Python packages." -f `
        $node.Count,
        $python.Count
)
