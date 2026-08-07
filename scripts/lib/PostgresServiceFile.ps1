Set-StrictMode -Version Latest

function ConvertTo-LibpqServiceValue([string]$Value) {
    $escaped = $Value.Replace('\', '\\').Replace("'", "\'")
    return "'$escaped'"
}

function Protect-PostgresServiceFile([string]$Path) {
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
        throw 'Could not restrict the temporary PostgreSQL service file.'
    }
}

function New-PostgresServiceFile([string]$DatabaseUrl) {
    try {
        $uri = [System.Uri]::new($DatabaseUrl)
    }
    catch {
        throw 'The PostgreSQL database URL is invalid.'
    }
    if ($uri.Scheme -notin @('postgres', 'postgresql') -or [string]::IsNullOrWhiteSpace($uri.Host)) {
        throw 'A postgresql:// database URL with a host is required.'
    }
    $identity = $uri.UserInfo.Split(':', 2)
    if ($identity.Count -ne 2) {
        throw 'The PostgreSQL database URL must contain a username and password.'
    }
    $database = [System.Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart('/'))
    if ([string]::IsNullOrWhiteSpace($database)) {
        throw 'The PostgreSQL database URL must contain a database name.'
    }
    $values = [ordered]@{
        host = $uri.Host
        port = $(if ($uri.IsDefaultPort) { '5432' } else { [string]$uri.Port })
        user = [System.Uri]::UnescapeDataString($identity[0])
        password = [System.Uri]::UnescapeDataString($identity[1])
        dbname = $database
    }
    foreach ($pair in $uri.Query.TrimStart('?').Split('&', [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $parts = $pair.Split('=', 2)
        $name = [System.Uri]::UnescapeDataString($parts[0]).ToLowerInvariant()
        if ($name -in @('sslmode', 'sslrootcert', 'sslcert', 'sslkey') -and $parts.Count -eq 2) {
            $values[$name] = [System.Uri]::UnescapeDataString($parts[1])
        }
    }
    $path = [System.IO.Path]::GetTempFileName()
    try {
        $lines = @('[istari_maintenance]')
        foreach ($item in $values.GetEnumerator()) {
            $lines += "$($item.Key)=$(ConvertTo-LibpqServiceValue ([string]$item.Value))"
        }
        Set-Content -LiteralPath $path -Value $lines -Encoding utf8NoBOM
        Protect-PostgresServiceFile $path
        return $path
    }
    catch {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw
    }
}
