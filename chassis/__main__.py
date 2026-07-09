# python -m chassis {init,run,watch}

import argparse
import logging
import os
import sys

from . import config as config_mod
from .supervisor import Supervisor
from .watchdog import Watchdog

EXAMPLE_TOML = '''\
# bots.toml — declare your fleet once; supervisor and watchdog both read it.

[chassis]
alerts = ["console"]           # add "sms" and/or "webhook" once env vars are set
# digest_at = "16:35"          # daily digest, local time
# healthcheck_url = ""         # e.g. a healthchecks.io ping URL

[[bot]]
name = "hello"
command = "python3 hello_bot.py"
heartbeat_max_minutes = 5      # alert if the heartbeat file goes stale
log = "hello.log"              # watchdog scans this for error spikes
'''

EXAMPLE_BOT = '''\
from chassis import Bot

bot = Bot("hello", log_file="hello.log")

@bot.every(minutes=1)
def say_hello():
    bot.log.info("hello — replace me with real work")

bot.run()
'''


def cmd_init(_args):
    for name, content in [("bots.toml", EXAMPLE_TOML), ("hello_bot.py", EXAMPLE_BOT)]:
        if os.path.exists(name):
            print(f"{name} already exists — leaving it alone")
            continue
        with open(name, "w") as f:
            f.write(content)
        print(f"wrote {name}")
    print("\nNext:  python -m chassis run          # start + supervise the fleet"
          "\n       python -m chassis watch --once  # one watchdog pass")


def main():
    parser = argparse.ArgumentParser(prog="chassis",
                                     description="the boring 90% of every bot, done for you")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write a starter bots.toml + hello bot")
    for name, help_text in [("run", "spawn and supervise the fleet"),
                            ("watch", "run the independent watchdog")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("config", nargs="?", default="bots.toml")
        if name == "watch":
            p.add_argument("--once", action="store_true", help="single pass, then exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

    if args.cmd == "init":
        cmd_init(args)
        return

    if not os.path.exists(args.config):
        sys.exit(f"{args.config} not found — run 'python -m chassis init' to create one")
    cfg = config_mod.load(args.config)

    if args.cmd == "run":
        Supervisor(cfg).run()
    elif args.cmd == "watch":
        Watchdog(cfg).run(once=args.once)


if __name__ == "__main__":
    main()
