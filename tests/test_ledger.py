"""ledger.py's CLI against a temporary state dir."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "skills" / "marque" / "scripts" / "ledger.py"


def run(*args, state_dir, env=None):
    e = {k: v for k, v in os.environ.items() if k != "MARQUE_LEDGER_CRASH_BEFORE_RENAME"}
    e.update(env or {})
    return subprocess.run(
        [sys.executable, str(LEDGER), "--state-dir", str(state_dir), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=e,
    )


class HelpTest(unittest.TestCase):
    def test_help_lists_every_state_and_its_meaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("--help", state_dir=tmp)

        self.assertEqual(r.returncode, 0, r.stderr)
        for state in (
            "queued",
            "exploring",
            "briefed",
            "running",
            "review",
            "retry",
            "orchestrator",
            "landing",
            "awaiting-approval",
            "landed",
            "needs-info",
            "blocked",
            "ready-for-human",
            "abandoned",
        ):
            self.assertIn(state, r.stdout)
        # The brief's state table, verbatim.
        self.assertIn("the guarded landing is under way", r.stdout)
        self.assertIn("the orchestrator is implementing the ticket itself", r.stdout)
        # The brief's in-flight list.
        self.assertIn("running, review, retry, orchestrator, landing", r.stdout)


if __name__ == "__main__":
    unittest.main()
