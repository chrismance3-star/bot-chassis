# chassis/config.py — bots.toml loader
#
# One TOML file describes the whole fleet. The supervisor and the watchdog
# both read it, so a bot declared once is spawned, restarted, heartbeat-
# checked, and log-scanned with no further wiring.

import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class BotSpec:
    name: str
    command: str                      # shell command that runs the bot
    heartbeat_max_minutes: float = 0  # 0 = don't check heartbeat freshness
    heartbeat_file: str = ""          # override — adopt a pre-existing bot's heartbeat path
    log: str = ""                     # log file the watchdog scans for error spikes
    log_max_silence_hours: float = 0  # alert if the log's mtime is older (0 = don't check)


@dataclass
class ChassisConfig:
    root: str
    bots: list[BotSpec]
    alerts: list[str] = field(default_factory=lambda: ["console"])
    status_dir: str = ".chassis"
    stop_file: str = "STOP"
    digest_at: str = ""               # "HH:MM" local time; empty = no daily digest
    healthcheck_url: str = ""         # dead man's switch ping (healthchecks.io etc.)
    check_interval_minutes: float = 10
    realert_cooldown_hours: float = 6
    error_spike_threshold: int = 5

    def path(self, rel: str) -> str:
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)

    def heartbeat_file(self, bot_name: str) -> str:
        for bot in self.bots:
            if bot.name == bot_name and bot.heartbeat_file:
                return self.path(bot.heartbeat_file)
        return os.path.join(self.path(self.status_dir), f"{bot_name}.heartbeat")


def load(config_path: str) -> ChassisConfig:
    config_path = os.path.abspath(config_path)
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    top = raw.get("chassis", {})
    bots_raw = raw.get("bot", [])
    if not bots_raw:
        raise ValueError(f"{config_path}: no [[bot]] entries found")

    bots = []
    seen = set()
    for entry in bots_raw:
        if "name" not in entry or "command" not in entry:
            raise ValueError(f"{config_path}: every [[bot]] needs 'name' and 'command'")
        if entry["name"] in seen:
            raise ValueError(f"{config_path}: duplicate bot name '{entry['name']}'")
        seen.add(entry["name"])
        bots.append(BotSpec(
            name=entry["name"],
            command=entry["command"],
            heartbeat_max_minutes=float(entry.get("heartbeat_max_minutes", 0)),
            heartbeat_file=entry.get("heartbeat_file", ""),
            log=entry.get("log", ""),
            log_max_silence_hours=float(entry.get("log_max_silence_hours", 0)),
        ))

    known = {f.name for f in ChassisConfig.__dataclass_fields__.values()} - {"root", "bots"}
    unknown = set(top) - known
    if unknown:
        raise ValueError(f"{config_path}: unknown [chassis] key(s): {sorted(unknown)}")

    return ChassisConfig(root=os.path.dirname(config_path), bots=bots, **top)
