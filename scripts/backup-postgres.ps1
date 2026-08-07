[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:ISTARI_BACKUP_DATABASE_URL)) {
    throw 'Set ISTARI_BACKUP_DATABASE_URL for the least-privileged backup identity.'
}
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    throw 'pg_dump is required.'
}
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
    throw 'pg_restore is required.'
}
. (Join-Path $PSScriptRoot 'lib/PostgresServiceFile.ps1')

$target = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $target)) {
    New-Item -ItemType Directory -Path $target | Out-Null
}
$target = (Resolve-Path -LiteralPath $target).Path
$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$temporary = Join-Path $target "istari-$stamp.dump.partial"
$backup = Join-Path $target "istari-$stamp.dump"
$manifest = "$backup.sha256.json"
$previousServiceFile = $env:PGSERVICEFILE
$serviceFile = New-PostgresServiceFile $env:ISTARI_BACKUP_DATABASE_URL
$env:PGSERVICEFILE = $serviceFile

function Protect-BackupFile([string]$Path) {
    if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl = Get-Acl -LiteralPath $Path
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($rule in @($acl.Access)) {
            [void]$acl.RemoveAccessRuleAll($rule)
        }
        $access = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $identity,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($access)
        Set-Acl -LiteralPath $Path -AclObject $acl
        return
    }
    & chmod 600 -- $Path
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict backup permissions for $Path."
    }
}

try {
    & pg_dump `
        --dbname=service=istari_maintenance `
        --format=custom `
        --no-owner `
        --no-acl `
        --file=$temporary
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE."
    }
    & pg_restore --list $temporary | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Backup validation failed.'
    }
    Move-Item -LiteralPath $temporary -Destination $backup
    Protect-BackupFile $backup
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash.ToLowerInvariant()
    @{
        algorithm = 'SHA256'
        backupFile = [System.IO.Path]::GetFileName($backup)
        createdAt = [DateTimeOffset]::UtcNow.ToString('o')
        hash = $hash
    } | ConvertTo-Json | Set-Content -LiteralPath $manifest -Encoding utf8NoBOM
    Protect-BackupFile $manifest
    Write-Output ([pscustomobject]@{
        backup = $backup
        manifest = $manifest
        sha256 = $hash
        validated = $true
    })
}
finally {
    $env:PGSERVICEFILE = $previousServiceFile
    Remove-Item -LiteralPath $serviceFile -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary
    }
}
