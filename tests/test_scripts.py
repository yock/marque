"""The moved skill's scripts still run from plugins/marque/skills/marque/."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts"


def run(script, *args, cwd):
    env = {k: v for k, v in os.environ.items() if k != "SYMPHONY_CONFIG"}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


class ScriptHelpTest(unittest.TestCase):
    def test_each_moved_script_prints_its_usage(self):
        # argparse's documented --help: exit 0 and a "usage: <prog>" line first.
        for name in ("frontier.py", "split_spec.py"):
            with self.subTest(script=name):
                r = run(SCRIPTS / name, "--help", cwd=REPO)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(r.stdout.startswith(f"usage: {name}"), r.stdout)
