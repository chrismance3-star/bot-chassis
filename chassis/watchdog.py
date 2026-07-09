# chassis/watchdog.py — Independent health watchdog
#
# The supervisor alerts while it is alive; the watchdog watches from
# OUTSIDE, as a separate process, so it can still reach you when the
# supervisor itself dies. Checks, per cycle:
#
#   - every bot process running
#   - heartbeat freshness (a hung process still passes the liveness poll)
#   - kill-switch file present (you probably forgot to remove it)
#   - error spikes in bot logs (only lines added since the last cycle)
#   - custom checks registered by the host app
#
# Plus a daily digest, a re-alert cooldown so one broken bot doesn't text
# you every 10 minutes, and an optional healthchecks.io-style ping so a
# dead watchdog is itself detected.
#
# Alert-only by design: it reports, it never touches the bots.
# Run: python -m chassis watch [bots.toml] [--once]

import json
import logging
import os
import shlex
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta

from .config import ChassisConfig
from .notify import Notifier
from .state import StateFile

log = logging.getLogger("watchdog")

ERROR_MARKERS = ("ERROR", "CRITICAL", "Traceback")


def process_pattern(command: str) -> str:
    """What to pgrep for. The live cmdline often resolves the executable
    differently than written ("python3 x.py" runs as ".../Python x.py"),
    so match on the arguments and only fall back to the whole command."""
    parts = shlex.split(command)
    return " ".join(parts[1:]) if len(parts) > 1 else command


