"""Mode-switch hotkey. In keyboard mode the analog stream is off, so we poll the OS key state."""
import os
import time

VK = {"Esc": 0x1B, "Del": 0x2E, "`": 0xC0, "-": 0xBD, "=": 0xBB, "Backspace": 8, "Home": 0x24,
      "Tab": 9, "[": 0xDB, "]": 0xDD, "\\": 0xDC, "PgUp": 0x21, "Caps": 0x14, ";": 0xBA, "'": 0xDE,
      "Enter": 0x0D, "PgDn": 0x22, "LShift": 0xA0, ",": 0xBC, ".": 0xBE, "/": 0xBF, "RShift": 0xA1,
      "Up": 0x26, "End": 0x23, "LCtrl": 0xA2, "LWin": 0x5B, "LAlt": 0xA4, "Space": 0x20,
      "RAlt": 0xA5, "RCtrl": 0xA3, "Left": 0x25, "Down": 0x28, "Right": 0x27}   # no Fn: it has no VK
VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
VK.update({c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})


def down(names) -> bool:
    """True while every named key is physically held (Windows only)."""
    if os.name != "nt" or not names:
        return False
    import ctypes
    get = ctypes.windll.user32.GetAsyncKeyState
    return all(get(VK[n]) & 0x8000 for n in names)


def release(names):
    """Send synthetic key-ups so Windows doesn't think the chord is stuck when analog mode starts."""
    if os.name != "nt":
        return
    import ctypes
    for n in names:
        ctypes.windll.user32.keybd_event(VK[n], 0, 2, 0)    # KEYEVENTF_KEYUP


class Edge:
    """Fires once per chord press: needs a release first, then a cooldown."""

    def __init__(self, cooldown=0.8):
        self.cooldown, self.armed, self._until = cooldown, False, 0.0

    def reset(self):
        self.armed = False          # the chord is probably still held; wait for release

    def update(self, pressed: bool) -> bool:
        if not pressed:
            self.armed = True
            return False
        if self.armed and time.monotonic() >= self._until:
            self.armed, self._until = False, time.monotonic() + self.cooldown
            return True
        return False
