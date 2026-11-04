$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "ثبّت Python 3.10 أو أحدث مع خيار Python Launcher."
}
py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "تعذر تحديث pip." }
py -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "فشل تثبيت MIRAGE LINK." }
Write-Host "اكتمل تثبيت MIRAGE LINK. نفّذ scripts\تشغيل-MIRAGE-LINK.ps1 -Action doctor" -ForegroundColor Green
