# chassis/dashboard.py — Mission control in one file
#
# A read-only status page for the fleet, built entirely from artifacts the
# other pieces already produce: process liveness, heartbeat files, the
# watchdog's status snapshot, and log tails. No database, no javascript
# build, no dependencies — one stdlib HTTP server you can leave running.
#
# Run: python -m chassis dash [bots.toml] [--port 8899]
#   GET /            the dashboard page
#   GET /api/status  the same data as JSON (for your own tooling)

import json
import logging
import os
import subprocess
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import ChassisConfig
from .watchdog import process_pattern

log = logging.getLogger("dashboard")

LOG_TAIL_LINES = 12


def _tail(path: str, n: int = LOG_TAIL_LINES) -> list[str]:
    try:
        with open(path, errors="replace") as f:
            return [line.rstrip("\n") for line in deque(f, maxlen=n)]
    except OSError:
        return []


def _pid_alive(pid_file: str) -> bool:
    try:
        with open(pid_file) as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def build_status(cfg: ChassisConfig) -> dict:
    status_dir = cfg.path(cfg.status_dir)

    watchdog = None
    try:
        with open(os.path.join(status_dir, "watchdog.status.json")) as f:
            watchdog = json.load(f)
    except (OSError, ValueError):
        pass

    bots = []
    for bot in cfg.bots:
        try:
            r = subprocess.run(["pgrep", "-f", "--", process_pattern(bot.command)],
                               capture_output=True, timeout=10)
            running = r.returncode == 0
        except Exception:
            running = False

        hb_age = None
        try:
            hb_age = time.time() - os.path.getmtime(cfg.heartbeat_file(bot.name))
        except OSError:
            pass

        hb_max = bot.heartbeat_max_minutes * 60
        # healthy = process up AND (no heartbeat configured, or heartbeat fresh)
        healthy = running and (not hb_max or (hb_age is not None and hb_age <= hb_max))

        bots.append({
            "name": bot.name,
            "command": bot.command,
            "running": running,
            "healthy": healthy,
            "heartbeat_age_s": None if hb_age is None else round(hb_age),
            "heartbeat_max_s": round(hb_max) or None,
            "log_tail": _tail(cfg.path(bot.log)) if bot.log else [],
        })

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "supervisor_running": _pid_alive(os.path.join(status_dir, "supervisor.pid")),
        "stop_file_present": os.path.exists(cfg.path(cfg.stop_file)),
        "watchdog": watchdog,
        "bots": bots,
    }


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>chassis — mission control</title>
<style>
  body { font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
         background: #0d1117; color: #c9d1d9; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }
  h1 { font-size: 1.1rem; color: #e6edf3; }
  .meta { color: #8b949e; margin-bottom: 1.5rem; }
  .card { border: 1px solid #30363d; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
  .row { display: flex; gap: .6rem; align-items: baseline; }
  .dot { width: .65rem; height: .65rem; border-radius: 50%; align-self: center; }
  .up   { background: #3fb950; } .down { background: #f85149; }
  .name { font-weight: 700; color: #e6edf3; }
  .cmd, .hb { color: #8b949e; font-size: .85rem; }
  .issues { color: #f85149; }
  pre { background: #010409; border-radius: 6px; padding: .6rem;
        overflow-x: auto; font-size: .8rem; color: #8b949e; margin: .6rem 0 0; }
  .banner { border: 1px solid #f8514966; background: #f8514912; color: #f85149;
            border-radius: 8px; padding: .6rem 1rem; margin-bottom: 1rem; }
</style></head><body>
<h1>chassis — mission control</h1>
<div class="meta" id="meta">loading…</div>
<div id="banners"></div>
<div id="bots"></div>
<script>
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const age = s => s == null ? 'n/a' : s < 90 ? s + 's' : Math.round(s/60) + 'm';
async function refresh() {
  let d;
  try { d = await (await fetch('/api/status')).json(); }
  catch (e) { document.getElementById('meta').textContent = 'dashboard unreachable'; return; }
  document.getElementById('meta').textContent =
    `updated ${new Date(d.generated_at).toLocaleTimeString()} — supervisor ` +
    (d.supervisor_running ? 'running' : 'NOT RUNNING');
  let banners = '';
  if (d.stop_file_present) banners += '<div class="banner">kill switch present — bots paused</div>';
  if (d.watchdog && d.watchdog.issues && d.watchdog.issues.length)
    banners += '<div class="banner">watchdog: ' + d.watchdog.issues.map(esc).join(' · ') + '</div>';
  document.getElementById('banners').innerHTML = banners;
  document.getElementById('bots').innerHTML = d.bots.map(b => `
    <div class="card">
      <div class="row">
        <span class="dot ${b.healthy ? 'up' : 'down'}"></span>
        <span class="name">${esc(b.name)}</span>
        <span class="cmd">${esc(b.command)}</span>
        <span class="hb">heartbeat ${age(b.heartbeat_age_s)}${b.heartbeat_max_s ? ' / limit ' + age(b.heartbeat_max_s) : ''}</span>
      </div>
      ${b.log_tail.length ? '<pre>' + esc(b.log_tail.join('\\n')) + '</pre>' : ''}
    </div>`).join('');
}
refresh(); setInterval(refresh, 5000);
</script></body></html>
"""


def serve(cfg: ChassisConfig, port: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                body = json.dumps(build_status(cfg), indent=2).encode()
                ctype = "application/json"
            elif self.path == "/":
                body = PAGE.encode()
                ctype = "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):   # route access noise through logging
            log.debug(fmt % args)

    # localhost only: the page exposes log contents — bind nothing to 0.0.0.0
    # unless the user reverse-proxies it deliberately
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log.info(f"Dashboard on http://localhost:{port}/ ({len(cfg.bots)} bot(s))")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Dashboard stopped")
