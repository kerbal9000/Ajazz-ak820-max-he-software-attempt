"""Local web UI (127.0.0.1 only): live key depth, gamepad tester, mapping + settings editor."""
import json
import os
import threading
from dataclasses import asdict, fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .profile import Profile, KEYS
from .sinks import _BUTTONS

PAGE = os.path.join(os.path.dirname(__file__), "ui.html")
RANGES = {"noise": (0, 300), "full": (300, 2000), "deadzone": (0, 0.5),
          "curve": (0.2, 4), "button_threshold": (0.05, 0.95)}
AXES = {"left_x", "left_y", "right_x", "right_y"}


class App:
    def __init__(self, engine, profile_path, stop):
        self.engine, self.path, self.stop = engine, profile_path, stop

    def apply(self, data):
        known = {f.name for f in fields(Profile)}
        p = Profile(**{k: v for k, v in data.items() if k in known})
        for f, (lo, hi) in RANGES.items():
            if not lo <= getattr(p, f) <= hi:
                raise ValueError(f"{f} must be between {lo} and {hi}")
        if p.full < p.noise + 50:
            raise ValueError("full must be at least noise + 50")
        if not set(p.axes) <= AXES or not set(p.triggers) <= {"left", "right"}:
            raise ValueError("unknown axis or trigger name")
        if any(b not in _BUTTONS for b in p.buttons.values()):
            raise ValueError("unknown gamepad button")
        self.engine.set_profile(p)          # raises ValueError on unknown key names
        p.save(self.path)


def _handler(app, port):
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}     # blocks DNS-rebinding

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") not in hosts:
                return self._send(403, {"error": "bad host"})
            e = app.engine
            if self.path == "/":
                with open(PAGE, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if self.path == "/api/config":
                return self._send(200, {"profile": asdict(e.p), "keys": KEYS})
            if self.path == "/api/state":
                axes, trig, btn = e.last or ({}, {}, set())
                depth = {str(k): round(v, 3) for k, v in list(e.depth.items()) if v > 0}
                return self._send(200, {"depth": depth, "axes": axes, "triggers": trig,
                                        "buttons": sorted(btn)})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if (self.headers.get("Host") not in hosts
                    or "application/json" not in self.headers.get("Content-Type", "")):
                return self._send(403, {"error": "forbidden"})
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                if self.path == "/api/profile":
                    app.apply(data)
                    return self._send(200, {"ok": True})
                if self.path == "/api/quit":
                    app.stop.set()
                    return self._send(200, {"ok": True})
                self._send(404, {"error": "not found"})
            except (ValueError, TypeError, AttributeError) as ex:
                self._send(400, {"error": str(ex)})

    return H


def serve(app, port=8820):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _handler(app, port))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
