# chassis — the boring 90% of every bot, done for you
#
# Library entry points:
#   Bot        — write one function, get a supervised, alerting, stateful bot
#   Notifier   — standalone alert fan-out (console / sms / webhook)
#   StateFile  — crash-safe JSON persistence
#   Supervisor — spawn + restart a fleet declared in bots.toml
#   Watchdog   — independent external health monitor
#
# CLI: python -m chassis {init,run,watch,dash}

from .config import ChassisConfig, load
from .notify import Notifier
from .runner import Bot
from .state import StateFile
from .supervisor import Supervisor
from .watchdog import Watchdog

__version__ = "0.1.0"
__all__ = ["Bot", "Notifier", "StateFile", "Supervisor", "Watchdog",
           "ChassisConfig", "load", "__version__"]
