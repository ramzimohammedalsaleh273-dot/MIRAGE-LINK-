param(
    [string]$ScrcpyDirectory = "$env:USERPROFILE\Desktop\scrcpy\scrcpy-win64-v3.3.1"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/5] Checking Python and packaging tools..."
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python Launcher (py) is required." }
py -m pip install --upgrade pip
py -m pip install -e ".[build]"

Write-Host "[2/5] Building the Windows GUI executable..."
if (Test-Path "build\MIRAGE-LINK") { Remove-Item "build\MIRAGE-LINK" -Recurse -Force }
if (Test-Path "dist\MIRAGE-LINK") { Remove-Item "dist\MIRAGE-LINK" -Recurse -Force }
py -m PyInstaller --noconfirm --clean --windowed --name "MIRAGE-LINK" --paths "src" --distpath "build\pyinstaller" --workpath "build\work" "packaging\run_gui.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

Write-Host "[3/5] Preparing portable directory..."
New-Item -ItemType Directory -Force -Path "dist\MIRAGE-LINK" | Out-Null
Copy-Item "build\pyinstaller\MIRAGE-LINK\*" "dist\MIRAGE-LINK" -Recurse -Force
Copy-Item "README.md" "dist\MIRAGE-LINK\README-project.md" -Force
Copy-Item "LICENSE" "dist\MIRAGE-LINK\LICENSE-MIRAGE-LINK" -Force
Copy-Item "packaging\تشغيل-MIRAGE-LINK.bat" "dist\MIRAGE-LINK\تشغيل-MIRAGE-LINK.bat" -Force

Write-Host "[4/5] Including external scrcpy/ADB tools when available..."
if (Test-Path (Join-Path $ScrcpyDirectory "scrcpy.exe")) {
    New-Item -ItemType Directory -Force -Path "dist\MIRAGE-LINK\tools\scrcpy" | Out-Null
    Copy-Item (Join-Path $ScrcpyDirectory "*") "dist\MIRAGE-LINK\tools\scrcpy" -Recurse -Force
} else {
    Write-Warning "scrcpy package not found. The portable app will require scrcpy and ADB installed separately."
}

Write-Host "[5/5] Writing package notes..."
@'
MIRAGE LINK — Windows portable build

1. Run تشغيل-MIRAGE-LINK.bat.
2. Connect an Android phone by USB and approve the USB debugging prompt.
3. For wireless use, pair/connect from Android Developer Options while both devices are on the same local network.
4. This app is an Arabic GUI/orchestrator. Video transport is provided by the separately licensed scrcpy project; ADB is also an external tool.
5. If tools/scrcpy is absent, install scrcpy and Android Platform Tools and add them to PATH.
6. This build does not contain an Android companion app, iOS receiver, AI upscaler, or a proprietary video engine.
7. Keep all third-party license files shipped with their original tool packages.
'@ | Set-Content -Encoding UTF8 "dist\MIRAGE-LINK\ملاحظات-التشغيل.txt"
Write-Host "Build completed: $((Resolve-Path 'dist\MIRAGE-LINK').Path)"
