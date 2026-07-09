# tests/smoke.py — dependency-free smoke tests (plain asserts, no pytest)
# Run: python3 tests/smoke.py

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chassis import Bot, StateFile, load
from chassis.dashboard import build_status
from chassis.watchdog import Watchdog, process_pattern


def test_state_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        sf = StateFile(os.path.join(d, "s.json"), defaults={"count": 0})
        assert sf.load() == {"count": 0}
        sf.update(count=3, name="x")
        assert sf.load() == {"count": 3, "name": "x"}
        # corrupt file falls back to defaults instead of crashing
        with open(sf.path, "w") as f:
            f.write("{not json")
        assert sf.load() == {"count": 0}


def test_config_load_and_validation():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bots.toml")
        with open(path, "w") as f:
            f.write('[chassis]\nalerts=["console"]\n'
                    '[[bot]]\nname="a"\ncommand="python3 a.py"\nheartbeat_max_minutes=5\n')
        cfg = load(path)
        assert cfg.bots[0].name == "a"
        assert cfg.heartbeat_file("a").endswith(".chassis/a.heartbeat")
        # unknown [chassis] key is rejected loudly, not silently ignored
        with open(path, "w") as f:
            f.write('[chassis]\ntypo_key=1\n[[bot]]\nname="a"\ncommand="x"\n')
        try:
            load(path)
            raise AssertionError("expected ValueError for unknown key")
        except ValueError:
            pass


def test_bot_runs_jobs_and_contains_errors(tmpdir):
    ran = []
    bot = Bot("smoke", status_dir=os.path.join(tmpdir, ".chassis"),
              stop_file=os.path.join(tmpdir, "STOP"))

    @bot.every(seconds=1)
    def good():
        ran.append("good")

    @bot.every(seconds=1)
    def bad():
        raise RuntimeError("boom")

    bot.run(once=True)   # the bad job must not stop the good one
    assert ran == ["good"]
    assert os.path.exists(bot.heartbeat_file)
    bot.state.update(k="v")
    assert bot.state.load()["k"] == "v"


def test_process_pattern():
    # match on the script, not the interpreter: "python3 x.py" may run as
    # ".../Python x.py", so the interpreter token must not be in the pattern
    assert process_pattern("python3 uptime_bot.py") == "uptime_bot.py"
    assert process_pattern("python3 -m mypkg --flag") == "-m mypkg --flag"
    assert process_pattern("single-binary") == "single-binary"


def test_watchdog_once(tmpdir):
    path = os.path.join(tmpdir, "bots.toml")
    hb_dir = os.path.join(tmpdir, ".chassis")
    os.makedirs(hb_dir)
    with open(path, "w") as f:
        f.write('[chassis]\nalerts=["console"]\n'
                '[[bot]]\nname="ghost"\ncommand="definitely-not-running-xyz"\n'
                'heartbeat_max_minutes=1\nheartbeat_file="legacy/.hb"\n'
                'log="ghost.log"\nlog_max_silence_hours=1\n')
    # stale heartbeat at an adopted (non-default) location
    os.makedirs(os.path.join(tmpdir, "legacy"))
    hb = os.path.join(tmpdir, "legacy", ".hb")
    with open(hb, "w") as f:
        f.write("0")
    os.utime(hb, (time.time() - 600, time.time() - 600))
    # log last written 2h ago — silent past its 1h cadence
    log_path = os.path.join(tmpdir, "ghost.log")
    with open(log_path, "w") as f:
        f.write("fine\n")
    os.utime(log_path, (time.time() - 7200, time.time() - 7200))

    cfg = load(path)
    assert cfg.heartbeat_file("ghost") == hb
    wd = Watchdog(cfg)
    issues = wd.run_checks()
    keys = {k for k, _ in issues}
    assert "proc:ghost" in keys, keys
    assert "heartbeat:ghost" in keys, keys
    assert "silence:ghost" in keys, keys
    # cooldown: second pass finds the same issues but they are not "new"
    state = wd.state.load()
    assert all(not wd._should_alert(state, k) for k in keys)

    # dashboard status built from the same artifacts: dead bot, stale heartbeat,
    # watchdog snapshot picked up
    status = build_status(load(path))
    bot = status["bots"][0]
    assert bot["name"] == "ghost" and not bot["running"] and not bot["healthy"]
    assert bot["heartbeat_age_s"] >= 590
    assert not status["supervisor_running"]
    assert status["watchdog"] and len(status["watchdog"]["issues"]) >= 2


if __name__ == "__main__":
    test_state_roundtrip()
    test_config_load_and_validation()
    test_process_pattern()
    with tempfile.TemporaryDirectory() as d:
        test_bot_runs_jobs_and_contains_errors(d)
    with tempfile.TemporaryDirectory() as d:
        test_watchdog_once(d)
    print("all smoke tests passed")
