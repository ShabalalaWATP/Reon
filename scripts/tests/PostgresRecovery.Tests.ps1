Describe 'PostgreSQL recovery transport policy' {
    BeforeAll {
        $scriptsRoot = Split-Path -Parent $PSScriptRoot
        . (Join-Path $scriptsRoot 'lib/PostgresServiceFile.ps1')
        function Assert-Matches([string]$Actual, [string]$Pattern) {
            if ($Actual -notmatch $Pattern) {
                throw "Expected '$Actual' to match '$Pattern'."
            }
        }
        function Assert-ThrowsLike([scriptblock]$Action, [string]$Pattern) {
            try {
                & $Action
            }
            catch {
                if ($_.Exception.Message -like $Pattern) { return }
                throw "Expected an error like '$Pattern', got '$($_.Exception.Message)'."
            }
            throw "Expected an error like '$Pattern', but no error was raised."
        }
    }
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
                Assert-Matches (Get-Content -Raw -LiteralPath $serviceFile) "host='$([regex]::Escape($hostName))'"
            }
            finally {
                Remove-Item -LiteralPath $serviceFile -Force
            }
        }
    }

    It 'does not broaden the exception to another address considered loopback' {
        Assert-ThrowsLike {
            New-PostgresServiceFile 'postgresql://user:password@127.0.0.2/database'
        } '*require sslmode=verify-full*'
    }

    It 'requires verify-full and the exact approved existing trust path remotely' {
        $certificate = Join-Path $TestDrive 'approved-ca.pem'
        Set-Content -LiteralPath $certificate -Value 'synthetic test CA'
        $env:ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT = $certificate
        $encodedCertificate = [uri]::EscapeDataString($certificate)

        Assert-ThrowsLike {
            New-PostgresServiceFile 'postgresql://user:password@db.example.test/database?sslmode=require'
        } '*require sslmode=verify-full*'
        Assert-ThrowsLike {
            New-PostgresServiceFile 'postgresql://user:password@db.example.test/database?sslmode=verify-full'
        } '*require sslrootcert*'
        Assert-ThrowsLike {
            New-PostgresServiceFile "postgresql://user:password@db.example.test/database?sslmode=verify-full&sslrootcert=$encodedCertificate.other"
        } '*must be the existing approved CA bundle path*'

        $serviceFile = New-PostgresServiceFile "postgresql://user:password@db.example.test/database?sslmode=verify-full&sslrootcert=$encodedCertificate"
        try {
            Assert-Matches (Get-Content -Raw -LiteralPath $serviceFile) "sslmode='verify-full'"
            Assert-Matches (Get-Content -Raw -LiteralPath $serviceFile) 'sslrootcert='
        }
        finally {
            Remove-Item -LiteralPath $serviceFile -Force
        }
    }
}

Describe 'Authenticated backup manifests' {
    BeforeAll {
        $scriptsRoot = Split-Path -Parent $PSScriptRoot
        . (Join-Path $scriptsRoot 'lib/BackupManifest.ps1')
        function Assert-DoesNotThrow([scriptblock]$Action) {
            try { & $Action }
            catch { throw "Expected no error, got '$($_.Exception.Message)'." }
        }
        function Assert-ThrowsLike([scriptblock]$Action, [string]$Pattern) {
            try {
                & $Action
            }
            catch {
                if ($_.Exception.Message -like $Pattern) { return }
                throw "Expected an error like '$Pattern', got '$($_.Exception.Message)'."
            }
            throw "Expected an error like '$Pattern', but no error was raised."
        }
    }
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
        Assert-DoesNotThrow { Assert-AuthenticatedBackupManifest $manifest $script:backupPath }
    }

    It 'rejects a tampered dump' {
        $manifest = New-AuthenticatedBackupManifest 'istari.dump' '2026-08-13T00:00:00Z' $script:hash
        Add-Content -LiteralPath $script:backupPath -Value 'tamper'
        Assert-ThrowsLike {
            Assert-AuthenticatedBackupManifest $manifest $script:backupPath
        } '*checksum does not match its authenticated manifest*'
    }

    It 'rejects a coordinated dump and manifest hash change without the key' {
        $manifest = New-AuthenticatedBackupManifest 'istari.dump' '2026-08-13T00:00:00Z' $script:hash
        Add-Content -LiteralPath $script:backupPath -Value 'tamper'
        $manifest.hash = (Get-FileHash -Algorithm SHA256 $script:backupPath).Hash.ToLowerInvariant()
        Assert-ThrowsLike {
            Assert-AuthenticatedBackupManifest $manifest $script:backupPath
        } '*manifest authentication failed*'
    }
}
