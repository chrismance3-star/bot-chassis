# bot-chassis

**The boring 90% of every bot, done for you.**

```
pip install bot-chassis
```

Anyone who has run a long-lived automation — a trading bot, an uptime monitor, a
scraper, a report generator — ends up rebuilding the same plumbing: a scheduler
loop, crash handling, restart logic, a way to know it's *hung* (not just dead),
alerts to your phone, a kill switch, state that survives crashes, and a second
process watching the first one. That plumbing is where the failures actually
happen, and it has nothing to do with your domain.

chassis is that plumbing as a product. You write the 10% that's yours; it runs
it like production infrastructure. **Zero dependencies** — pure Python stdlib,
3.11+.

## A complete bot

```python
from chassis import Bot

bot = Bot("uptime", log_file="uptime.log")

@bot.every(minutes=5)
def check():
    if not site_is_up("https://example.com"):
        bot.alert("DOWN: example.com")

bot.run()
```

That function now has, for free:

| You get | Meaning |
|---|---|
| Crash containment | An exception in a job is logged + alerted; the loop survives |
| Scheduling | `@bot.every(minutes=5)`, `@bot.daily_at("16:05", tz="America/New_York")`, optional `when=` guards |
| Heartbeat | A file touched every minute so *outside* processes can detect hangs |
| Kill switch | Drop a `STOP` file → jobs pause, remove it → they resume |
| Alerts | `bot.alert(...)` → console, SMS (email-to-SMS gateway), or webhook (Slack/Discord/ntfy) |
| State | `bot.state` — atomic, crash-safe JSON that survives restarts |

## A supervised fleet

Declare bots once in `bots.toml`:

```toml
[chassis]
alerts = ["sms", "console"]
digest_at = "16:35"                # daily summary text

[[bot]]
name = "uptime"
command = "python3 uptime_bot.py"
heartbeat_max_minutes = 10
log = "uptime.log"
```

Then:

```
chassis run     # spawn everything; restart crashes; give up on crash-loops; alert on hangs
chassis watch   # independent watchdog — still texts you when the supervisor itself dies
chassis dash    # mission control: http://localhost:8899 status page (+ /api/status JSON)
chassis init    # starter bots.toml + hello bot
```

(`python -m chassis` works everywhere the `chassis` script does.)

The **supervisor** restarts bots that die (with rapid-crash backoff so a
broken bot doesn't restart forever) and alerts on stale heartbeats. The
**watchdog** runs as a separate process and re-checks everything from outside —
processes, heartbeats, kill switch, error spikes in logs — with per-issue alert
cooldowns and an optional daily digest and healthchecks.io ping. Domain checks
plug in:

```python
wd = Watchdog(load("bots.toml"))

@wd.add_check
def account_equity():   # anything that returns [(key, message)]
    ...
```

## Troubleshooting

**Every HTTPS request fails instantly with `CERTIFICATE_VERIFY_FAILED`** (bot
jobs, the sms/webhook channels): your Python has no CA certificate bundle —
common with python.org installers on macOS. Either run the installer's
`Install Certificates.command`, or point Python at the system bundle:

```
export SSL_CERT_FILE=/etc/ssl/cert.pem
```

## Provenance

Extracted from a live multi-bot trading system where every one of these
features was added because its absence caused a real incident: a bot that ran
dead for a day with no alert (supervision), a hung process that passed the
liveness poll (heartbeats), burst SMS silently collapsed by the carrier
(delivery slots), a crash mid-write corrupting state (atomic saves), a launcher
that couldn't report its own death (external watchdog). That trading fleet
runs on bot-chassis today — this package is its production supervisor, not a
side project's abstraction of one.

Linux and macOS. Python 3.11+. Zero dependencies, and that's a promise, not
a current status.

## Layout

```
chassis/
  runner.py       Bot — the decorator API and job loop
  supervisor.py   fleet spawn/restart/heartbeat supervision
  watchdog.py     independent external health monitor
  dashboard.py    one-file status page + JSON API (localhost only)
  notify.py       alert fan-out: console / sms / webhook
  state.py        crash-safe JSON state
  config.py       bots.toml loader
examples/
  uptime_bot.py   a complete non-trading bot in ~40 lines
```

## License

MIT.
