"""Talks to the keyboard. Only this module knows about USB/HID."""
import atexit
import time
from dataclasses import dataclass

VID, PID = 0x0C45, 0x80B1
PAGE_CMD = 0xFF68      # commands out, acks + analog reports in. (0xFF67 is NOT used.)


def _pad(*b):
    return bytes(b).ljust(64, b"\x00")


START = [
    _pad(0xAA, 0x10, 0x30, 0, 0, 0, 0x01, 0),   # handshake
    _pad(0xAA, 0x11, 0x38, 0, 0, 0, 0x01, 0),   # get version
    _pad(0xAA, 0x64, 0x00),                      # enter analog mode (typing stops)
]
STOP = _pad(0xAA, 0x65, 0x00)                    # exit analog mode (typing resumes)


@dataclass(frozen=True)
class Report:
    key: int
    s1: int   # per-key rest baseline
    s2: int   # status / stored value (not live depth)
    s3: int   # live reading

    @property
    def drop(self) -> int:
        """Depth in raw counts: 0 at rest, ~1100 at bottom-out."""
        return self.s1 - self.s3


def parse(data):
    if len(data) >= 10 and data[0] == 0x55 and data[1] == 0xFB:
        w = lambda i: data[i] | (data[i + 1] << 8)
        return Report(data[2], w(4), w(6), w(8))
    return None


class Board:
    def __init__(self):
        import hid   # imported here so replay/tests work without hidapi installed
        self._h = None
        for d in hid.enumerate(VID, PID):
            if d["usage_page"] == PAGE_CMD:
                self._h = hid.device()
                self._h.open_path(d["path"])
                break
        if self._h is None:
            raise RuntimeError("AK820 MAX HE (usage page 0xff68) not found")
        self._active = False
        atexit.register(self.stop)

    def _send(self, pkt):
        self._h.write(b"\x00" + pkt)
        time.sleep(0.05)
        try:
            while self._h.read(65, 10):
                pass
        except OSError:
            pass

    def start(self):
        for p in START:
            self._send(p)
        self._active = True

    def stop(self):
        if self._active:
            self._active = False
            try:
                self._send(STOP)
            except Exception:
                pass

    def reports(self):
        """Yield a Report, or None when nothing arrived (so callers can keep ticking)."""
        while True:
            yield parse(self._h.read(65, 5))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
