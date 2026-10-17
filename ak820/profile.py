"""Profile = everything the user can configure. Stored as JSON."""
import json
from dataclasses import dataclass, field, fields, asdict


def _keys():
    k = {"Esc": 0, "Del": 106, "`": 16, "-": 27, "=": 28, "Backspace": 92, "Home": 104,
         "Tab": 32, "[": 43, "]": 44, "\\": 60, "PgUp": 105, "Caps": 48, ";": 58, "'": 59,
         "Enter": 76, "PgDn": 108, "LShift": 64, ",": 72, ".": 73, "/": 74, "RShift": 75,
         "Up": 90, "End": 107, "LCtrl": 80, "LWin": 81, "LAlt": 82, "Space": 83,
         "RAlt": 84, "Fn": 85, "RCtrl": 87, "Left": 88, "Down": 89, "Right": 91}
    k.update({f"F{i}": i for i in range(1, 13)})
    k.update({c: 17 + i for i, c in enumerate("1234567890")})
    k.update({c: 33 + i for i, c in enumerate("QWERTYUIOP")})
    k.update({c: 49 + i for i, c in enumerate("ASDFGHJKL")})
    k.update({c: 65 + i for i, c in enumerate("ZXCVBNM")})
    return k


KEYS = _keys()


def key_id(name: str) -> int:
    try:
        return KEYS[name]
    except KeyError:
        raise ValueError(f"unknown key name {name!r}; valid names: {', '.join(KEYS)}")


@dataclass
class Profile:
    name: str = "default"
    noise: int = 40            # raw counts below which a key reads as 0
    full: int = 1000           # raw counts treated as 100% press
    deadzone: float = 0.05     # applied to stick axes
    curve: float = 1.0         # >1 = gentler start, <1 = more sensitive start
    button_threshold: float = 0.5
    exit_key: str = "Esc"      # hold fully ~0.5 s to quit
    axes: dict = field(default_factory=lambda: {
        "left_x":  {"neg": "A",    "pos": "D"},
        "left_y":  {"neg": "S",    "pos": "W"},
        "right_x": {"neg": "Left", "pos": "Right"},
        "right_y": {"neg": "Down", "pos": "Up"},
    })
    triggers: dict = field(default_factory=lambda: {"left": "Q", "right": "E"})
    buttons: dict = field(default_factory=lambda: {   # key name -> pad button
        "Space": "A", "C": "B", "X": "X", "V": "Y", "LShift": "LB", "R": "RB",
    })

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)
