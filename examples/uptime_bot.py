# examples/uptime_bot.py — a complete non-trading bot in ~40 lines
#
# Checks a list of URLs every few minutes and alerts when a site goes down
# or comes back. Everything else — scheduling, crash containment, logging,
# heartbeat, kill switch, remembering what was already alerted — is chassis.
#
# Run directly:            python3 examples/uptime_bot.py
# Or supervised:           python -m chassis run examples/bots.toml

import os
import sys
import urllib.request

# Make the example runnable straight from a clone, no pip install needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chassis import Bot

SITES = [
    "https://example.com",
    "https://httpbin.org/status/200",
]

bot = Bot("uptime", log_file="uptime.log")


def check(url: str) -> str:
    """Empty string if the site is up, otherwise the failure reason."""
    try:
        status = urllib.request.urlopen(url, timeout=10).status
        return "" if status < 400 else f"HTTP {status}"
    except Exception as e:
        return str(e)[:80]


@bot.every(minutes=5)
def check_sites():
    state = bot.state.load()
    down = set(state.get("down", []))
    for url in SITES:
        reason = check(url)
        up = not reason
        bot.log.info(f"{url} — {'UP' if up else f'DOWN ({reason})'}")
        if not up and url not in down:
            bot.alert(f"DOWN: {url}\n{reason}")
            down.add(url)
        elif up and url in down:
            bot.alert(f"RECOVERED: {url}")
            down.discard(url)
    bot.state.update(down=sorted(down))


if __name__ == "__main__":
    bot.run()
