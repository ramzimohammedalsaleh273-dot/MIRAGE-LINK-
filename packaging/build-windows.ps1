param(
    [string]$ScrcpyDirectory = "$env:USERPROFILE\Desktop\scrcpy\scrcpy-win64-v3.3.1"
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host '[1/5] Checking Python and packaging tools...'
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher (py) is required.'
}
py --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python Launcher is not working.'
}

py -m pip install -e '.[build]'
if ($LASTEXITCODE -ne 0) {
    throw 'Could not install project build dependencies.'
}

Write-Host '[2/5] Building the Windows GUI executable...'
if (Test-Path 'build\pyinstaller\MIRAGE-LINK') {
    Remove-Item 'build\pyinstaller\MIRAGE-LINK' -Recurse -Force
}
if (Test-Path 'build\work') {
    Remove-Item 'build\work' -Recurse -Force
}
if (Test-Path 'dist\MIRAGE-LINK') {
    Remove-Item 'dist\MIRAGE-LINK' -Recurse -Force
}

py -m PyInstaller --noconfirm --clean --windowed --name 'MIRAGE-LINK' --paths 'src' --collect-all av --collect-all PIL --distpath 'build\pyinstaller' --workpath 'build\work' 'packaging\run_gui.py'
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller failed.'
}

Write-Host '[3/5] Preparing portable directory...'
New-Item -ItemType Directory -Force -Path 'dist\MIRAGE-LINK' | Out-Null
Copy-Item 'build\pyinstaller\MIRAGE-LINK\*' 'dist\MIRAGE-LINK' -Recurse -Force
Copy-Item 'README.md' 'dist\MIRAGE-LINK\README-project.md' -Force
Copy-Item 'LICENSE' 'dist\MIRAGE-LINK\LICENSE-MIRAGE-LINK' -Force

$Launcher = Get-ChildItem 'packaging' -Filter '*.bat' | Select-Object -First 1
if ($null -eq $Launcher) {
    throw 'The portable BAT launcher was not found in packaging.'
}
Copy-Item $Launcher.FullName (Join-Path 'dist\MIRAGE-LINK' $Launcher.Name) -Force

Write-Host '[4/5] Including external scrcpy/ADB tools when available...'
if (Test-Path (Join-Path $ScrcpyDirectory 'scrcpy.exe')) {
    New-Item -ItemType Directory -Force -Path 'dist\MIRAGE-LINK\tools\scrcpy' | Out-Null
    Copy-Item (Join-Path $ScrcpyDirectory '*') 'dist\MIRAGE-LINK\tools\scrcpy' -Recurse -Force
} else {
    Write-Warning 'scrcpy package not found. The portable app will require scrcpy and ADB installed separately.'
}

Write-Host '[5/5] Writing package notes...'
$Notes = @(
    'MIRAGE LINK - Windows portable build'
    ''
    '1. Run the BAT launcher in this folder.'
    '2. Connect an Android phone by USB and approve the USB debugging prompt.'
    '3. For Wi-Fi: connect Windows to the phone hotspot, open the Android companion, approve screen capture, then click Wi-Fi display in this app.'
    '4. Video transport is provided by the separately licensed scrcpy project; ADB is also an external tool.'
    '5. If tools/scrcpy is absent, install scrcpy and Android Platform Tools and add them to PATH.'
    '6. Wi-Fi video uses the Android companion app (MediaProjection + H.264) and local UDP/TCP; no ADB wireless debugging is used.'
    '7. iPhone support and AI upscaling are not included.'
    '8. Keep all third-party license files shipped with their original tool packages.'
)
$Notes | Set-Content -Encoding UTF8 'dist\MIRAGE-LINK\NOTES.txt'

$OutputPath = (Resolve-Path 'dist\MIRAGE-LINK').Path
Write-Host ('Build completed: ' + $OutputPath)
