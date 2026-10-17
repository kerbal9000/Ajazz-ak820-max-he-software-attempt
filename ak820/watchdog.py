"""Safety net for analog mode.

While the keyboard is in analog mode it can't type. If the main program is killed,
crashes, or hangs, nothing would send the exit command (aa 65) and you'd have to
replug the keyboard. This module runs a *separate, detached* process that does it:

  main program --heartbeat file--> watchdog process
    - parent process gone, heartbeat file still there -> send aa 65
    - heartbeat file stale (program hung)             -> send aa 65
    - heartbeat file deleted by a clean exit          -> do nothing

The watchdog is detached from the console, so closing the console window (which
kills the main program) does not kill the watchdog.
Log: <temp dir>/ak820-watchdog.log
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

LOG = os.path.join(tempfile.gettempdir(), "ak820-watchdog.log")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass


# ---------------------------------------------------------------- sending the exit

def send_stop(dry_run=False) -> bool:
    """Open the command interface on its own handle and send aa 65."""
    if dry_run:
        log("DRY RUN: would send aa 65")
        return True
    import hid
    from .device import VID, PID, PAGE_CMD, STOP
    for attempt in range(1, 6):
        try:
            for d in hid.enumerate(VID, PID):
                if d["usage_page"] == PAGE_CMD:
                    h = hid.device()
                    h.open_path(d["path"])
                    try:
                        h.write(b"\x00" + STOP)
                    finally:
                        h.close()
                    log("sent aa 65")
                    return True
            log("keyboard not found (unplugged?), nothing to reset")
            return False
        except OSError as e:
            log(f"attempt {attempt} failed: {e}")
            time.sleep(0.5)
    log("gave up; replug the keyboard")
    return False


# ---------------------------------------------------------------- process liveness

def _open_process(pid):
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        k.OpenProcess.restype = ctypes.c_void_p
        return k.OpenProcess(0x00100000, False, pid) or None   # SYNCHRONIZE
    return pid


def _alive(handle) -> bool:
    if handle is None:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return k.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0x102   # WAIT_TIMEOUT
    try:
        os.kill(handle, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ---------------------------------------------------------------- the watchdog process

def monitor(pid, hb, timeout, stop_fn, poll=0.25) -> int:
    handle = _open_process(pid)       # held for the whole run, so the pid can't be reused
    log(f"watching pid {pid}, timeout {timeout}s")
    reason = None
    while reason is None:
        time.sleep(poll)
        if not os.path.exists(hb):
            log("disarmed cleanly")
            return 0
        if not _alive(handle):
            reason = "main program died"
        else:
            try:
                age = time.time() - os.path.getmtime(hb)
            except OSError:
                continue
            if age > timeout:
                reason = f"heartbeat stale for {age:.1f}s (main program hung)"
    if not os.path.exists(hb):        # clean exit raced with our checks
        log("disarmed cleanly")
        return 0
    log(f"TRIPPED: {reason}")
    try:
        with open(hb) as f:
            active = f.read().strip() != "0"
    except OSError:
        active = True
    if active:
        stop_fn()
    else:
        log("keyboard was in normal mode; nothing to reset")
    try:
        os.remove(hb)                 # tells a hung-but-alive program that it was reset
    except OSError:
        pass
    return 1


# ---------------------------------------------------------------- used by the main program

class Watchdog:
    def __init__(self, timeout=3.0, enabled=True, dry_run=False):
        self.timeout, self.enabled, self.dry_run = timeout, enabled, dry_run
        self.path = os.path.join(tempfile.gettempdir(), f"ak820-wd-{os.getpid()}.hb")
        self._last = 0.0
        self._armed = False

    def arm(self):
        """Call BEFORE the keyboard enters analog mode."""
        if not self.enabled:
            return
        with open(self.path, "w") as f:
            f.write("1")           # 1 = keyboard is in analog mode
        cmd = [sys.executable, "-m", "ak820.watchdog", "--pid", str(os.getpid()),
               "--hb", self.path, "--timeout", str(self.timeout)]
        if self.dry_run:
            cmd.append("--dry-run")
        if os.name == "nt":
            kw = dict(creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            kw = dict(start_new_session=True)
        subprocess.Popen(cmd, cwd=_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, **kw)
        self._last = time.monotonic()
        self._armed = True

    def beat(self) -> bool:
        """Call from the main loop. False means the watchdog already reset the keyboard."""
        if not self._armed:
            return True
        now = time.monotonic()
        if now - self._last < 0.25:
            return True
        self._last = now
        try:
            os.utime(self.path)
            return True
        except FileNotFoundError:
            self._armed = False
            return False

    def set_active(self, active: bool):
        """Tell the watchdog whether the keyboard is in analog mode (nothing to reset if not)."""
        if self._armed:
            try:
                with open(self.path, "r+") as f:
                    f.write("1" if active else "0")
                    f.truncate()
            except OSError:
                pass

    def disarm(self):
        """Call AFTER the keyboard has left analog mode."""
        if self._armed:
            self._armed = False
            try:
                os.remove(self.path)
            except OSError:
                pass

    def __enter__(self):
        self.arm()
        return self

    def __exit__(self, *exc):
        self.disarm()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--hb", required=True)
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.exit(monitor(a.pid, a.hb, a.timeout, lambda: send_stop(a.dry_run)))
