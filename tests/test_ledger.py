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

    def test_set_on_an_existing_row_changes_only_the_fields_it_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            run("set", "5", "running", "--branch", "orch-5", state_dir=state_dir)

            run("set", "5", "review", "--verdict", "pass", state_dir=state_dir)

            self.assertEqual(run("get", "5", "branch", state_dir=state_dir).stdout, "orch-5\n")
            self.assertEqual(run("get", "5", "verdict", state_dir=state_dir).stdout, "pass\n")

    def test_set_refuses_an_unknown_state_and_names_the_allowed_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            run("set", "5", "running", "--branch", "orch-5", state_dir=state_dir)
            before = (state_dir / "ledger.tsv").read_bytes()

            r = run("set", "5", "opus", state_dir=state_dir)

            self.assertEqual(r.returncode, 2)
            self.assertIn("opus", r.stderr)
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
                self.assertIn(state, r.stderr)
            self.assertEqual((state_dir / "ledger.tsv").read_bytes(), before)

    def test_set_refuses_a_value_that_would_break_the_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            run("set", "5", "running", "--branch", "orch-5", state_dir=state_dir)
            before = (state_dir / "ledger.tsv").read_bytes()

            for value in ("a\tb", "a\nb"):
                with self.subTest(value=value):
                    r = run("set", "5", "review", "--note", value, state_dir=state_dir)

                    self.assertEqual(r.returncode, 2)
                    self.assertEqual((state_dir / "ledger.tsv").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
