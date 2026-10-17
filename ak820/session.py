"""Owns the mode (controller / keyboard) and runs the main loop."""
import time
from . import hotkey


class Session:
    def __init__(self, board, engine, watchdog, stop):
        self.board, self.eng, self.wd, self.stop = board, engine, watchdog, stop
        self.mode, self._want, self._edge = "controller", None, hotkey.Edge()

    def request(self, mode):               # called from the UI thread
        self._want = mode

    def _set(self, mode):
        if mode == self.mode:
            return
        if mode == "keyboard":
            self.eng.release_all()          # neutral pad first
            self.board.stop()               # aa 65: keyboard types again
            self.wd.set_active(False)
        else:
            self.wd.set_active(True)        # watchdog must know before analog mode starts
            self.board.start()              # aa 64
            self.eng.depth.clear()
            hotkey.release(self.eng.p.hotkey)
        self.mode = mode
        self._edge.reset()
        print(f"[{mode} mode]")

    def run(self):
        reports = self.board.reports()
        while not self.stop.is_set():
            if self._want:
                want, self._want = self._want, None
                self._set(want)
            if self.mode == "controller":
                r = next(reports)
                if r:
                    self.eng.feed(r)
                if not self.wd.beat():
                    return print("Watchdog reset the keyboard (the loop stalled). Exiting.")
                if not self.eng.tick():
                    return
                if self._edge.update(self.eng.chord_held()):
                    self._set("keyboard")
            else:
                time.sleep(0.02)
                if not self.wd.beat():
                    return print("Watchdog reset the keyboard (the loop stalled). Exiting.")
                if self._edge.update(hotkey.down(self.eng.p.hotkey)):
                    self._set("controller")
