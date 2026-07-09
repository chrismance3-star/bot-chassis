# chassis/state.py — Crash-safe JSON state for bots
#
# Every bot needs to remember things between cycles (positions, offsets,
# last-alert times). A plain json.dump() that dies mid-write corrupts the
# file and the bot wakes up amnesiac. Writes here go to a temp file first,
# then atomically replace the real one.

import json
import os


class StateFile:
    def __init__(self, path: str, defaults: dict | None = None):
        self.path = os.path.abspath(path)
        self.defaults = defaults or {}

    def load(self) -> dict:
        try:
            with open(self.path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("state root is not a dict")
        except Exception:
            data = {}
        for key, value in self.defaults.items():
            data.setdefault(key, value)
        return data

    def save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, self.path)

    def update(self, **changes) -> dict:
        """Load, apply changes, save, return the new state."""
        data = self.load()
        data.update(changes)
        self.save(data)
        return data
