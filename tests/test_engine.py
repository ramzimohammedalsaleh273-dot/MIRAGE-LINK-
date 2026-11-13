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
            "List of discovered mdns services\n"
            "adb-123 _adb-tls-pairing._tcp. 192.168.43.1:37123\n"
            "adb-123 _adb-tls-connect._tcp. 192.168.43.1:42111\n"
            "unrelated _other._tcp. 192.168.43.1:80\n"
        )
    engine = Engine(adb_path=adb, runner=runner)
    assert engine.mdns_services() == {
        "pairing": ["192.168.43.1:37123"],
        "connect": ["192.168.43.1:42111"],
    }
    assert seen[0] == [adb, "mdns", "services"]


def test_mdns_services_returns_empty_lists_when_phone_not_advertising(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    engine = Engine(adb_path=adb, runner=lambda *a, **k: Result("List of discovered mdns services\n"))
    assert engine.mdns_services() == {"pairing": [], "connect": []}


def test_pair_validates_endpoint_and_code(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    engine = Engine(adb_path=adb, runner=lambda *a, **k: Result("paired"))
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:abc", "123456")
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:37123", "abc")
    with pytest.raises(MirageError):
        engine.pair("192.168.1.2:37123", "²²²²")
    assert engine.pair("192.168.1.2:37123", "123456") == "paired"


@pytest.mark.parametrize(("code", "expected"), [
    ("١٢٣٤٥٦", "123456"),
    ("۱۲۳۴۵۶", "123456"),
    (" ١٢٣٤٥٦ ", "123456"),
])
def test_pair_normalizes_arabic_and_persian_digits(tmp_path, code, expected):
    adb = fake_tool(tmp_path, "adb")
    seen = []

    def runner(args, **kwargs):
        seen.append(args)
        return Result("Successfully paired")

    engine = Engine(adb_path=adb, runner=runner)
    assert engine.pair("192.168.1.2:37123", code) == "Successfully paired"
    assert seen == [[adb, "pair", "192.168.1.2:37123", expected]]


def test_connect_uses_argument_array_not_shell(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []
    def runner(args, **kwargs):
        seen.append((args, kwargs))
        return Result("connected")
    engine = Engine(adb_path=adb, runner=runner)
    engine.connect("192.168.1.10:5555")
    assert seen[0][0] == [adb, "connect", "192.168.1.10:5555"]


@pytest.mark.parametrize("endpoint", [
    "999.1.1.1:5555", "192.168.1.1:0", "192.168.1.1:65536",
    "phone.local:5555", "192.168.1.1", "192.168.1.1:abc",
])
def test_endpoint_validation_rejects_invalid_ipv4_or_port(endpoint):
    with pytest.raises(MirageError):
        Engine._validate_endpoint(endpoint)


def test_wifi_discover_connects_dynamic_endpoint_and_filters_usb(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []

    def runner(args, **kwargs):
        command = args[1:]
        seen.append(command)
        if command == ["mdns", "services"]:
            return Result(
                "List of discovered mdns services\n"
                "adb-phone _adb-tls-connect._tcp. 192.168.43.1:43821\n"
            )
        if command == ["connect", "192.168.43.1:43821"]:
            return Result("connected")
        if command == ["devices", "-l"]:
            return Result(
                "List of devices attached\n"
                "USB123 device product:test model:Phone\n"
                "192.168.43.1:43821 device product:test model:Phone\n"
            )
        return Result()

    engine = Engine(adb_path=adb, runner=runner)
    services, devices, errors = engine.wifi_discover()
    assert services["connect"] == ["192.168.43.1:43821"]
    assert [device.serial for device in devices] == ["192.168.43.1:43821"]
    assert errors == []
    assert ["connect", "192.168.43.1:43821"] in seen


def test_wifi_discover_does_not_connect_to_multiple_paired_phones_automatically(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []

    def runner(args, **kwargs):
        command = args[1:]
        seen.append(command)
        if command == ["mdns", "services"]:
            return Result(
                "List of discovered mdns services\n"
                "phone-a _adb-tls-connect._tcp. 192.168.43.1:42736\n"
                "phone-b _adb-tls-connect._tcp. 192.168.43.2:42737\n"
            )
        if command == ["devices", "-l"]:
            return Result("List of devices attached\n")
        return Result()

    services, devices, errors = Engine(adb_path=adb, runner=runner).wifi_discover()

    assert services["connect"] == ["192.168.43.1:42736", "192.168.43.2:42737"]
    assert devices == []
    assert len(errors) == 1
    assert "أكثر من خدمة اتصال" in errors[0]
    assert not any(command and command[0] == "connect" for command in seen)


def test_wifi_discover_keeps_existing_wireless_device_when_mdns_fails(tmp_path):
    adb = fake_tool(tmp_path, "adb")

    def runner(args, **kwargs):
        command = args[1:]
        if command == ["mdns", "services"]:
            return Result(stderr="mDNS discovery is disabled", returncode=1)
        if command == ["devices", "-l"]:
            return Result(
                "List of devices attached\n"
                "adb-CP36T1043200729-QXjCrW._adb-tls-connect._tcp device model:Phone\n"
                "USB123 device usb:1 model:Phone\n"
            )
        return Result()

    services, devices, errors = Engine(adb_path=adb, runner=runner).wifi_discover()

    assert services == {"pairing": [], "connect": []}
    assert [device.serial for device in devices] == [
        "adb-CP36T1043200729-QXjCrW._adb-tls-connect._tcp"
    ]
    assert errors == ["mDNS discovery is disabled"]


def test_wifi_pair_and_connect_uses_advertised_dynamic_ports(tmp_path, monkeypatch):
    adb = fake_tool(tmp_path, "adb")
    seen = []
    mdns_calls = 0

    def runner(args, **kwargs):
        nonlocal mdns_calls
        command = args[1:]
        seen.append(command)
        if command == ["mdns", "services"]:
            mdns_calls += 1
            if mdns_calls == 1:
                return Result(
                    "List of discovered mdns services\n"
                    "adb-phone _adb-tls-pairing._tcp. 192.168.43.1:36127\n"
                )
            return Result(
                "List of discovered mdns services\n"
                "adb-phone _adb-tls-connect._tcp. 192.168.43.1:42736\n"
            )
        if command[0] == "pair":
            return Result("Successfully paired")
        if command[0] == "connect":
            return Result("connected")
        if command == ["devices", "-l"]:
            if mdns_calls < 2:
                return Result("List of devices attached\n")
            return Result(
                "List of devices attached\n"
                "192.168.43.1:42736 device product:test model:Phone\n"
            )
        return Result()

    monkeypatch.setattr("mirage_link.engine.time.sleep", lambda _seconds: None)
    engine = Engine(adb_path=adb, runner=runner)
    devices = engine.wifi_pair_and_connect("123456", retries=2, retry_interval=0)
    assert [device.serial for device in devices] == ["192.168.43.1:42736"]
    assert ["pair", "192.168.43.1:36127", "123456"] in seen
    assert ["connect", "192.168.43.1:42736"] in seen


def test_wifi_pair_refuses_ambiguous_pairing_services_without_sending_code(tmp_path):
    adb = fake_tool(tmp_path, "adb")
    seen = []

    def runner(args, **kwargs):
        command = args[1:]
        seen.append(command)
        if command == ["mdns", "services"]:
            return Result(
                "List of discovered mdns services\n"
                "adb-phone-a _adb-tls-pairing._tcp. 192.168.43.1:36127\n"
                "adb-phone-b _adb-tls-pairing._tcp. 192.168.43.2:36227\n"
            )
        if command == ["devices", "-l"]:
            return Result("List of devices attached\n")
        return Result()

    engine = Engine(adb_path=adb, runner=runner)
    with pytest.raises(MirageError, match="أكثر من خدمة اقتران"):
        engine.wifi_pair_and_connect("123456", retries=1, retry_interval=0)

    assert not any(command and command[0] == "pair" for command in seen)


def test_wifi_pair_requires_android_pairing_service(tmp_path):
    adb = fake_tool(tmp_path, "adb")

    def runner(args, **kwargs):
        if args[1:] == ["mdns", "services"]:
            return Result("List of discovered mdns services\n")
        if args[1:] == ["devices", "-l"]:
            return Result("List of devices attached\n")
        return Result()

    engine = Engine(adb_path=adb, runner=runner)
    with pytest.raises(MirageError, match="لم تظهر خدمة الاقتران"):
        engine.wifi_pair_and_connect("123456", retries=1, retry_interval=0)


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

@pytest.mark.parametrize(("serial", "expected"), [
    ("192.168.43.1:42736", True),
    ("adb-CP36T1043200729-QXjCrW._adb-tls-connect._tcp", True),
    ("CP36T1043200729", False),
    ("USB123", False),
])
def test_wireless_device_recognizes_tcp_and_mdns_serials(serial, expected):
    assert Engine.is_wireless_device(Device(serial, "device")) is expected


def test_wifi_discover_keeps_mDNS_serials_and_excludes_usb(tmp_path):
    adb = fake_tool(tmp_path, "adb")

    def runner(args, **kwargs):
        command = args[1:]
        if command == ["mdns", "services"]:
            return Result(
                "List of discovered mdns services\n"
                "adb-phone _adb-tls-connect._tcp. 192.168.43.1:42736\n"
            )
        if command == ["connect", "192.168.43.1:42736"]:
            return Result("connected to 192.168.43.1:42736")
        if command == ["devices", "-l"]:
            return Result(
                "List of devices attached\n"
                "adb-CP36T1043200729-QXjCrW._adb-tls-connect._tcp device product:test model:Phone\n"
                "CP36T1043200729 device usb:1 product:test model:Phone\n"
            )
        return Result()

    services, devices, errors = Engine(adb_path=adb, runner=runner).wifi_discover()
    assert services["connect"] == ["192.168.43.1:42736"]
    assert [device.serial for device in devices] == [
        "adb-CP36T1043200729-QXjCrW._adb-tls-connect._tcp"
    ]
    assert errors == []

def test_wifi_pair_and_connect_reports_last_adb_connection_error(tmp_path, monkeypatch):
    adb = fake_tool(tmp_path, "adb")
    mdns_calls = 0

    def runner(args, **kwargs):
        nonlocal mdns_calls
        command = args[1:]
        if command == ["mdns", "services"]:
            mdns_calls += 1
            if mdns_calls == 1:
                return Result(
                    "List of discovered mdns services\n"
                    "adb-phone _adb-tls-pairing._tcp. 192.168.43.1:36127\n"
                )
            return Result(
                "List of discovered mdns services\n"
                "adb-phone _adb-tls-connect._tcp. 192.168.43.1:42736\n"
            )
        if command[0] == "pair":
            return Result("Successfully paired")
        if command[0] == "connect":
            return Result(stderr="failed to connect: Connection refused", returncode=1)
        if command == ["devices", "-l"]:
            return Result("List of devices attached\n")
        return Result()

    monkeypatch.setattr("mirage_link.engine.time.sleep", lambda _seconds: None)
    engine = Engine(adb_path=adb, runner=runner)
    with pytest.raises(MirageError, match="Connection refused"):
        engine.wifi_pair_and_connect("123456", retries=2, retry_interval=0)
