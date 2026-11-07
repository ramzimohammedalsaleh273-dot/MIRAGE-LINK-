param(
  [ValidateSet("doctor","devices","stream","gui","help")]
  [string]$Action = "doctor",
  [string]$Serial = "",
  [string]$AdbPath = "",
  [string]$ScrcpyPath = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = (Join-Path $Root "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH

$KnownDir = Join-Path $env:USERPROFILE "Desktop\scrcpy\scrcpy-win64-v3.3.1"
if (-not $AdbPath -and (Test-Path (Join-Path $KnownDir "adb.exe"))) {
  $AdbPath = Join-Path $KnownDir "adb.exe"
}
if (-not $ScrcpyPath -and (Test-Path (Join-Path $KnownDir "scrcpy.exe"))) {
  $ScrcpyPath = Join-Path $KnownDir "scrcpy.exe"
}
if ($AdbPath) { $env:MIRAGE_ADB = $AdbPath }
if ($ScrcpyPath) { $env:MIRAGE_SCRCPY = $ScrcpyPath }

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Python Launcher غير موجود. ثبّت Python 3.10 أو أحدث ثم أعد المحاولة."
}
py -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ مطلوب'"
if ($LASTEXITCODE -ne 0) { throw "إصدار Python غير مدعوم." }

switch ($Action) {
  "doctor"  { py -m mirage_link doctor }
  "devices" { py -m mirage_link devices }
  "gui"     { py -m mirage_link.gui }
  "stream"  {
    $cliArgs = @("-m","mirage_link","stream","--fullscreen")
    if ($Serial) { $cliArgs += @("--serial",$Serial) }
    py @cliArgs
  }
  "help"    { py -m mirage_link --help }
}
exit $LASTEXITCODE
