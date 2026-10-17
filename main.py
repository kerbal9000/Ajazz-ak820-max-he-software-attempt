"""AK820 MAX HE analog gamepad.

  python main.py run    [--profile profiles/default.json] [--no-watchdog]
  python main.py record out.jsonl [--seconds 10]     # capture raw reports
  python main.py replay out.jsonl [--profile ...]    # test the engine, no keyboard needed
  python main.py ui     [--profile ...] [--port 8820]   # live UI in your browser
  python main.py rescue                              # send the exit command to a stuck keyboard

The keyboard does not type while `run`/`record` are active. Hold Esc to quit `run`.
A detached watchdog process resets the keyboard if the program is killed or hangs.
"""
import argparse
import json
import threading
import time

from ak820.device import Report
from ak820.engine import Engine
from ak820.profile import Profile
from ak820.watchdog import Watchdog, LOG, send_stop


def cmd_run(a):
    from ak820.device import Board
    from ak820.session import Session
    from ak820.sinks import VigemSink
    eng = Engine(Profile.load(a.profile), VigemSink())
    # order matters: arm the watchdog first, leave analog mode before disarming
    with Watchdog(enabled=not a.no_watchdog) as wd, Board() as board:
        print("Running. Hold Esc to quit; hold your mode hotkey to switch to keyboard mode.")
        Session(board, eng, wd, threading.Event()).run()


def cmd_ui(a):
    import webbrowser
    from ak820.device import Board
    from ak820.session import Session
    from ak820.sinks import VigemSink
    from ak820.ui import App, serve
    eng, stop = Engine(Profile.load(a.profile), VigemSink()), threading.Event()
    with Watchdog() as wd, Board() as board:
        session = Session(board, eng, wd, stop)
        srv = serve(App(eng, a.profile, stop, session), a.port)
        url = f"http://127.0.0.1:{a.port}/"
        print(f"UI at {url}  (Esc held or the Stop button quits; hotkey/button switches mode)")
        if not a.no_browser:
            webbrowser.open(url)
        try:
            session.run()
        finally:
            srv.shutdown()


def cmd_record(a):
    from ak820.device import Board
    last, end = {}, time.time() + a.seconds
    with Watchdog() as wd, Board() as board, open(a.out, "w") as f:
        print(f"Recording {a.seconds}s to {a.out} (keyboard won't type)...")
        for r in board.reports():
            if time.time() > end or not wd.beat():
                break
            if r and last.get(r.key) != (r.s1, r.s2, r.s3):
                last[r.key] = (r.s1, r.s2, r.s3)
                f.write(json.dumps({"t": round(time.time(), 4), "k": r.key,
                                    "s": [r.s1, r.s2, r.s3]}) + "\n")


def cmd_replay(a):
    from ak820.sinks import PrintSink
    eng = Engine(Profile.load(a.profile), PrintSink())
    with open(a.file) as f:
        for line in f:
            d = json.loads(line)
            eng.feed(Report(d["k"], *d["s"]))
            eng.tick()


def cmd_rescue(a):
    ok = send_stop()
    print("Sent the exit command." if ok else f"Could not reach the keyboard. See {LOG}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--profile", default="profiles/default.json")
    r.add_argument("--no-watchdog", action="store_true"); r.set_defaults(fn=cmd_run)
    r = sub.add_parser("ui"); r.add_argument("--profile", default="profiles/default.json")
    r.add_argument("--port", type=int, default=8820); r.add_argument("--no-browser", action="store_true"); r.set_defaults(fn=cmd_ui)
    r = sub.add_parser("record"); r.add_argument("out"); r.add_argument("--seconds", type=float, default=10); r.set_defaults(fn=cmd_record)
    r = sub.add_parser("replay"); r.add_argument("file"); r.add_argument("--profile", default="profiles/default.json"); r.set_defaults(fn=cmd_replay)
    r = sub.add_parser("rescue"); r.set_defaults(fn=cmd_rescue)
    a = ap.parse_args()
    a.fn(a)
