$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsRoot = Split-Path -Parent $here
. (Join-Path $scriptsRoot 'lib/PostgresServiceFile.ps1')
. (Join-Path $scriptsRoot 'lib/BackupManifest.ps1')

Describe 'PostgreSQL recovery transport policy' {
    BeforeEach {
        $script:previousApprovedCert = $env:ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT
    }
    AfterEach {
        $env:ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT = $script:previousApprovedCert
    }

    It 'allows only the three exact loopback hosts without TLS parameters' {
        foreach ($hostName in @('localhost', '127.0.0.1', '[::1]')) {
            $serviceFile = New-PostgresServiceFile "postgresql://user:password@$hostName/database"
            try {
                (Get-Content -Raw -LiteralPath $serviceFile) | Should Match "host='$([regex]::Escape($hostName))'"
            }
            finally {
                Remove-Item -LiteralPath $serviceFile -Force
            }
        }
    }

    It 'does not broaden the exception to another address considered loopback' {
        { New-PostgresServiceFile 'postgresql://user:password@127.0.0.2/database' } |
            Should Throw 'Non-loopback PostgreSQL URLs require sslmode=verify-full.'
    }

    It 'requires verify-full and the exact approved existing trust path remotely' {
        $certificate = Join-Path $TestDrive 'approved-ca.pem'
        Set-Content -LiteralPath $certificate -Value 'synthetic test CA'
        $env:ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT = $certificate
        $encodedCertificate = [uri]::EscapeDataString($certificate)

        { New-PostgresServiceFile 'postgresql://user:password@db.example.test/database?sslmode=require' } |
            Should Throw 'Non-loopback PostgreSQL URLs require sslmode=verify-full.'
        { New-PostgresServiceFile 'postgresql://user:password@db.example.test/database?sslmode=verify-full' } |
            Should Throw 'Non-loopback PostgreSQL URLs require sslrootcert.'
        { New-PostgresServiceFile "postgresql://user:password@db.example.test/database?sslmode=verify-full&sslrootcert=$encodedCertificate.other" } |
            Should Throw 'sslrootcert must be the existing approved CA bundle path.'

        $serviceFile = New-PostgresServiceFile "postgresql://user:password@db.example.test/database?sslmode=verify-full&sslrootcert=$encodedCertificate"
        try {
            (Get-Content -Raw -LiteralPath $serviceFile) | Should Match "sslmode='verify-full'"
            (Get-Content -Raw -LiteralPath $serviceFile) | Should Match 'sslrootcert='
        }
        finally {
            Remove-Item -LiteralPath $serviceFile -Force
        }
    }
}

Describe 'Authenticated backup manifests' {
    BeforeEach {
        $script:previousIntegrityKey = $env:ISTARI_BACKUP_INTEGRITY_KEY_BASE64
        $env:ISTARI_BACKUP_INTEGRITY_KEY_BASE64 = [Convert]::ToBase64String([byte[]](1..32))
        $script:backupPath = Join-Path $TestDrive 'istari.dump'
        Set-Content -LiteralPath $script:backupPath -Value 'synthetic backup'
        $script:hash = (Get-FileHash -Algorithm SHA256 $script:backupPath).Hash.ToLowerInvariant()
    }
    AfterEach {
        $env:ISTARI_BACKUP_INTEGRITY_KEY_BASE64 = $script:previousIntegrityKey
    }

    It 'accepts an unchanged dump and authenticated manifest' {
        $manifest = New-AuthenticatedBackupManifest 'istari.dump' '2026-08-13T00:00:00Z' $script:hash
        { Assert-AuthenticatedBackupManifest $manifest $script:backupPath } | Should Not Throw
    }

    It 'rejects a tampered dump' {
        $manifest = New-AuthenticatedBackupManifest 'istari.dump' '2026-08-13T00:00:00Z' $script:hash
        Add-Content -LiteralPath $script:backupPath -Value 'tamper'
        { Assert-AuthenticatedBackupManifest $manifest $script:backupPath } |
            Should Throw 'Backup checksum does not match its authenticated manifest.'
    }

    It 'rejects a coordinated dump and manifest hash change without the key' {
        $manifest = New-AuthenticatedBackupManifest 'istari.dump' '2026-08-13T00:00:00Z' $script:hash
        Add-Content -LiteralPath $script:backupPath -Value 'tamper'
        $manifest.hash = (Get-FileHash -Algorithm SHA256 $script:backupPath).Hash.ToLowerInvariant()
        { Assert-AuthenticatedBackupManifest $manifest $script:backupPath } |
            Should Throw 'Backup manifest authentication failed.'
    }
}
