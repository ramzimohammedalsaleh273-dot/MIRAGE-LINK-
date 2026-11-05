from mirage_link.wifi_receiver import WifiReceiver


def test_parse_valid_beacon():
    assert WifiReceiver.parse_beacon(b"MIRAGE-LINK/1|27183") == 27183


def test_parse_rejects_other_protocol():
    assert WifiReceiver.parse_beacon(b"OTHER/1|27183") is None


def test_parse_rejects_invalid_port():
    assert WifiReceiver.parse_beacon(b"MIRAGE-LINK/1|99999") is None
    assert WifiReceiver.parse_beacon(b"MIRAGE-LINK/1|zero") is None


def test_parse_rejects_malformed_payload():
    assert WifiReceiver.parse_beacon(b"") is None
    assert WifiReceiver.parse_beacon(b"MIRAGE-LINK/1") is None
