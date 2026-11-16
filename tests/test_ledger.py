"""ledger.py's CLI against a temporary state dir."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts" / "ledger.py"
STUBS = Path(__file__).resolve().parent / "stubs"


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


ALL_STATE_ROWS = """\
issue	state	branch	worktree	session	attempts	brief	verdict	landed	note
1	queued
2	exploring
3	briefed
4	running
5	review
6	retry
7	orchestrator
8	landing
9	awaiting-approval
10	landed
11	needs-info
12	blocked
13	ready-for-human
14	abandoned
15	blocked-ext
"""


class ListAndRecoverTest(unittest.TestCase):
    def test_recover_prints_only_the_in_flight_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            (state_dir / "ledger.tsv").write_text(ALL_STATE_ROWS)

            r = run("recover", state_dir=state_dir)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(
                r.stdout,
                "4\trunning\t\t\t\t\t\t\t\t\n"
                "5\treview\t\t\t\t\t\t\t\t\n"
                "6\tretry\t\t\t\t\t\t\t\t\n"
                "7\torchestrator\t\t\t\t\t\t\t\t\n"
                "8\tlanding\t\t\t\t\t\t\t\t\n",
            )

    def test_list_prints_every_row_in_file_order_or_one_state_s(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            (state_dir / "ledger.tsv").write_text(
                "issue\tstate\tbranch\tworktree\tsession\tattempts\tbrief\tverdict\tlanded\tnote\n"
                "1\tlanded\torch-1\twt1\ts1\t1\tb1\tpass\tabc123\tn1\n"
                "2\tblocked-ext\torch-2\twt2\ts2\t2\tb2\t\tabc124\tn2\n"
                "3\trunning\torch-3\twt3\ts3\t3\tb3\t\tabc125\tn3\n"
            )

            r = run("list", "--state", "landed", state_dir=state_dir)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "1\tlanded\torch-1\twt1\ts1\t1\tb1\tpass\tabc123\tn1\n")

            r = run("list", state_dir=state_dir)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(
                r.stdout,
                "1\tlanded\torch-1\twt1\ts1\t1\tb1\tpass\tabc123\tn1\n"
                "2\tblocked-ext\torch-2\twt2\ts2\t2\tb2\t\tabc124\tn2\n"
                "3\trunning\torch-3\twt3\ts3\t3\tb3\t\tabc125\tn3\n",
            )

    def test_set_leaves_other_rows_unchanged_even_in_an_unknown_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            (state_dir / "ledger.tsv").write_text(
                "issue\tstate\tbranch\tworktree\tsession\tattempts\tbrief\tverdict\tlanded\tnote\n"
                "1\tlanded\torch-1\twt1\ts1\t1\tb1\tpass\tabc123\tn1\n"
                "2\tblocked-ext\torch-2\twt2\ts2\t2\tb2\t\tabc124\tn2\n"
                "3\trunning\torch-3\twt3\ts3\t3\tb3\t\tabc125\tn3\n"
            )

            r = run("set", "3", "review", "--note", "changed", state_dir=state_dir)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(
                run("get", "2", state_dir=state_dir).stdout,
                "2\tblocked-ext\torch-2\twt2\ts2\t2\tb2\t\tabc124\tn2\n",
            )

    def test_an_interrupted_set_leaves_the_old_ledger_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            run("set", "5", "running", "--branch", "orch-5", state_dir=state_dir)
            before = (state_dir / "ledger.tsv").read_bytes()

            r = run(
                "set",
                "5",
                "landed",
                state_dir=state_dir,
                env={"MARQUE_LEDGER_CRASH_BEFORE_RENAME": "1"},
            )

            # os._exit(70): the process dies between the write and the rename.
            self.assertEqual(r.returncode, 70)
            self.assertEqual((state_dir / "ledger.tsv").read_bytes(), before)
            # The temp file is left behind, as a real kill would leave it.
            self.assertNotEqual(list(state_dir.glob(".ledger.*.tmp")), [])


def stub_env(tmp):
    """The env that puts the stub `beam` first on PATH, ahead of the real one."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("STUB_BEAM")}
    env["PATH"] = str(STUBS) + os.pathsep + env.get("PATH", "")
    env["STUB_BEAM_STATE"] = str(Path(tmp) / "stub")
    return env


def dead_pid():
    """A pid that has already finished: a run that is no longer live."""
    process = subprocess.Popen(["true"])
    process.wait()
    return process.pid


class RecoverSweepTest(unittest.TestCase):
    def test_recover_runs_the_sweep_after_the_in_flight_rows(self):
        # Crash recovery sweeps before it visits the rows' worktrees: the
        # dead run's box is stopped, and its line follows the five rows.
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            (state_dir / "ledger.tsv").write_text(ALL_STATE_ROWS)
            containers = state_dir / "beam" / "containers"
            containers.mkdir(parents=True)
            (containers / "box-9").write_text(
                "pid: %d\nhost: %s\nrun: R1\nrecord: /tmp/one.record\n"
                "created: 2026-01-01T00:00:00Z\nworst: 70.0000\n"
                % (dead_pid(), os.uname().nodename)
            )
            (Path(tmp) / "stub").mkdir()
            (Path(tmp) / "stub" / "containers.json").write_text(
                '{"box-9": "2026-01-01T00:00:00Z"}'
            )

            r = run("recover", state_dir=state_dir, env=stub_env(tmp))

            self.assertEqual(r.returncode, 0, r.stderr)
            lines = r.stdout.splitlines()
            # Five in-flight states; then the sweep's one line.
            self.assertEqual(len(lines), 6, r.stdout)
            self.assertTrue(lines[0].startswith("4\trunning\t"), lines)
            self.assertTrue(lines[4].startswith("8\tlanding\t"), lines)
            self.assertEqual(lines[5], "stopped box-9: confirmed")
            self.assertEqual(
                json.loads((Path(tmp) / "stub" / "containers.json").read_text()), {}
            )


if __name__ == "__main__":
    unittest.main()
