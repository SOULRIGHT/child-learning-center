# Lightweight Browser QA. Does not run the unittest suite.
# Usage: .\scripts\qa.ps1 step3|step4|step5
param(
    [Parameter(Position = 0)]
    [string]$Suite
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir

if ($Suite -ne 'step3' -and $Suite -ne 'step4' -and $Suite -ne 'step5') {
    Write-Host 'Usage: .\scripts\qa.ps1 step3|step4|step5'
    exit 2
}

$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
$DotVenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} elseif (Test-Path $DotVenvPython) {
    $Python = $DotVenvPython
} else {
    Write-Host 'QA Python interpreter not found.'
    Write-Host 'Use the app/test interpreter, not system or Anaconda Python.'
    Write-Host "  expected: $VenvPython"
    Write-Host "  fallback: $DotVenvPython"
    exit 1
}

Write-Host "QA Python: $Python"

& $Python -c "import flask, flask_login"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Selected Python cannot import Flask/flask_login.'
    Write-Host "  $Python"
    Write-Host 'Use the interpreter that already runs the app and unittest suite:'
    Write-Host '  .\venv\Scripts\python.exe'
    exit 1
}

& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('playwright') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Playwright is not installed.'
    Write-Host 'Install:'
    Write-Host "  $Python -m pip install -r requirements-dev.txt"
    Write-Host "  $Python -m playwright install chromium"
    exit 1
}

& $Python -c "from pathlib import Path; from playwright.sync_api import sync_playwright; p = sync_playwright().start(); ok = Path(p.chromium.executable_path).exists(); p.stop(); raise SystemExit(0 if ok else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Playwright Chromium is not installed.'
    Write-Host 'Install:'
    Write-Host "  $Python -m playwright install chromium"
    exit 1
}

& $Python (Join-Path $Root 'scripts\qa\run.py') $Suite
exit $LASTEXITCODE
