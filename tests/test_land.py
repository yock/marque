"""land.py's CLI against temporary git repos with a bare origin."""
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAND = REPO / "skills" / "marque" / "scripts" / "land.py"
LEDGER = REPO / "skills" / "marque" / "scripts" / "ledger.py"

ISSUE = 7
BRANCH = "orch-7"
GIST = "Add the two"
RESOLUTION_TEXT = "Finished #7: the worktree adds two.\n"


def sh(*args, cwd):
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("%s failed: %s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.strip()


def ledger(*args, state):
    return subprocess.run(
        [sys.executable, str(LEDGER), "--state-dir", str(state), *args],
        capture_output=True,
        text=True,
    )


class Landing:
    """A bare origin, a main checkout, a ticket worktree and the landing inputs."""

    def comment_cmd(self):
        return 'echo "comment $MARQUE_ISSUE $(cat "$MARQUE_RESOLUTION")" >> %s' % shlex.quote(
            str(self.calls)
        )

    def close_cmd(self):
        return 'echo "close $MARQUE_ISSUE" >> %s' % shlex.quote(str(self.calls))


def make_landing(tmp):
    l = Landing()
    l.root = Path(tmp)
    l.origin = l.root / "origin.git"
    l.repo = l.root / "repo"
    l.wt = l.root / "wt"
    l.state = l.root / "state"
    l.resolution = l.root / "resolution.md"
    l.suite = l.root / "suite.log"
    l.calls = l.root / "calls"

    sh("git", "init", "--bare", "--quiet", str(l.origin), cwd=l.root)
    sh("git", "clone", "--quiet", str(l.origin), str(l.repo), cwd=l.root)
    sh("git", "config", "user.name", "Landing Test", cwd=l.repo)
    sh("git", "config", "user.email", "landing@example.com", cwd=l.repo)
    sh("git", "checkout", "--quiet", "-b", "master", cwd=l.repo)
    (l.repo / "numbers.txt").write_text("one\n")
    sh("git", "add", "numbers.txt", cwd=l.repo)
    sh("git", "commit", "--quiet", "-m", "Start with one", cwd=l.repo)
    sh("git", "push", "--quiet", "origin", "master", cwd=l.repo)

    sh("git", "worktree", "add", "--quiet", "-b", BRANCH, str(l.wt), "master", cwd=l.repo)
    (l.wt / "numbers.txt").write_text("one\ntwo\n")
    sh("git", "commit", "--quiet", "-am", GIST, cwd=l.wt)

    # The suite log must post-date the branch tip; commit times are whole seconds,
    # so put the log a minute into the future rather than racing the clock.
    l.suite.write_text("OK 12 tests\n")
    l.tip_time = int(sh("git", "log", "-1", "--format=%ct", cwd=l.wt))
    os.utime(l.suite, (l.tip_time + 60, l.tip_time + 60))

    l.resolution.write_text(RESOLUTION_TEXT)
    l.state.mkdir()
    return l


def land(l, env=None, merge_style=None, comment_cmd=None, close_cmd=None):
    e = {k: v for k, v in os.environ.items() if k != "MARQUE_LAND_CRASH_AFTER"}
    e.update(env or {})
    cmd = [
        sys.executable,
        str(LAND),
        "direct",
        "--issue",
        str(ISSUE),
        "--branch",
        BRANCH,
        "--worktree",
        str(l.wt),
        "--target",
        "master",
        "--gist",
        GIST,
        "--state-dir",
        str(l.state),
        "--suite-green",
        str(l.suite),
        "--resolution",
        str(l.resolution),
        "--comment-cmd",
        comment_cmd if comment_cmd is not None else l.comment_cmd(),
        "--close-cmd",
        close_cmd if close_cmd is not None else l.close_cmd(),
        "--repo",
        str(l.repo),
    ]
    if merge_style is not None:
        cmd += ["--merge-style", merge_style]
    return subprocess.run(cmd, capture_output=True, text=True, env=e)


class HelpTest(unittest.TestCase):
    def test_help_and_direct_help_exit_zero(self):
        for args in (["--help"], ["direct", "--help"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(LAND), *args], capture_output=True, text=True
                )
                self.assertEqual(r.returncode, 0, r.stderr)


class HappyPathTest(unittest.TestCase):
    def test_direct_lands_the_ticket_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            r = land(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            tip = sh("git", "rev-parse", "master", cwd=l.origin)
            self.assertEqual(r.stdout, "landed #7 %s\n" % tip)

            # --no-ff: a merge commit with two parents, and the message from the brief.
            self.assertEqual(
                sh("git", "log", "-1", "--format=%s", "master", cwd=l.origin),
                "Merge #7: Add the two",
            )
            parents = sh("git", "log", "-1", "--format=%P", "master", cwd=l.origin).split()
            self.assertEqual(len(parents), 2)

            self.assertEqual(
                l.calls.read_text(),
                "comment 7 Finished #7: the worktree adds two.\nclose 7\n",
            )
            self.assertFalse(l.wt.exists())
            self.assertEqual(sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo), "")
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")
            self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), tip)
            self.assertFalse((l.state / "landing" / "7.log").exists())


