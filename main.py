"""AK820 MAX HE analog gamepad.

  python main.py run    [--profile profiles/default.json]
  python main.py record out.jsonl [--seconds 10]     # capture raw reports
  python main.py replay out.jsonl [--profile ...]    # test the engine, no keyboard needed

The keyboard does not type while `run`/`record` are active. Hold Esc to quit `run`.
"""
import argparse
import json
import time

from ak820.device import Report
from ak820.engine import Engine
from ak820.profile import Profile


def cmd_run(a):
    from ak820.device import Board
    from ak820.sinks import VigemSink
    eng = Engine(Profile.load(a.profile), VigemSink())
    with Board() as board:
        print("Running. Hold Esc fully for 0.5 s to quit.")
        for r in board.reports():
            if r:
                eng.feed(r)
            if not eng.tick():
                break


def cmd_record(a):
    from ak820.device import Board
    last, end = {}, time.time() + a.seconds
    with Board() as board, open(a.out, "w") as f:
        print(f"Recording {a.seconds}s to {a.out} (keyboard won't type)...")
        for r in board.reports():
            if time.time() > end:
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--profile", default="profiles/default.json"); r.set_defaults(fn=cmd_run)
    r = sub.add_parser("record"); r.add_argument("out"); r.add_argument("--seconds", type=float, default=10); r.set_defaults(fn=cmd_record)
    r = sub.add_parser("replay"); r.add_argument("file"); r.add_argument("--profile", default="profiles/default.json"); r.set_defaults(fn=cmd_replay)
    a = ap.parse_args()
    a.fn(a)
