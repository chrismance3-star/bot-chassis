# chassis/supervisor.py — Starts the fleet, keeps it alive
#
# One process spawns every bot in bots.toml, then supervises: a bot that
# dies is restarted and alerted on; a bot that crash-loops is given up on
# (restarting forever just spams alerts and hides the real problem); a bot
# whose heartbeat goes stale gets a hang alert — a stuck process still
# passes a liveness poll, so exit codes alone aren't enough.
#
# Run: python -m chassis run [bots.toml]

import logging
import os
import shlex
import subprocess
import sys
import time

from .config import ChassisConfig
from .notify import Notifier

log = logging.getLogger("supervisor")

CHECK_INTERVAL = 30       # seconds between liveness checks
RAPID_CRASH_WINDOW = 180  # a death this soon after start counts as a rapid crash
MAX_RAPID_CRASHES = 3     # stop restarting after this many rapid crashes in a row


class Supervisor:
    def __init__(self, config: ChassisConfig):
        self.config = config
        self.notifier = Notifier(config.alerts)
        self.lock_file = os.path.join(config.path(config.status_dir), "supervisor.pid")
        self.procs: dict[str, dict] = {}

    # ── Single-instance lock ──────────────────────────────────────
    # A second supervisor would spawn duplicate bots and both would
    # fight to restart each other's casualties.

    def acquire_lock(self):
        os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file) as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, 0)   # 0 = just check the process exists
                sys.exit(f"supervisor already running (PID {old_pid}) — stop it first: kill {old_pid}")
            except (OSError, ValueError):
                pass   # stale lock — safe to continue
        with open(self.lock_file, "w") as f:
            f.write(str(os.getpid()))

    def release_lock(self):
        try:
            os.remove(self.lock_file)
        except OSError:
            pass

    # ── Process management ────────────────────────────────────────

    def _spawn(self, bot) -> subprocess.Popen:
        console_log = self.config.path(f"{bot.name}.console.log")
        out = open(console_log, "a")
        return subprocess.Popen(
            shlex.split(bot.command),
            cwd=self.config.root, stdout=out, stderr=subprocess.STDOUT,
        )

    def start_all(self):
        for bot in self.config.bots:
            log.info(f"Starting {bot.name}: {bot.command}")
            self.procs[bot.name] = {
                "spec": bot,
                "proc": self._spawn(bot),
                "last_start": time.time(),
                "rapid_crashes": 0,
                "hb_alerted": False,
            }

    def _check_heartbeat(self, name: str, entry: dict):
        bot = entry["spec"]
        if not bot.heartbeat_max_minutes:
            return
        max_age = bot.heartbeat_max_minutes * 60
        if time.time() - entry["last_start"] <= max_age:
            return   # too young — the bot hasn't had time to heartbeat yet
        try:
            hb_age = time.time() - os.path.getmtime(self.config.heartbeat_file(name))
        except FileNotFoundError:
            hb_age = float("inf")
        if hb_age > max_age and not entry["hb_alerted"]:
            log.warning(f"{name}: no heartbeat for {hb_age/60:.0f} min — may be hung")
            self.notifier.send(
                f"SUPERVISOR\n{name} has not heartbeated in {hb_age/60:.0f} min — may be hung."
            )
            entry["hb_alerted"] = True
        elif hb_age <= max_age:
            entry["hb_alerted"] = False

    def _check_exit(self, name: str, entry: dict):
        code = entry["proc"].poll()
        if code is None:
            self._check_heartbeat(name, entry)
            return
        if entry["rapid_crashes"] >= MAX_RAPID_CRASHES:
            return   # already gave up on this one

        rapid = (time.time() - entry["last_start"]) < RAPID_CRASH_WINDOW
        entry["rapid_crashes"] = entry["rapid_crashes"] + 1 if rapid else 0

        if entry["rapid_crashes"] >= MAX_RAPID_CRASHES:
            log.error(f"{name} keeps crashing (exit {code}) — giving up. Check its logs.")
            self.notifier.send(f"SUPERVISOR\n{name} keeps crashing (exit {code}).\nNOT restarting — check logs.")
            return

        log.warning(f"{name} exited with code {code} — restarting")
        self.notifier.send(f"SUPERVISOR\n{name} died (exit {code}) — restarted automatically.")
        entry["proc"] = self._spawn(entry["spec"])
        entry["last_start"] = time.time()

    # ── Main loop ─────────────────────────────────────────────────

    def run(self):
        self.acquire_lock()
        try:
            self.start_all()
            log.info(f"Supervising {len(self.procs)} bot(s). Ctrl+C stops everything.")
            while True:
                time.sleep(CHECK_INTERVAL)
                for name, entry in self.procs.items():
                    self._check_exit(name, entry)
        except KeyboardInterrupt:
            log.info("Shutting down all bots...")
            for entry in self.procs.values():
                entry["proc"].terminate()
        finally:
            self.release_lock()