def commit_elsewhere(l):
    """A commit on origin's master that the main checkout has not seen."""
    other = l.root / "other"
    sh("git", "clone", "--quiet", str(l.origin), str(other), cwd=l.root)
    sh("git", "config", "user.name", "Other", cwd=other)
    sh("git", "config", "user.email", "other@example.com", cwd=other)
    (other / "numbers.txt").write_text("one\nthree\n")
    sh("git", "commit", "--quiet", "-am", "Elsewhere", cwd=other)
    sh("git", "push", "--quiet", "origin", "master", cwd=other)


def commit_on_master(l):
    """After the branch was cut, master moves on."""
    (l.repo / "numbers.txt").write_text("one\nfour\n")
    sh("git", "commit", "--quiet", "-am", "Master moves on", cwd=l.repo)
    sh("git", "push", "--quiet", "origin", "master", cwd=l.repo)


def dirty_repo(l):
    (l.repo / "numbers.txt").write_text("one\nfive\n")


def dirty_worktree(l):
    (l.wt / "numbers.txt").write_text("one\nsix\n")


def suite_log_missing(l):
    l.suite.unlink()


def suite_log_stale(l):
    os.utime(l.suite, (l.tip_time - 60, l.tip_time - 60))


def resolution_missing(l):
    l.resolution.unlink()


class PreconditionTest(unittest.TestCase):
    def test_each_broken_precondition_stops_before_anything_changes(self):
        cases = [
            ("master behind origin", commit_elsewhere, "origin/master"),
            ("branch does not contain master", commit_on_master, "does not contain master"),
            ("dirty repo", dirty_repo, "repo has uncommitted changes"),
            ("dirty worktree", dirty_worktree, "worktree has uncommitted changes"),
            ("missing suite log", suite_log_missing, "suite log"),
            ("suite log older than the branch tip", suite_log_stale, "predates"),
            ("missing resolution file", resolution_missing, "resolution file"),
        ]
        for name, mutate, phrase in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                l = make_landing(tmp)
                mutate(l)
                origin_before = sh("git", "rev-parse", "master", cwd=l.origin)

                r = land(l)

                self.assertEqual(r.returncode, 3, r.stderr)
                self.assertIn(phrase, r.stderr)
                # Nothing changed: no ledger row, origin untouched, no tracker
                # calls, the worktree and branch still there.
                self.assertNotEqual(ledger("get", "7", state=l.state).returncode, 0)
                self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
                self.assertFalse(l.calls.exists())
                self.assertTrue(l.wt.exists())
                self.assertEqual(sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo), BRANCH)


STEPS = ["landing", "merged", "pushed", "confirmed", "commented", "closed", "cleaned"]


class CrashAndResumeTest(unittest.TestCase):
    def test_a_crash_after_any_step_resumes_without_repeating_it(self):
        for step in STEPS:
            with self.subTest(step=step), tempfile.TemporaryDirectory() as tmp:
                l = make_landing(tmp)

                r = land(l, env={"MARQUE_LAND_CRASH_AFTER": step})

                # os._exit(70): the run dies where it stood, as a power cut would.
                self.assertEqual(r.returncode, 70, r.stderr)
                self.assertEqual(
                    ledger("get", "7", "state", state=l.state).stdout.strip(), "landing"
                )

                r = land(l)

                self.assertEqual(r.returncode, 0, r.stderr)
                tip = sh("git", "rev-parse", "master", cwd=l.origin)
                self.assertEqual(r.stdout, "landed #7 %s\n" % tip)
                # Each tracker call happened exactly once, and the merge too.
                self.assertEqual(
                    l.calls.read_text(),
                    "comment 7 Finished #7: the worktree adds two.\nclose 7\n",
                )
                self.assertEqual(
                    len(sh("git", "log", "--oneline", "--grep", "Merge #7:", "master", cwd=l.origin).splitlines()),
                    1,
                )
                self.assertFalse(l.wt.exists())
                self.assertEqual(
                    sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                    "",
                )
                self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")
                self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), tip)
                self.assertFalse((l.state / "landing" / "7.log").exists())


class AlreadyLandedTest(unittest.TestCase):
    def test_a_second_run_reports_the_landing_without_touching_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            first = land(l)
            self.assertEqual(first.returncode, 0, first.stderr)
            calls = l.calls.read_text()
            tip = sh("git", "rev-parse", "master", cwd=l.origin)

            r = land(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "landed #7 %s\n" % tip)
            self.assertEqual(l.calls.read_text(), calls)


if __name__ == "__main__":
    unittest.main()