class Watchdog:
    def __init__(self, config: ChassisConfig):
        self.config = config
        self.notifier = Notifier(config.alerts)
        status_dir = config.path(config.status_dir)
        self.state = StateFile(
            os.path.join(status_dir, "watchdog.state.json"),
            defaults={"last_alerts": {}, "log_offsets": {}, "digest_sent_date": None},
        )
        self.status_file = os.path.join(status_dir, "watchdog.status.json")
        # Custom checks: callables returning [(key, message)] — how a host
        # app adds domain checks (equity drop, queue depth, disk space...)
        self.custom_checks: list = []

    def add_check(self, fn):
        self.custom_checks.append(fn)
        return fn

    # ── Re-alert cooldown ─────────────────────────────────────────

    def _should_alert(self, state: dict, key: str) -> bool:
        last = state["last_alerts"].get(key)
        if last:
            try:
                cooldown = timedelta(hours=self.config.realert_cooldown_hours)
                if datetime.now().astimezone() - datetime.fromisoformat(last) < cooldown:
                    return False
            except Exception:
                pass
        return True

    # ── Built-in checks — each returns [(key, message)] ───────────

    def check_processes(self) -> list:
        issues = []
        for bot in self.config.bots:
            try:
                r = subprocess.run(["pgrep", "-f", "--", process_pattern(bot.command)],
                                   capture_output=True, timeout=10)
                if r.returncode != 0:
                    issues.append((f"proc:{bot.name}",
                                   f"{bot.name} process is NOT running ({bot.command})"))
            except Exception as e:
                issues.append((f"proc-check:{bot.name}", f"could not check {bot.name}: {e}"))
        return issues

    def check_heartbeats(self) -> list:
        issues = []
        for bot in self.config.bots:
            if not bot.heartbeat_max_minutes:
                continue
            path = self.config.heartbeat_file(bot.name)
            try:
                age_min = (time.time() - os.path.getmtime(path)) / 60
                if age_min > bot.heartbeat_max_minutes:
                    issues.append((f"heartbeat:{bot.name}",
                                   f"{bot.name} heartbeat is {age_min:.0f} min old "
                                   f"(limit {bot.heartbeat_max_minutes:.0f}) — bot may be hung"))
            except FileNotFoundError:
                issues.append((f"heartbeat:{bot.name}", f"{bot.name} heartbeat file missing"))
        return issues

    def check_stop_file(self) -> list:
        path = self.config.path(self.config.stop_file)
        if os.path.exists(path):
            return [("stop", f"kill switch {self.config.stop_file} is present — bots are paused")]
        return []

    def check_log_errors(self, state: dict) -> list:
        issues = []
        for bot in self.config.bots:
            if not bot.log:
                continue
            path = self.config.path(bot.log)
            try:
                size = os.path.getsize(path)
            except FileNotFoundError:
                continue
            offset = state["log_offsets"].get(bot.log, size)
            if offset > size:   # rotated/truncated — start over
                offset = 0
            new_errors = []
            try:
                with open(path, errors="replace") as f:
                    f.seek(offset)
                    for line in f:
                        if any(m in line for m in ERROR_MARKERS):
                            new_errors.append(line.strip())
            except Exception:
                continue
            state["log_offsets"][bot.log] = size
            if len(new_errors) >= self.config.error_spike_threshold:
                issues.append((f"errors:{bot.name}",
                               f"{len(new_errors)} new error lines in {bot.log} "
                               f"— last: {new_errors[-1][:120]}"))
        return issues

    # ── Daily digest ──────────────────────────────────────────────

    def _digest_due(self, state: dict) -> bool:
        if not self.config.digest_at:
            return False
        now = datetime.now().astimezone()
        hour, minute = (int(x) for x in self.config.digest_at.split(":"))
        after = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return now >= after and state.get("digest_sent_date") != now.strftime("%Y-%m-%d")

    def _build_digest(self, issues: list, alerts_today: int) -> str:
        lines = [f"CHASSIS DAILY DIGEST — {len(self.config.bots)} bot(s)"]
        down = [k.split(":", 1)[1] for k, _ in issues if k.startswith(("proc:", "heartbeat:"))]
        lines.append("All bots healthy" if not down else "Unhealthy: " + ", ".join(sorted(set(down))))
        lines.append(f"{alerts_today} alert(s) today")
        return "\n".join(lines)

    # ── Main cycle ────────────────────────────────────────────────

    def run_checks(self) -> list:
        state = self.state.load()
        issues = (self.check_processes() + self.check_heartbeats()
                  + self.check_stop_file() + self.check_log_errors(state))
        for check in self.custom_checks:
            try:
                issues += list(check())
            except Exception as e:
                issues.append((f"check:{check.__name__}", f"custom check {check.__name__} failed: {e}"))

        today = datetime.now().astimezone().strftime("%Y-%m-%d")
        new = [(k, m) for k, m in issues if self._should_alert(state, k)]
        if new:
            body = "\n".join(f"- {m}" for _, m in new[:6])
            self.notifier.send(f"WATCHDOG\n{body}")
            for k, _ in new:
                state["last_alerts"][k] = datetime.now().astimezone().isoformat()
            state[f"alert_count:{today}"] = state.get(f"alert_count:{today}", 0) + len(new)

        if self._digest_due(state):
            self.notifier.send(self._build_digest(issues, state.get(f"alert_count:{today}", 0)))
            state["digest_sent_date"] = today

        # Status snapshot for dashboards / remote inspection
        try:
            with open(self.status_file, "w") as f:
                json.dump({"checked_at": datetime.now().astimezone().isoformat(),
                           "issues": [m for _, m in issues]}, f, indent=2)
        except Exception:
            pass

        if self.config.healthcheck_url:
            try:
                urllib.request.urlopen(self.config.healthcheck_url, timeout=10)
            except Exception as e:
                log.warning(f"Healthcheck ping failed: {e}")

        self.state.save(state)
        return issues

    def run(self, once: bool = False):
        interval = self.config.check_interval_minutes
        log.info(f"Watchdog started (interval {interval:g} min{', single run' if once else ''})")
        while True:
            issues = self.run_checks()
            log.info("All checks passed" if not issues
                     else f"{len(issues)} issue(s): " + "; ".join(m for _, m in issues))
            if once:
                return issues
            time.sleep(interval * 60)
