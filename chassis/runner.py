# chassis/runner.py — The bot you don't have to write
#
# A Bot wraps the boring-but-critical 90% of every long-running automation:
# logging, scheduling, crash containment, alerting, a heartbeat file for
# external supervision, a kill-switch file, and persistent state. The user
# supplies only the interesting 10% — the job functions.
#
#     from chassis import Bot
#
#     bot = Bot("uptime")
#
#     @bot.every(minutes=5)
#     def check():
#         ...
#
#     bot.run()
#
# One exception in a job never kills the bot: it's logged, alerted, and the
# next cycle runs on schedule.

import logging
import os
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from .notify import Notifier
from .state import StateFile

TICK_SECONDS = 1          # scheduler resolution
HEARTBEAT_EVERY = 60      # seconds between heartbeat touches


class _Job:
    def __init__(self, fn, label: str, when=None):
        self.fn = fn
        self.label = label
        self.when = when          # optional guard: run only if when() is truthy
        self.next_run = 0.0       # unix timestamp; 0 = run at startup

    def schedule_next(self):
        raise NotImplementedError


class _IntervalJob(_Job):
    def __init__(self, fn, interval_s: float, when=None, run_at_start=True):
        super().__init__(fn, f"{fn.__name__} (every {interval_s:.0f}s)", when)
        self.interval_s = interval_s
        if not run_at_start:
            self.next_run = time.time() + interval_s

    def schedule_next(self):
        self.next_run = time.time() + self.interval_s


class _DailyJob(_Job):
    def __init__(self, fn, at: str, tz: ZoneInfo, when=None):
        super().__init__(fn, f"{fn.__name__} (daily {at} {tz})", when)
        self.hour, self.minute = (int(x) for x in at.split(":"))
        self.tz = tz
        self.schedule_next()

    def schedule_next(self):
        now = datetime.now(self.tz)
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        self.next_run = target.timestamp()


class Bot:
    def __init__(
        self,
        name: str,
        *,
        status_dir: str = ".chassis",
        alerts: list[str] | None = None,
        log_file: str | None = None,
        stop_file: str = "STOP",
        state_defaults: dict | None = None,
    ):
        self.name = name
        self.status_dir = os.path.abspath(status_dir)
        os.makedirs(self.status_dir, exist_ok=True)

        self.heartbeat_file = os.path.join(self.status_dir, f"{name}.heartbeat")
        self.stop_file = os.path.abspath(stop_file)
        self.state = StateFile(
            os.path.join(self.status_dir, f"{name}.state.json"), state_defaults
        )
        self.notifier = Notifier(alerts)
        self._jobs: list[_Job] = []
        self._stopped_logged = False

        handlers: list[logging.Handler] = [logging.StreamHandler()]
        if log_file:
            handlers.append(RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3))
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)s  %(message)s",
            handlers=handlers,
            force=True,   # replace handlers attached by imports — prevents duplicate lines
        )
        self.log = logging.getLogger(name)

    # ── Registering jobs ──────────────────────────────────────────

    def every(self, *, seconds: float = 0, minutes: float = 0, hours: float = 0,
              when=None, run_at_start: bool = True):
        interval = seconds + minutes * 60 + hours * 3600
        if interval <= 0:
            raise ValueError("every() needs a positive interval")

        def decorator(fn):
            self._jobs.append(_IntervalJob(fn, interval, when, run_at_start))
            return fn
        return decorator

    def daily_at(self, at: str, *, tz: str | None = None, when=None):
        zone = ZoneInfo(tz) if tz else datetime.now().astimezone().tzinfo

        def decorator(fn):
            self._jobs.append(_DailyJob(fn, at, zone, when))
            return fn
        return decorator

    # ── Runtime ───────────────────────────────────────────────────

    def alert(self, message: str):
        self.notifier.send(f"{self.name.upper()}\n{message}")

    def _heartbeat(self):
        try:
            with open(self.heartbeat_file, "w") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass

    def _stopped(self) -> bool:
        stopped = os.path.exists(self.stop_file)
        if stopped and not self._stopped_logged:
            self.log.warning(f"Kill switch {self.stop_file} present — jobs paused")
            self._stopped_logged = True
        elif not stopped and self._stopped_logged:
            self.log.info("Kill switch removed — jobs resumed")
            self._stopped_logged = False
        return stopped

    def _run_job(self, job: _Job):
        if job.when and not job.when():
            return
        try:
            job.fn()
        except Exception as e:
            # Contain the blast radius: log, alert, keep the loop alive
            self.log.error(f"{job.label} failed: {e}", exc_info=True)
            self.alert(f"ERROR in {job.fn.__name__}\n{str(e)[:120]}")

    def run(self, once: bool = False):
        if not self._jobs:
            raise RuntimeError("no jobs registered — decorate functions with @bot.every / @bot.daily_at")

        self.log.info(f"{self.name} starting — {len(self._jobs)} job(s):")
        for job in self._jobs:
            self.log.info(f"  - {job.label}")

        if once:
            for job in self._jobs:
                self._run_job(job)
            self._heartbeat()
            return

        last_hb = 0.0
        try:
            while True:
                now = time.time()
                if now - last_hb > HEARTBEAT_EVERY:
                    self._heartbeat()   # heartbeat even while paused — process is alive
                    last_hb = now
                if not self._stopped():
                    for job in self._jobs:
                        if now >= job.next_run:
                            job.schedule_next()   # schedule first — a slow job must not double-fire
                            self._run_job(job)
                time.sleep(TICK_SECONDS)
        except KeyboardInterrupt:
            self.log.info(f"{self.name} stopped by user (Ctrl+C)")
