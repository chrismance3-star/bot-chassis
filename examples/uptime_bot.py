# examples/uptime_bot.py — a complete non-trading bot in ~40 lines
#
# Checks a list of URLs every few minutes and alerts when a site goes down
# or comes back. Everything else — scheduling, crash containment, logging,
# heartbeat, kill switch, remembering what was already alerted — is chassis.
#
# Run directly:            python3 examples/uptime_bot.py
# Or supervised:           python -m chassis run examples/bots.toml

import urllib.request

from chassis import Bot

SITES = [
    "https://example.com",
    "https://httpbin.org/status/200",
]

bot = Bot("uptime", log_file="uptime.log")


def is_up(url: str) -> bool:
    try:
        return urllib.request.urlopen(url, timeout=10).status < 400
    except Exception:
        return False


@bot.every(minutes=5)
def check_sites():
    state = bot.state.load()
    down = set(state.get("down", []))
    for url in SITES:
        up = is_up(url)
        bot.log.info(f"{url} — {'UP' if up else 'DOWN'}")
        if not up and url not in down:
            bot.alert(f"DOWN: {url}")
            down.add(url)
        elif up and url in down:
            bot.alert(f"RECOVERED: {url}")
            down.discard(url)
    bot.state.update(down=sorted(down))


if __name__ == "__main__":
    bot.run()
