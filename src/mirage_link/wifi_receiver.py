"""Wireless H.264 receiver for the Android MediaProjection companion."""
from __future__ import annotations

import socket
import threading
import time
from typing import Callable

DISCOVERY_PORT = 27184
MAGIC = "MIRAGE-LINK/1"


class WifiReceiver:
    """Find the companion by UDP beacon, then decode its Annex-B H.264 TCP stream."""

    def __init__(self, on_frame: Callable, on_status: Callable):
        self.on_frame = on_frame
        self.on_status = on_status
        self._stop = threading.Event()
        self._discovery_socket = None
        self._video_socket = None
        self._thread = None
        self._lock = threading.Lock()
        self.address = None

    @staticmethod
    def parse_beacon(data: bytes):
        try:
            magic, port_text = data.decode("ascii").strip().split("|", 1)
            port = int(port_text)
            if magic != MAGIC or not 1 <= port <= 65535:
                return None
            return port
        except (UnicodeDecodeError, ValueError):
            return None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._discover, name="mirage-wifi", daemon=True)
        self._thread.start()

    def _discover(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._discovery_socket = sock
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(1.0)
            self.on_status("نبحث عن تطبيق MIRAGE LINK على شبكة الهاتف...")
            while not self._stop.is_set():
                try:
                    data, peer = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                port = self.parse_beacon(data)
                if port is None:
                    continue
                self.address = (peer[0], port)
                self.on_status(f"تم اكتشاف الهاتف {peer[0]} — جارٍ الاتصال...")
                self._connect_and_decode(peer[0], port)
                return
        except OSError as exc:
            if not self._stop.is_set():
                self.on_status(f"تعذر اكتشاف الهاتف: {exc}")
        finally:
            if self._discovery_socket:
                try:
                    self._discovery_socket.close()
                except OSError:
                    pass
                self._discovery_socket = None

    def _connect_and_decode(self, host, port):
        try:
            import av
            sock = socket.create_connection((host, port), timeout=12)
            self._video_socket = sock
            sock.settimeout(3.0)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            decoder = av.CodecContext.create("h264", "r")
            self.on_status(f"متصل بالهاتف {host} — استقبال الصورة...")
            while not self._stop.is_set():
                try:
                    chunk = sock.recv(256 * 1024)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                for packet in decoder.parse(chunk):
                    for frame in decoder.decode(packet):
                        self.on_frame(frame.to_image())
            for packet in decoder.parse(b""):
                for frame in decoder.decode(packet):
                    self.on_frame(frame.to_image())
            for frame in decoder.decode(None):
                self.on_frame(frame.to_image())
            if not self._stop.is_set():
                self.on_status("انقطع اتصال الهاتف.")
        except Exception as exc:
            if not self._stop.is_set():
                self.on_status(f"تعذر استقبال الفيديو: {exc}")
        finally:
            if self._video_socket:
                try:
                    self._video_socket.close()
                except OSError:
                    pass
                self._video_socket = None

    def stop(self):
        self._stop.set()
        for sock in (self._discovery_socket, self._video_socket):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass
