"""The battery-pacing example script, against a fake power supply."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "examples" / "battery-pacing" / "battery.sh"


class BatteryPacingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.ps = self.root / "power_supply"
        for name, kind in (("BAT0", "Battery"), ("AC", "Mains")):
            (self.ps / name).mkdir(parents=True)
            (self.ps / name / "type").write_text(f"{kind}\n")
        (self.ps / "AC" / "online").write_text("1\n")
        self.log = self.root / "battery.log"

    def supply(self, capacity, status="Discharging"):
        (self.ps / "BAT0" / "capacity").write_text(f"{capacity}\n")
        (self.ps / "BAT0" / "status").write_text(f"{status}\n")

    def battery(self, *args, **env):
        environ = {
            k: v for k, v in os.environ.items() if not k.startswith("BATTERY_PACING_")
        }
        environ["BATTERY_PACING_POWER_SUPPLY"] = str(self.ps)
        environ.update(env)
        return subprocess.run(
            [str(SCRIPT), *args], capture_output=True, text=True, env=environ, timeout=30
        )

    def test_now_prints_the_capacity_status_and_adapter(self):
        # Format from battery.sh's header: "capacity status adapter=0|1".
        self.supply(55, "Discharging")
        r = self.battery("now")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "55 Discharging adapter=1\n")

    def test_watch_run_stops_at_emergency(self):
        self.supply(15)
        r = self.battery("watch", "run", str(self.log))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "EMERGENCY 15\n")
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_watch_run_stops_at_low(self):
        self.supply(35)
        r = self.battery("watch", "run", str(self.log))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "LOW 35\n")
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_watch_wait_stops_at_resume(self):
        self.supply(70, "Charging")
        r = self.battery("watch", "wait", str(self.log))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "RESUME 70\n")

    def test_the_thresholds_come_from_the_environment(self):
        # BATTERY_PACING_LOW is the example's own variable (#32).
        self.supply(45)
        r = self.battery("watch", "run", str(self.log), BATTERY_PACING_LOW="50")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "LOW 45\n")
