#requires -Version 7.4
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$SkipWorkflowDeployment,
    [switch]$SeedDemoData,
    [string]$ComposeProjectName = $(
        if ($env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME }
        else { "mist-service-local" }
    )
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentPath = Join-Path $repositoryRoot ".env"

if ($ComposeProjectName -notmatch "^[a-z0-9][a-z0-9_-]{0,62}$") {
    throw "ComposeProjectName must be a bounded lower-case Compose project name."
}

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "Create .env from .env.example and replace every CHANGE_ME value first."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $environmentPath) {
    if ($line -match "^\s*([A-Z][A-Z0-9_]*)=(.*)$") {
        $settings[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}

$requiredSettings = @(
    "POSTGRES_ADMIN_PASSWORD",
    "APP_DATABASE_NAME",
    "APP_DATABASE_USER",
    "APP_DATABASE_PASSWORD",
    "APP_RUNTIME_DATABASE_USER",
    "APP_RUNTIME_DATABASE_PASSWORD",
    "APP_BACKUP_DATABASE_USER",
    "APP_BACKUP_DATABASE_PASSWORD",
    "APP_MAINTENANCE_DATABASE_USER",
    "APP_MAINTENANCE_DATABASE_PASSWORD",
    "CAMUNDA_DATABASE_NAME",
    "CAMUNDA_DATABASE_USER",
    "CAMUNDA_DATABASE_PASSWORD",
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "ENVIRONMENT",
    "SESSION_COOKIE_SECURE",
    "WEB_ORIGIN",
    "TRUSTED_ORIGINS",
    "ALLOW_DEMO_USERS",
    "DEMO_USER_PASSWORD",
    "AUDIT_HMAC_KEY",
    "SECURITY_PSEUDONYM_KEY"
)
foreach ($settingName in $requiredSettings) {
    $settingValue = $settings[$settingName]
    if (-not $settingValue -or $settingValue -match "CHANGE_ME") {
        throw "Set a non-placeholder value for $settingName in .env."
    }
}

if ($settings.ENVIRONMENT -ne "local") {
    throw "The local Compose helper requires ENVIRONMENT=local."
}

$databaseUsers = @(
    $settings.APP_DATABASE_USER,
    $settings.APP_RUNTIME_DATABASE_USER,
    $settings.APP_BACKUP_DATABASE_USER,
    $settings.APP_MAINTENANCE_DATABASE_USER,
    $settings.CAMUNDA_DATABASE_USER
)
if (($databaseUsers | Select-Object -Unique).Count -ne $databaseUsers.Count) {
    throw "Migration, runtime, backup and Camunda database identities must differ."
}

$databasePasswords = @(
    $settings.POSTGRES_ADMIN_PASSWORD,
    $settings.APP_DATABASE_PASSWORD,
    $settings.APP_RUNTIME_DATABASE_PASSWORD,
    $settings.APP_BACKUP_DATABASE_PASSWORD,
    $settings.APP_MAINTENANCE_DATABASE_PASSWORD,
    $settings.CAMUNDA_DATABASE_PASSWORD
)
if (($databasePasswords | Select-Object -Unique).Count -ne $databasePasswords.Count) {
    throw "Bootstrap, migration, runtime, backup and Camunda passwords must differ."
}

if ($settings.DEMO_USER_PASSWORD -in $databasePasswords) {
    throw "The demo-user password must differ from every database password."
}
if ([Text.Encoding]::UTF8.GetByteCount($settings.AUDIT_HMAC_KEY) -lt 32) {
    throw "AUDIT_HMAC_KEY must contain at least 32 UTF-8 bytes."
}
if ($settings.AUDIT_HMAC_KEY -in ($databasePasswords + $settings.DEMO_USER_PASSWORD)) {
    throw "AUDIT_HMAC_KEY must differ from database and demo-user passwords."
}
if ([Text.Encoding]::UTF8.GetByteCount($settings.SECURITY_PSEUDONYM_KEY) -lt 32) {
    throw "SECURITY_PSEUDONYM_KEY must contain at least 32 UTF-8 bytes."
}
if ($settings.SECURITY_PSEUDONYM_KEY -in (
        $databasePasswords + $settings.DEMO_USER_PASSWORD + $settings.AUDIT_HMAC_KEY
    )) {
    throw "SECURITY_PSEUDONYM_KEY must differ from audit, database and demo-user secrets."
}

$databaseUri = [Uri]$settings.DATABASE_URL
$databaseIdentity = $databaseUri.UserInfo.Split(":", 2)
$databaseName = [Uri]::UnescapeDataString($databaseUri.AbsolutePath.TrimStart("/"))
if ($databaseIdentity.Count -ne 2 -or
    $databaseUri.Scheme -ne "postgresql+asyncpg" -or
    $databaseUri.Host -ne "postgres" -or
    $databaseUri.Port -ne 5432 -or
    $databaseUri.Query -or
    $databaseUri.Fragment -or
    [Uri]::UnescapeDataString($databaseIdentity[0]) -cne $settings.APP_RUNTIME_DATABASE_USER -or
    [Uri]::UnescapeDataString($databaseIdentity[1]) -cne $settings.APP_RUNTIME_DATABASE_PASSWORD -or
    $databaseName -cne $settings.APP_DATABASE_NAME) {
    throw "DATABASE_URL must target the runtime role and application database on postgres:5432."
}

$migrationUri = [Uri]$settings.MIGRATION_DATABASE_URL
$migrationIdentity = $migrationUri.UserInfo.Split(":", 2)
$migrationDatabase = [Uri]::UnescapeDataString($migrationUri.AbsolutePath.TrimStart("/"))
if ($migrationIdentity.Count -ne 2 -or
    $migrationUri.Scheme -ne "postgresql+asyncpg" -or
    $migrationUri.Host -ne "postgres" -or
    $migrationUri.Port -ne 5432 -or
    $migrationUri.Query -or
    $migrationUri.Fragment -or
    [Uri]::UnescapeDataString($migrationIdentity[0]) -cne $settings.APP_DATABASE_USER -or
    [Uri]::UnescapeDataString($migrationIdentity[1]) -cne $settings.APP_DATABASE_PASSWORD -or
    $migrationDatabase -cne $settings.APP_DATABASE_NAME) {
    throw "MIGRATION_DATABASE_URL must target the migration owner and application database."
}

$webOrigin = [Uri]$settings.WEB_ORIGIN
if ($webOrigin.Scheme -ne "http" -or $webOrigin.Host -notin @("127.0.0.1", "localhost", "::1")) {
    throw "WEB_ORIGIN must be a loopback HTTP origin for local Compose."
}
foreach ($originText in $settings.TRUSTED_ORIGINS.Split(',')) {
    $trustedOrigin = [Uri]$originText.Trim()
    if ($trustedOrigin.Scheme -ne "http" -or
        $trustedOrigin.Host -notin @("127.0.0.1", "localhost", "::1")) {
        throw "TRUSTED_ORIGINS may contain only loopback HTTP origins locally."
    }
}

Push-Location $repositoryRoot
try {
    $arguments = @(
        "compose", "--project-name", $ComposeProjectName,
        "up", "--detach", "--wait"
    )
    if (-not $NoBuild) {
        $arguments += "--build"
    }

    & docker @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose did not reach a healthy state."
    }

    if (-not $SkipWorkflowDeployment) {
        & (Join-Path $PSScriptRoot "deploy-workflow-compose.ps1") `
            -ComposeProjectName $ComposeProjectName `
            -OperatorSubject ("local:{0}" -f [Environment]::UserName)
        if ($LASTEXITCODE -ne 0) {
            throw "Workflow deployment failed."
        }
    }

    if ($SeedDemoData) {
        Write-Host "Seeding the demo request portfolio (idempotent; reruns resume)."
        $planPath = Join-Path $repositoryRoot "output/demo-portfolio-plan.json"
        Push-Location (Join-Path $repositoryRoot "apps/api")
        try {
            $env:DEMO_USER_PASSWORD = $settings.DEMO_USER_PASSWORD
            & uv run python ../../scripts/seed-demo-portfolio.py --plan-output $planPath
            if ($LASTEXITCODE -ne 0) {
                throw "Demo portfolio seeding did not complete; rerun with -SeedDemoData to resume."
            }
        }
        finally {
            Pop-Location
        }
        Write-Host "Spreading seeded history across recent weeks for statistics."
        Get-Content -Raw (Join-Path $repositoryRoot "scripts/lib/demo_portfolio_backdate.py") |
            & docker compose --project-name $ComposeProjectName `
                exec --no-TTY api sh -c 'cat > /tmp/backdate.py'
        Get-Content -Raw $planPath |
            & docker compose --project-name $ComposeProjectName `
                exec --no-TTY api sh -c 'cat > /tmp/plan.json'
        & docker compose --project-name $ComposeProjectName exec --no-TTY `
            -e ("DATABASE_URL={0}" -f $settings.MIGRATION_DATABASE_URL) `
            api python /tmp/backdate.py /tmp/plan.json
        if ($LASTEXITCODE -ne 0) {
            throw "Demo history backdating failed."
        }
    }
}
finally {
    Pop-Location
}
