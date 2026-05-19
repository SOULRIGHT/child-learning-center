param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$BackupRoot = $env:BACKUP_ROOT
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp][$Level] $Message"
    Write-Output $line
    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value $line
    }
}

function Normalize-DatabaseUrl {
    param([string]$Url)
    if (-not $Url) {
        return $null
    }
    # libpq(pg_dump)는 postgresql:// 스킴을 권장
    if ($Url.StartsWith("postgres://")) {
        return "postgresql://" + $Url.Substring("postgres://".Length)
    }
    return $Url
}

try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $projectRoot = Resolve-Path (Join-Path $scriptDir "..\..")

    if (-not $BackupRoot) {
        $BackupRoot = Join-Path $projectRoot "Backups\postgres"
    }

    $now = Get-Date
    $targetDir = Join-Path $BackupRoot ($now.ToString("yyyy\\MM"))
    $logDir = Join-Path $BackupRoot "_logs"
    New-Item -Path $targetDir -ItemType Directory -Force | Out-Null
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null

    $script:LogFile = Join-Path $logDir ("pg_dump_" + $now.ToString("yyyy-MM-dd") + ".log")

    $normalizedUrl = Normalize-DatabaseUrl -Url $DatabaseUrl
    if (-not $normalizedUrl) {
        throw "DATABASE_URL 환경변수가 없습니다. 백업을 중단합니다."
    }

    $pgDumpCmd = $env:PG_DUMP_PATH
    if (-not $pgDumpCmd) {
        $pgDumpCmd = "pg_dump"
    }

    $backupFile = Join-Path $targetDir ("postgres_" + $now.ToString("yyyy-MM-dd_HH-mm") + ".dump")
    Write-Log "백업 시작: $backupFile"
    Write-Log "저장 루트: $BackupRoot"

    $args = @(
        "--format=custom",
        "--file", $backupFile,
        "--no-owner",
        "--no-privileges",
        "--dbname", $normalizedUrl
    )

    & $pgDumpCmd @args 2>&1 | ForEach-Object {
        Add-Content -Path $script:LogFile -Value $_
    }

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "pg_dump 실패 (exit code: $exitCode)"
    }

    if (-not (Test-Path $backupFile)) {
        throw "백업 파일이 생성되지 않았습니다: $backupFile"
    }

    $fileInfo = Get-Item $backupFile
    if ($fileInfo.Length -le 0) {
        throw "백업 파일 크기가 0입니다: $backupFile"
    }

    Write-Log ("백업 성공: {0} ({1:N2} MB)" -f $backupFile, ($fileInfo.Length / 1MB)) "SUCCESS"
    exit 0
}
catch {
    Write-Log $_.Exception.Message "ERROR"
    exit 1
}
