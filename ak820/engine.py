"""Pure logic: raw reports in, gamepad state out. No USB, no OS calls."""
import time
from .profile import Profile, key_id


class Engine:
    def __init__(self, profile: Profile, sink):
        self.p, self.sink = profile, sink
        self.depth = {}                      # key id -> 0..1
        self._exit_since = None
        # resolve names once so a typo fails at startup, not mid-game
        self._axes = {n: (key_id(v["neg"]), key_id(v["pos"])) for n, v in profile.axes.items()}
        self._trig = {n: key_id(k) for n, k in profile.triggers.items()}
        self._btns = {key_id(k): b for k, b in profile.buttons.items()}
        self._exit = key_id(profile.exit_key)

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
        self.sink.update(axes, triggers, buttons)
        return True
