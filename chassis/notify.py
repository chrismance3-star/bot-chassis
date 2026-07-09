# chassis/notify.py — Pluggable alert delivery
#
# Alerts fire in a background thread so they never block the bot's work
# loop, and each delivery retries before giving up. Channels:
#
#   console — always available, prints to stderr
#   sms     — email-to-SMS gateway via SMTP (how most carriers accept texts)
#   webhook — JSON POST, works out of the box with Slack/Discord/ntfy
#
# Configure via environment variables (a .env loader is NOT built in — the
# host app or supervisor exports them):
#
#   CHASSIS_SMTP_USER / CHASSIS_SMTP_PASSWORD  — SMTP login (e.g. Gmail + app password)
#   CHASSIS_SMS_TO                             — gateway address, e.g. 5551234567@vtext.com
#   CHASSIS_SMTP_HOST / CHASSIS_SMTP_PORT      — default smtp.gmail.com:587
#   CHASSIS_WEBHOOK_URL                        — where the webhook channel POSTs
#
# Email-to-SMS gateways collapse or drop near-identical messages that arrive
# in a burst, so each sender thread reserves a delivery slot at least
# MIN_SEND_GAP seconds after the previous one.

import json
import logging
import os
import smtplib
import threading
import time
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 4     # seconds between retries
MIN_SEND_GAP = 12   # seconds between SMS deliveries

_slot_lock = threading.Lock()
_next_slot = [0.0]


def _reserve_slot():
    with _slot_lock:
        slot = max(time.time(), _next_slot[0])
        _next_slot[0] = slot + MIN_SEND_GAP
    wait = slot - time.time()
    if wait > 0:
        time.sleep(wait)


def _with_retries(label: str, fn):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            fn()
            log.info(f"Alert delivered via {label} (attempt {attempt})")
            return
        except Exception as e:
            log.warning(f"{label} alert attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    log.error(f"{label} alert permanently failed after {MAX_RETRIES} attempts")


# ── Channels ──────────────────────────────────────────────────────

def _send_console(message: str):
    print(f"[ALERT] {message}", flush=True)


def _send_sms(message: str):
    user = os.getenv("CHASSIS_SMTP_USER")
    password = os.getenv("CHASSIS_SMTP_PASSWORD")
    to = os.getenv("CHASSIS_SMS_TO")
    if not (user and password and to):
        log.warning("sms channel skipped — CHASSIS_SMTP_USER/PASSWORD/SMS_TO not set")
        return
    host = os.getenv("CHASSIS_SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("CHASSIS_SMTP_PORT", "587"))

    _reserve_slot()

    def send():
        msg = MIMEText(message)
        msg["From"], msg["To"], msg["Subject"] = user, to, ""
        # STARTTLS on 587 is faster and more reliable than SSL/465 with Gmail
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

    _with_retries("sms", send)


def _send_webhook(message: str):
    url = os.getenv("CHASSIS_WEBHOOK_URL")
    if not url:
        log.warning("webhook channel skipped — CHASSIS_WEBHOOK_URL not set")
        return

    def send():
        # "text" covers Slack; "content" covers Discord; ntfy reads the body
        body = json.dumps({"text": message, "content": message}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=15).read()

    _with_retries("webhook", send)


_CHANNELS = {"console": _send_console, "sms": _send_sms, "webhook": _send_webhook}


class Notifier:
    """Fans an alert out to the configured channels, off the caller's thread."""

    def __init__(self, channels: list[str] | None = None):
        channels = channels if channels is not None else ["console"]
        unknown = [c for c in channels if c not in _CHANNELS]
        if unknown:
            raise ValueError(f"unknown alert channel(s): {unknown} — pick from {sorted(_CHANNELS)}")
        self.channels = channels

    def send(self, message: str):
        # Timestamp so a delayed delivery still tells you when it happened
        stamp = datetime.now().astimezone().strftime("%-I:%M%p").lower()
        full = f"[{stamp}] {message}"
        for name in self.channels:
            threading.Thread(target=_CHANNELS[name], args=(full,), daemon=True).start()
