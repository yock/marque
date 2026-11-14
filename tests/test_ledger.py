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


HEADER = "issue\tstate\tbranch\tworktree\tsession\tattempts\tbrief\tverdict\tlanded\tnote\n"


class SetAndGetTest(unittest.TestCase):
    def test_set_creates_the_ledger_with_the_header_and_get_prints_the_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            r = run("set", "5", "running", "--branch", "orch-5", state_dir=state_dir)
            self.assertEqual(r.returncode, 0, r.stderr)

            text = (state_dir / "ledger.tsv").read_text()
            self.assertEqual(text.split("\n")[0] + "\n", HEADER)

            r = run("get", "5", state_dir=state_dir)
            self.assertEqual(r.returncode, 0, r.stderr)
            # Ten fields, padded with empties.
            self.assertEqual(r.stdout, "5\trunning\torch-5\t\t\t\t\t\t\t\n")

    def test_get_of_a_row_that_does_not_exist_exits_one_and_prints_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            run("set", "5", "running", state_dir=state_dir)

            r = run("get", "99", state_dir=state_dir)

            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout, "")
            self.assertIn("no row for #99", r.stderr)


if __name__ == "__main__":
    unittest.main()
