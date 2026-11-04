"""Safe subprocess orchestration for ADB and scrcpy.

No shell is used. The streaming implementation is delegated to scrcpy's
Android MediaCodec capture/encode and desktop decode pipeline.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class MirageError(RuntimeError):
    """Expected, user-facing MIRAGE LINK error."""


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    details: str = ""


@dataclass(frozen=True)
class ToolPaths:
    adb: str
    scrcpy: str


def resolve_tool(name: str, explicit: str | None = None) -> str | None:
    candidates = [explicit, os.environ.get("MIRAGE_ADB" if name == "adb" else "MIRAGE_SCRCPY")]
    executable = "adb.exe" if name == "adb" and os.name == "nt" else name
    executable_scrcpy = "scrcpy.exe" if name == "scrcpy" and os.name == "nt" else name
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return shutil.which(executable) or shutil.which(executable_scrcpy)


class Engine:
    def __init__(self, adb_path: str | None = None, scrcpy_path: str | None = None,
                 runner=subprocess.run, popen=subprocess.Popen):
        self.adb = resolve_tool("adb", adb_path)
        self.scrcpy = resolve_tool("scrcpy", scrcpy_path)
        self._run = runner
        self._popen = popen

    def _require(self, value: str | None, name: str) -> str:
        if not value:
            raise MirageError(f"لم يتم العثور على {name}. ثبّته أو عيّن مساره في PATH أو متغير البيئة.")
        return value

    def command(self, args: Sequence[str], timeout: int = 20) -> str:
        adb = self._require(self.adb, "ADB")
        try:
            result = self._run([adb, *args], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MirageError(f"تعذر تنفيذ ADB: {exc}") from exc
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise MirageError(output.strip() or f"فشل ADB برمز {result.returncode}")
        return output.strip()

    def devices(self) -> list[Device]:
        output = self.command(["devices", "-l"])
        found: list[Device] = []
        for line in output.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] != "*":
                found.append(Device(parts[0], parts[1], " ".join(parts[2:])))
        return found

    def pair(self, endpoint: str, code: str) -> str:
        self._validate_endpoint(endpoint)
        if not code.isdigit() or not (4 <= len(code) <= 12):
            raise MirageError("رمز الاقتران يجب أن يكون أرقاماً كما يظهر على الهاتف.")
        return self.command(["pair", endpoint, code], timeout=45)

    def connect(self, endpoint: str) -> str:
        self._validate_endpoint(endpoint)
        return self.command(["connect", endpoint], timeout=30)

    def tcpip(self, port: int = 5555, serial: str | None = None) -> str:
        if not 1024 <= port <= 65535:
            raise MirageError("رقم المنفذ يجب أن يكون بين 1024 و65535.")
        args = (["-s", serial] if serial else []) + ["tcpip", str(port)]
        return self.command(args, timeout=30)

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if endpoint.count(":") != 1:
            raise MirageError("اكتب العنوان بالشكل IP:PORT كما يظهر في إعدادات الهاتف.")
        host, port = endpoint.rsplit(":", 1)
        if not host or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise MirageError("عنوان IP أو رقم المنفذ غير صالح.")

    def stream(self, serial: str | None = None, codec: str = "h264",
               max_fps: int = 60, bit_rate: str = "24M",
               fullscreen: bool = False, max_size: int | None = None,
               extra_args: Sequence[str] = ()) -> subprocess.Popen:
        """Start a source-resolution stream with a balanced high-quality bitrate.

        max_size is intentionally omitted by default: scrcpy then captures the
        device's native display size. Upscaling the desktop window cannot create
        additional source detail, so MIRAGE LINK does not mislabel it as 4K/8K.
        """
        scrcpy = self._require(self.scrcpy, "scrcpy")
        if codec not in {"auto", "h264", "h265"}:
            raise MirageError("الترميز المتاح: auto أو h264 أو h265.")
        if not 1 <= max_fps <= 240:
            raise MirageError("معدل الإطارات يجب أن يكون بين 1 و240.")
        if not bit_rate or any(c.isspace() for c in bit_rate) or bit_rate.startswith("-"):
            raise MirageError("قيمة معدل البت غير صالحة، مثال: 24M.")
        args: list[str] = []
        if serial:
            args += ["--serial", serial]
        if codec != "auto":
            args += ["--video-codec", codec]
        args += ["--max-fps", str(max_fps), "--video-bit-rate", bit_rate, "--stay-awake"]
        if fullscreen:
            args.append("--fullscreen")
        if max_size:
            if not 240 <= max_size <= 8192:
                raise MirageError("الحد الأقصى للحجم يجب أن يكون بين 240 و8192.")
            args += ["--max-size", str(max_size)]
        args.extend(extra_args)
        try:
            return self._popen([scrcpy, *args], shell=False)
        except OSError as exc:
            raise MirageError(f"تعذر تشغيل scrcpy: {exc}") from exc

    def doctor(self) -> dict[str, str]:
        report = {
            "ADB": self.adb or "غير موجود",
            "scrcpy": self.scrcpy or "غير موجود",
        }
        if self.adb:
            try:
                report["إصدار ADB"] = self.command(["version"]).splitlines()[0]
                report["الأجهزة"] = str(len(self.devices()))
            except MirageError as exc:
                report["فحص ADB"] = str(exc)
        if self.scrcpy:
            try:
                result = self._run([self.scrcpy, "--version"], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace",
                                   timeout=10, check=False)
                report["إصدار scrcpy"] = ((result.stdout or result.stderr).strip().splitlines() or ["غير معروف"])[0]
            except (OSError, subprocess.TimeoutExpired) as exc:
                report["فحص scrcpy"] = str(exc)
        return report
