Set-StrictMode -Version Latest

function Get-BackupIntegrityKey {
    if ([string]::IsNullOrWhiteSpace($env:ISTARI_BACKUP_INTEGRITY_KEY_BASE64)) {
        throw 'Set ISTARI_BACKUP_INTEGRITY_KEY_BASE64 from the operational secret store.'
    }
    try {
        $key = [Convert]::FromBase64String($env:ISTARI_BACKUP_INTEGRITY_KEY_BASE64)
    }
    catch {
        throw 'ISTARI_BACKUP_INTEGRITY_KEY_BASE64 must be valid base64.'
    }
    if ($key.Length -lt 32) {
        throw 'The backup integrity key must contain at least 256 bits.'
    }
    return $key
}

function Get-BackupManifestPayload(
    [string]$BackupFile,
    [string]$CreatedAt,
    [string]$Hash
) {
    return [ordered]@{
        algorithm = 'SHA256'
        backupFile = $BackupFile
        createdAt = $CreatedAt
        hash = $Hash
    } | ConvertTo-Json -Compress
}

function Get-BackupManifestTag([string]$Payload) {
    $hmac = [System.Security.Cryptography.HMACSHA256]::new((Get-BackupIntegrityKey))
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Payload)
        return [Convert]::ToHexString($hmac.ComputeHash($bytes)).ToLowerInvariant()
    }
    finally {
        $hmac.Dispose()
    }
}

function New-AuthenticatedBackupManifest(
    [string]$BackupFile,
    [string]$CreatedAt,
    [string]$Hash
) {
    $payload = Get-BackupManifestPayload $BackupFile $CreatedAt $Hash
    return [ordered]@{
        algorithm = 'SHA256'
        authenticationAlgorithm = 'HMAC-SHA256'
        authenticationTag = Get-BackupManifestTag $payload
        backupFile = $BackupFile
        createdAt = $CreatedAt
        hash = $Hash
    }
}

function Assert-AuthenticatedBackupManifest([object]$Manifest, [string]$BackupPath) {
    if ($Manifest.algorithm -cne 'SHA256' -or
        $Manifest.authenticationAlgorithm -cne 'HMAC-SHA256' -or
        $Manifest.backupFile -cne [System.IO.Path]::GetFileName($BackupPath) -or
        [string]$Manifest.hash -notmatch '^[a-f0-9]{64}$') {
        throw 'The backup manifest metadata is invalid.'
    }
    $payload = Get-BackupManifestPayload `
        ([string]$Manifest.backupFile) `
        ([string]$Manifest.createdAt) `
        ([string]$Manifest.hash)
    try {
        $supplied = [Convert]::FromHexString([string]$Manifest.authenticationTag)
    }
    catch {
        throw 'The backup manifest authentication tag is invalid.'
    }
    $expected = [Convert]::FromHexString((Get-BackupManifestTag $payload))
    if (-not [System.Security.Cryptography.CryptographicOperations]::FixedTimeEquals(
        $supplied,
        $expected
    )) {
        throw 'Backup manifest authentication failed.'
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupPath).Hash.ToLowerInvariant()
    if ($actualHash -cne [string]$Manifest.hash) {
        throw 'Backup checksum does not match its authenticated manifest.'
    }
}
