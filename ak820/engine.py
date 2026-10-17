"""Pure logic: raw reports in, gamepad state out. No USB, no OS calls."""
import time
from .profile import Profile, key_id


def _kid(name):
    return key_id(name) if name else -1      # unassigned -> a key that never has depth


class Engine:
    def __init__(self, profile: Profile, sink):
        self.sink = sink
        self.depth = {}                      # key id -> 0..1
        self.last = None                     # (axes, triggers, buttons) from the last tick
        self._exit_since = None
        self.set_profile(profile)

    def set_profile(self, profile: Profile):
        """Compile first, then swap, so a bad profile raises ValueError and changes nothing."""
        axes = {n: (_kid(v.get("neg")), _kid(v.get("pos"))) for n, v in profile.axes.items()}
        trig = {n: _kid(k) for n, k in profile.triggers.items()}
        btns = {key_id(k): b for k, b in profile.buttons.items()}
        ex = key_id(profile.exit_key)
        self._hot = [key_id(n) for n in profile.hotkey]
        self._axes, self._trig, self._btns, self._exit, self.p = axes, trig, btns, ex, profile

    def chord_held(self) -> bool:
        return bool(self._hot) and all(self.depth.get(k, 0.0) > self.p.button_threshold for k in self._hot)

    def release_all(self):
        """Neutral pad (used when leaving controller mode)."""
        self.depth.clear()
        self.last = ({n: 0.0 for n in self._axes}, {n: 0.0 for n in self._trig}, set())
        self.sink.update(*self.last)

    def feed(self, r):
        p = self.p
        drop = r.drop
        if drop < p.noise:
            x = 0.0
        else:
            x = min(1.0, (drop - p.noise) / (p.full - p.noise)) ** p.curve
        self.depth[r.key] = x

    def tick(self) -> bool:
        """Push current state to the sink. Returns False when the exit combo is held."""
        d = lambda k: self.depth.get(k, 0.0)
        p = self.p

        if d(self._exit) > 0.8:
            self._exit_since = self._exit_since or time.monotonic()
            if time.monotonic() - self._exit_since > 0.5:
                return False
        else:
            self._exit_since = None

        axes = {}
        for name, (neg, pos) in self._axes.items():
            v = d(pos) - d(neg)
            axes[name] = 0.0 if abs(v) < p.deadzone else max(-1.0, min(1.0, v))
        triggers = {n: d(k) for n, k in self._trig.items()}
        buttons = {b for k, b in self._btns.items() if d(k) > p.button_threshold}
        self.last = (axes, triggers, buttons)
        self.sink.update(axes, triggers, buttons)
        return True
