"""Where engine output goes. Swap sinks without touching the engine."""

_BUTTONS = {
    "A": "XUSB_GAMEPAD_A", "B": "XUSB_GAMEPAD_B", "X": "XUSB_GAMEPAD_X", "Y": "XUSB_GAMEPAD_Y",
    "LB": "XUSB_GAMEPAD_LEFT_SHOULDER", "RB": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "START": "XUSB_GAMEPAD_START", "BACK": "XUSB_GAMEPAD_BACK",
    "L3": "XUSB_GAMEPAD_LEFT_THUMB", "R3": "XUSB_GAMEPAD_RIGHT_THUMB",
    "DPAD_UP": "XUSB_GAMEPAD_DPAD_UP", "DPAD_DOWN": "XUSB_GAMEPAD_DPAD_DOWN",
    "DPAD_LEFT": "XUSB_GAMEPAD_DPAD_LEFT", "DPAD_RIGHT": "XUSB_GAMEPAD_DPAD_RIGHT",
}


def _snapshot(axes, triggers, buttons):
    return (tuple(round(v, 3) for _, v in sorted(axes.items())),
            tuple(round(v, 3) for _, v in sorted(triggers.items())),
            tuple(sorted(buttons)))


class VigemSink:
    """Virtual Xbox 360 pad (needs the ViGEmBus driver)."""

    def __init__(self):
        import vgamepad as vg
        self._vg = vg
        self._pad = vg.VX360Gamepad()
        self._last = None

    def update(self, axes, triggers, buttons):
        snap = _snapshot(axes, triggers, buttons)
        if snap == self._last:              # only talk to the driver when something changed
            return
        self._last = snap
        g = self._pad
        g.left_joystick_float(axes.get("left_x", 0.0), axes.get("left_y", 0.0))
        g.right_joystick_float(axes.get("right_x", 0.0), axes.get("right_y", 0.0))
        g.left_trigger_float(triggers.get("left", 0.0))
        g.right_trigger_float(triggers.get("right", 0.0))
        for name, attr in _BUTTONS.items():
            btn = getattr(self._vg.XUSB_BUTTON, attr)
            (g.press_button if name in buttons else g.release_button)(btn)
        g.update()


class PrintSink:
    """Debug sink: prints state changes. Used by `replay`."""

    def __init__(self):
        self._last = None

    def update(self, axes, triggers, buttons):
        snap = _snapshot(axes, triggers, buttons)
        if snap != self._last:
            self._last = snap
            print(f"axes={dict(axes)} triggers={dict(triggers)} buttons={sorted(buttons)}")
