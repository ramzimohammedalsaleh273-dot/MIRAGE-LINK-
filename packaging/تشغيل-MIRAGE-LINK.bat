@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%tools\scrcpy\adb.exe" set "MIRAGE_ADB=%ROOT%tools\scrcpy\adb.exe"
if exist "%ROOT%tools\scrcpy\scrcpy.exe" set "MIRAGE_SCRCPY=%ROOT%tools\scrcpy\scrcpy.exe"
start "MIRAGE LINK" "%ROOT%MIRAGE-LINK.exe"
endlocal
