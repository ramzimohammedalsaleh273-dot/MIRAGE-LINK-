import subprocess
import pytest
from mirage_link.engine import Engine, MirageError, Device


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def test_devices_parses_states():
    calls = []
    def runner(args, **kwargs):
        calls.append(args)
        return Result("List of devices attached\nABC123 device product:test model:Phone\nXYZ unauthorized usb:1\n")
    engine = Engine(adb_path="/fake/adb", scrcpy_path="/fake/scrcpy", runner=runner)
    assert engine.devices() == [
        Device("ABC123", "device", "product:test model:Phone"),
        Device("XYZ", "unauthorized", "usb:1"),
    ]


def test_pair_validates_endpoint_and_code():
    engine = Engine(adb_path="/fake/adb", runner=lambda *a, **k: Result("paired"))
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:abc", "123456")
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:37123", "abc")
    assert engine.pair("192.168.1.2:37123", "123456") == "paired"


def test_connect_uses_argument_array_not_shell():
    seen = []
    def runner(args, **kwargs):
        seen.append((args, kwargs))
        return Result("connected")
    engine = Engine(adb_path="/fake/adb", runner=runner)
    engine.connect("192.168.1.10:5555")
    assert seen[0][0] == ["/fake/adb", "connect", "192.168.1.10:5555"]


def test_stream_builds_expected_scrcpy_args():
    seen = []
    class Proc:
        pid = 42
    def popen(args, **kwargs):
        seen.append((args, kwargs))
        return Proc()
    engine = Engine(scrcpy_path="/fake/scrcpy", popen=popen)
    proc = engine.stream("ABC", "h264", 60, "16M", True, 1920)
    assert proc.pid == 42
    assert seen[0][0] == [
        "/fake/scrcpy", "--serial", "ABC", "--video-codec", "h264",
        "--max-fps", "60", "--video-bit-rate", "16M", "--stay-awake",
        "--fullscreen", "--max-size", "1920"
    ]
    assert seen[0][1]["shell"] is False


@pytest.mark.parametrize("kwargs", [
    {"codec": "bad"}, {"max_fps": 0}, {"max_fps": 241},
    {"bit_rate": "16 M"}, {"max_size": 100}
])
def test_stream_rejects_invalid_options(kwargs):
    engine = Engine(scrcpy_path="/fake/scrcpy", popen=lambda *a, **k: None)
    with pytest.raises(MirageError):
        engine.stream(**kwargs)


def test_missing_adb_is_actionable():
    engine = Engine(adb_path="/definitely/missing/adb")
    with pytest.raises(MirageError, match="ADB"):
        engine.devices()
