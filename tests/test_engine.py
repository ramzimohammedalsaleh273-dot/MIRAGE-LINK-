import subprocess
import pytest
from mirage_link.engine import Engine, MirageError, Device
from mirage_link.cli import build_parser


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def fake_tool(tmp_path, name):
    path = tmp_path / name
    path.write_text("test executable", encoding="utf-8")
    return str(path)


def test_devices_parses_states(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    def runner(args, **kwargs):
        return Result("List of devices attached\nABC123 device product:test model:Phone\nXYZ unauthorized usb:1\n")
    engine = Engine(adb_path=adb, scrcpy_path=fake_tool(tmp_path, "scrcpy"), runner=runner)
    assert engine.devices() == [
        Device("ABC123", "device", "product:test model:Phone"),
        Device("XYZ", "unauthorized", "usb:1"),
    ]


def test_mdns_services_discovers_wifi_pairing_and_connect_endpoints(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []
    def runner(args, **kwargs):
        seen.append(args)
        return Result(
            "List of discovered mdns services\\n"
            "adb-123 _adb-tls-pairing._tcp. 192.168.43.1:37123\\n"
            "adb-123 _adb-tls-connect._tcp. 192.168.43.1:42111\\n"
            "unrelated _other._tcp. 192.168.43.1:80\\n"
        )
    engine = Engine(adb_path=adb, runner=runner)
    assert engine.mdns_services() == {
        "pairing": ["192.168.43.1:37123"],
        "connect": ["192.168.43.1:42111"],
    }
    assert seen[0] == [adb, "mdns", "services"]


def test_mdns_services_returns_empty_lists_when_phone_not_advertising(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    engine = Engine(adb_path=adb, runner=lambda *a, **k: Result("List of discovered mdns services\\n"))
    assert engine.mdns_services() == {"pairing": [], "connect": []}


def test_pair_validates_endpoint_and_code(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    engine = Engine(adb_path=adb, runner=lambda *a, **k: Result("paired"))
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:abc", "123456")
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:37123", "abc")
    assert engine.pair("192.168.1.2:37123", "123456") == "paired"


def test_connect_uses_argument_array_not_shell(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []
    def runner(args, **kwargs):
        seen.append((args, kwargs))
        return Result("connected")
    engine = Engine(adb_path=adb, runner=runner)
    engine.connect("192.168.1.10:5555")
    assert seen[0][0] == [adb, "connect", "192.168.1.10:5555"]


def test_stream_defaults_to_native_capture_and_balanced_high_quality(tmp_path):
    scrcpy = fake_tool(tmp_path, "scrcpy")
    seen = []
    class Proc:
        pid = 42
    def popen(args, **kwargs):
        seen.append((args, kwargs))
        return Proc()
    engine = Engine(scrcpy_path=scrcpy, popen=popen)
    proc = engine.stream("ABC")
    assert proc.pid == 42
    assert seen[0][0] == [
        scrcpy, "--serial", "ABC", "--video-codec", "h264",
        "--max-fps", "60", "--video-bit-rate", "40M", "--stay-awake"
    ]
    assert "--max-size" not in seen[0][0]
    assert seen[0][1]["shell"] is False


def test_stream_allows_explicit_source_size_cap_when_requested(tmp_path):
    scrcpy = fake_tool(tmp_path, "scrcpy")
    seen = []
    engine = Engine(scrcpy_path=scrcpy, popen=lambda args, **kwargs: seen.append(args))
    engine.stream(max_size=1920)
    assert "--max-size" in seen[0]
    assert seen[0][seen[0].index("--max-size") + 1] == "1920"


def test_cli_stream_defaults_are_quality_preserving():
    args = build_parser().parse_args(["stream"])
    assert args.codec == "h264"
    assert args.max_fps == 60
    assert args.bit_rate == "40M"
    assert args.max_size is None


@pytest.mark.parametrize("kwargs", [
    {"codec": "bad"}, {"max_fps": 0}, {"max_fps": 241},
    {"bit_rate": "16 M"}, {"max_size": 100}
])
def test_stream_rejects_invalid_options(tmp_path, kwargs):
    engine = Engine(scrcpy_path=fake_tool(tmp_path, "scrcpy"), popen=lambda *a, **k: None)
    with pytest.raises(MirageError):
        engine.stream(**kwargs)


def test_missing_adb_is_actionable():
    engine = Engine(adb_path="/definitely/missing/adb")
    with pytest.raises(MirageError, match="ADB"):
        engine.devices()


def test_stream_latency_buffer_and_fps_diagnostics(tmp_path):
    scrcpy = fake_tool(tmp_path, "scrcpy")
    seen = []
    engine = Engine(scrcpy_path=scrcpy, popen=lambda args, **kwargs: seen.append(args))
    engine.stream("ABC", video_buffer_ms=25, print_fps=True)
    assert "--video-buffer" in seen[0]
    assert seen[0][seen[0].index("--video-buffer") + 1] == "25"
    assert "--print-fps" in seen[0]


def test_stream_rejects_invalid_video_buffer(tmp_path):
    engine = Engine(scrcpy_path=fake_tool(tmp_path, "scrcpy"), popen=lambda *a, **k: None)
    with pytest.raises(MirageError):
        engine.stream(video_buffer_ms=501)

def test_cli_exposes_buffer_and_fps_switches():
    args = build_parser().parse_args(["stream", "--video-buffer-ms", "25", "--print-fps"])
    assert args.video_buffer_ms == 25
    assert args.print_fps is True


@pytest.mark.parametrize("kwargs", [
    {"bit_rate": "abc"}, {"bit_rate": "40 M"}, {"max_size": 0}
])
def test_stream_rejects_malformed_bitrate_and_size(tmp_path, kwargs):
    engine = Engine(scrcpy_path=fake_tool(tmp_path, "scrcpy"), popen=lambda *a, **k: None)
    with pytest.raises(MirageError):
        engine.stream(**kwargs)

def test_stream_forwards_diagnostic_log_handles(tmp_path):
    scrcpy = fake_tool(tmp_path, "scrcpy")
    output = object()
    error = object()
    seen = {}
    def popen(args, **kwargs):
        seen.update(kwargs)
        return object()
    Engine(scrcpy_path=scrcpy, popen=popen).stream(
        "ABC", print_fps=True, stdout=output, stderr=error
    )
    assert seen["stdout"] is output
    assert seen["stderr"] is error
