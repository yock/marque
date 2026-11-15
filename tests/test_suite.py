"""suite.py's CLI against a temporary git repo, with the record outside it."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts" / "suite.py"


def sh(*args, cwd):
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("%s failed: %s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.strip()


def make_repo(tmp):
    """A git repo with one committed file, and a record path outside it."""
    root = Path(tmp)
    repo = root / "repo"
    repo.mkdir()
    sh("git", "init", "--quiet", str(repo), cwd=root)
    sh("git", "config", "user.name", "Suite Test", cwd=repo)
    sh("git", "config", "user.email", "suite@example.com", cwd=repo)
    (repo / "file.txt").write_text("one\n")
    sh("git", "add", "file.txt", cwd=repo)
    sh("git", "commit", "--quiet", "-m", "Start with one", cwd=repo)
    return repo, root / "state" / "logs" / "full-suite-1.record"


def run_suite(repo, record, command):
    return subprocess.run(
        [sys.executable, str(SUITE), "run", "--record", str(record), "--", *command],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


class HelpTest(unittest.TestCase):
    def test_help_and_run_help_exit_zero(self):
        for args in (["--help"], ["run", "--help"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(SUITE), *args], capture_output=True, text=True
                )
                self.assertEqual(r.returncode, 0, r.stderr)


class TreeBeforeCommandTest(unittest.TestCase):
    def test_the_record_names_the_tree_before_the_command_runs(self):
        # The spec's point: a tree written down after the run would be a claim,
        # not a record. The command snapshots the record while it is running.
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_repo(tmp)
            snapshot = Path(tmp) / "snapshot"
            run_suite(
                repo,
                record,
                ["sh", "-c", 'cp "$1" "$2"', "sh", str(record), str(snapshot)],
            )
            tree = sh("git", "rev-parse", "HEAD^{tree}", cwd=repo)
            lines = snapshot.read_text().splitlines()
            self.assertIn("tree: %s" % tree, lines)
            self.assertIn("runner: local", lines)
            self.assertFalse([line for line in lines if line.startswith("verdict:")], lines)


class VerdictTest(unittest.TestCase):
    def test_the_verdict_follows_the_command_exit_status(self):
        # POSIX: true exits 0, false exits 1, `exit 7` exits 7.
        cases = [
            (["true"], 0, "pass", "0"),
            (["false"], 1, "fail", "1"),
            (["sh", "-c", "exit 7"], 1, "fail", "7"),
        ]
        for command, code, verdict, status in cases:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, record = make_repo(tmp)
                    r = run_suite(repo, record, command)
                    self.assertEqual(r.returncode, code, r.stderr)
                    lines = record.read_text().splitlines()
                    self.assertIn("exit.1: %s" % status, lines)
                    self.assertIn("verdict: %s" % verdict, lines)


class MissingProgramTest(unittest.TestCase):
    def test_a_missing_program_fails_with_the_shells_127(self):
        # 127 is the shell's "command not found"; suite.py reports it the same way.
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_repo(tmp)
            r = run_suite(repo, record, ["/nonexistent/program"])
            self.assertEqual(r.returncode, 1, r.stderr)
            lines = record.read_text().splitlines()
            self.assertIn("exit.1: 127", lines)
            self.assertIn("verdict: fail", lines)


class RecordFormatTest(unittest.TestCase):
    def test_the_record_has_the_documented_keys_in_order_and_a_log_beside_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_repo(tmp)
            r = run_suite(repo, record, ["sh", "-c", "echo hello-from-suite"])
            self.assertEqual(r.returncode, 0, r.stderr)
            text = record.read_text()
            lines = text.splitlines()
            self.assertTrue(text.endswith("\n"), text)
            for line in lines:
                self.assertRegex(line, r"^[a-z0-9.]+: .+$")
            self.assertEqual(
                [line.split(": ", 1)[0] for line in lines],
                ["tree", "commit", "runner", "started", "ended", "exit.1", "verdict", "cost", "log"],
            )
            values = dict(line.split(": ", 1) for line in lines)
            self.assertEqual(values["commit"], sh("git", "rev-parse", "HEAD", cwd=repo))
            self.assertEqual(values["cost"], "0")
            stamp = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$"
            self.assertRegex(values["started"], stamp)
            self.assertRegex(values["ended"], stamp)
            self.assertLessEqual(values["started"], values["ended"])
            log = Path(tmp) / "state" / "logs" / "full-suite-1.log"
            self.assertEqual(values["log"], str(log))
            self.assertIn("hello-from-suite", log.read_text())
