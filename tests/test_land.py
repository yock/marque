"""land.py's CLI against temporary git repos with a bare origin."""
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts"
LAND = SCRIPTS / "land.py"
LEDGER = SCRIPTS / "ledger.py"
SUITE = SCRIPTS / "suite.py"

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


def write_record(path, **keys):
    """A suite record: one `key: value` per line, in the order given."""
    path.write_text("".join("%s: %s\n" % item for item in keys.items()))


def make_landing(tmp):
    l = Landing()
    l.root = Path(tmp)
    l.origin = l.root / "origin.git"
    l.repo = l.root / "repo"
    l.wt = l.root / "wt"
    l.state = l.root / "state"
    l.resolution = l.root / "resolution.md"
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

    l.resolution.write_text(RESOLUTION_TEXT)
    l.state.mkdir()
    # The integration run's record, under the state dir's logs/, naming the branch's tree.
    l.tree = sh("git", "rev-parse", "%s^{tree}" % BRANCH, cwd=l.repo)
    l.record = l.state / "logs" / "full-suite-7.record"
    l.record.parent.mkdir()
    write_record(
        l.record,
        tree=l.tree,
        commit=sh("git", "rev-parse", BRANCH, cwd=l.repo),
        runner="local",
        started="2026-01-01T00:00:00Z",
        ended="2026-01-01T00:01:00Z",
        **{"exit.1": "0"},
        verdict="pass",
        cost="0",
    )
    return l


def direct_args(l, comment_cmd=None, close_cmd=None, merge_style=None, suite_flag="--suite-record"):
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
        suite_flag,
        str(l.record),
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
    return cmd


def land(l, env=None, merge_style=None, comment_cmd=None, close_cmd=None):
    e = {k: v for k, v in os.environ.items() if k != "MARQUE_LAND_CRASH_AFTER"}
    e.update(env or {})
    cmd = direct_args(l, comment_cmd=comment_cmd, close_cmd=close_cmd, merge_style=merge_style)
    return subprocess.run(cmd, capture_output=True, text=True, env=e)


class HelpTest(unittest.TestCase):
    def test_help_and_direct_help_exit_zero(self):
        for args in (["--help"], ["direct", "--help"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(LAND), *args], capture_output=True, text=True
                )
                self.assertEqual(r.returncode, 0, r.stderr)


class SuiteRecordFlagTest(unittest.TestCase):
    def test_the_old_suite_green_flag_is_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)

            r = subprocess.run(
                direct_args(l, suite_flag="--suite-green"),
                capture_output=True,
                text=True,
                env=landing_env(),
            )
            self.assertEqual(r.returncode, 2, r.stderr)

            r = subprocess.run(
                [sys.executable, str(LAND), "direct", "--help"],
                capture_output=True,
                text=True,
            )
            self.assertNotIn("suite-green", r.stdout)


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
            # The merge put on the target exactly the tree the record tested.
            self.assertEqual(sh("git", "rev-parse", "master^{tree}", cwd=l.origin), l.tree)


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


def suite_record_missing(l):
    l.record.unlink()


def suite_record_for_another_tree(l):
    write_record(
        l.record,
        tree=sh("git", "rev-parse", "master^{tree}", cwd=l.repo),
        verdict="pass",
    )


def suite_record_failed(l):
    write_record(l.record, tree=l.tree, verdict="fail")


def suite_record_interrupted(l):
    # suite.py writes the opening keys before the command runs, so a record from
    # an interrupted run has no verdict line at all.
    write_record(l.record, tree=l.tree, runner="local")


def suite_record_outside_logs(l):
    outside = l.state / "full-suite-7.record"
    outside.write_text(l.record.read_text())
    l.record = outside


def resolution_missing(l):
    l.resolution.unlink()


class PreconditionTest(unittest.TestCase):
    def test_each_broken_precondition_stops_before_anything_changes(self):
        cases = [
            ("master behind origin", commit_elsewhere, "origin/master"),
            ("branch does not contain master", commit_on_master, "does not contain master"),
            ("dirty repo", dirty_repo, "repo has uncommitted changes"),
            ("dirty worktree", dirty_worktree, "worktree has uncommitted changes"),
            ("missing suite record", suite_record_missing, "suite record"),
            (
                "record for another tree",
                suite_record_for_another_tree,
                "is not orch-7's tree",
            ),
            (
                "record with a failing verdict",
                suite_record_failed,
                "verdict 'fail', not pass",
            ),
            (
                "record with no verdict",
                suite_record_interrupted,
                "verdict None, not pass",
            ),
            (
                "record outside the logs directory",
                suite_record_outside_logs,
                "is not an integration record under",
            ),
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


STEPS = ["landing", "merged", "verified", "pushed", "confirmed", "commented", "closed", "cleaned"]


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
                # Clean-up comes last: until it has run, the worktree and branch stay.
                if step != "cleaned":
                    self.assertTrue(l.wt.exists())
                    self.assertEqual(
                        sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                        BRANCH,
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


class FailingStepTest(unittest.TestCase):
    def test_a_failed_tracker_step_stops_the_landing_and_a_re_run_finishes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)

            r = land(l, close_cmd="exit 1")

            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landing")
            # The comment went out once and the close step stopped the landing;
            # the worktree is still there for the re-run.
            self.assertEqual(l.calls.read_text(), "comment 7 Finished #7: the worktree adds two.\n")
            self.assertTrue(l.wt.exists())
            self.assertEqual(
                sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                BRANCH,
            )

            r = land(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(
                l.calls.read_text(),
                "comment 7 Finished #7: the worktree adds two.\nclose 7\n",
            )
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")


class SquashTest(unittest.TestCase):
    def test_squash_style_lands_one_commit_on_the_branch_tip_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)

            r = land(l, merge_style="squash")

            self.assertEqual(r.returncode, 0, r.stderr)
            tip = sh("git", "rev-parse", "master", cwd=l.origin)
            self.assertEqual(r.stdout, "landed #7 %s\n" % tip)
            self.assertEqual(
                sh("git", "log", "-1", "--format=%s", "master", cwd=l.origin),
                "Merge #7: Add the two",
            )
            # One parent: the branch's work landed as a single commit on master.
            self.assertEqual(len(sh("git", "log", "-1", "--format=%P", "master", cwd=l.origin).split()), 1)
            self.assertEqual(sh("git", "show", "master:numbers.txt", cwd=l.origin), "one\ntwo")
            # The squash put on the target exactly the tree the record tested.
            self.assertEqual(sh("git", "rev-parse", "master^{tree}", cwd=l.origin), l.tree)
            self.assertFalse(l.wt.exists())
            self.assertEqual(
                sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                "",
            )
            self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), tip)


class NoForcePushTest(unittest.TestCase):
    def test_a_rejected_push_is_a_failed_step_not_a_forced_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            r = land(l, env={"MARQUE_LAND_CRASH_AFTER": "merged"})
            self.assertEqual(r.returncode, 70, r.stderr)
            commit_elsewhere(l)
            other_tip = sh("git", "rev-parse", "master", cwd=l.origin)

            r = land(l)

            self.assertEqual(r.returncode, 1, r.stderr)
            # The push was rejected; origin still has the other clone's commit.
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), other_tip)
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landing")
            self.assertFalse(l.calls.exists())


def commit_on_target(l):
    """A commit on the repo's local target, on top of the merge the crash left."""
    (l.repo / "numbers.txt").write_text("one\nseven\n")
    sh("git", "commit", "--quiet", "-am", "After the merge", cwd=l.repo)


class VerifiedTreeTest(unittest.TestCase):
    def test_a_target_that_moved_after_the_merge_stops_before_the_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            r = land(l, env={"MARQUE_LAND_CRASH_AFTER": "merged"})
            self.assertEqual(r.returncode, 70, r.stderr)
            commit_on_target(l)
            target_tree = sh("git", "rev-parse", "master^{tree}", cwd=l.repo)
            origin_before = sh("git", "rev-parse", "master", cwd=l.origin)

            r = land(l)

            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(
                "the target's tree %s is not the tested tree %s" % (target_tree, l.tree),
                r.stderr,
            )
            # Nothing was pushed and the ticket was not touched.
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
            self.assertFalse(l.calls.exists())
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landing")
            self.assertNotIn("verified", (l.state / "landing" / "7.log").read_text())

    def test_a_resume_after_the_tree_check_checks_the_tree_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            r = land(l, env={"MARQUE_LAND_CRASH_AFTER": "verified"})
            self.assertEqual(r.returncode, 70, r.stderr)
            origin_before = sh("git", "rev-parse", "master", cwd=l.origin)
            commit_on_target(l)
            target_tree = sh("git", "rev-parse", "master^{tree}", cwd=l.repo)

            r = land(l)

            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(
                "the target's tree %s is not the tested tree %s" % (target_tree, l.tree),
                r.stderr,
            )
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
            self.assertFalse(l.calls.exists())


class RealSuiteRecordTest(unittest.TestCase):
    def test_a_record_written_by_the_suite_wrapper_lands(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            l.record.unlink()

            r = subprocess.run(
                [sys.executable, str(SUITE), "run", "--record", str(l.record), "--", "true"],
                cwd=str(l.wt),
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)

            r = land(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")


# --- pr mode: check and finish ---------------------------------------------


def landing_env(extra=None):
    e = {k: v for k, v in os.environ.items() if k != "MARQUE_LAND_CRASH_AFTER"}
    e.update(extra or {})
    return e


def check(l, await_approval=False, env=None):
    cmd = [
        sys.executable,
        str(LAND),
        "check",
        "--issue",
        str(ISSUE),
        "--branch",
        BRANCH,
        "--worktree",
        str(l.wt),
        "--target",
        "master",
        "--state-dir",
        str(l.state),
        "--suite-record",
        str(l.record),
        "--resolution",
        str(l.resolution),
        "--repo",
        str(l.repo),
    ]
    if await_approval:
        cmd.append("--await-approval")
    return subprocess.run(cmd, capture_output=True, text=True, env=landing_env(env))


def branch_tip(l):
    return sh("git", "rev-parse", BRANCH, cwd=l.repo)


def finish(l, is_closed_cmd=None, merge_commit=None, merge_style=None, env=None):
    cmd = [
        sys.executable,
        str(LAND),
        "finish",
        "--issue",
        str(ISSUE),
        "--branch",
        BRANCH,
        "--worktree",
        str(l.wt),
        "--target",
        "master",
        "--state-dir",
        str(l.state),
        "--suite-record",
        str(l.record),
        "--resolution",
        str(l.resolution),
        "--comment-cmd",
        l.comment_cmd(),
        "--close-cmd",
        l.close_cmd(),
        "--repo",
        str(l.repo),
    ]
    if is_closed_cmd is not None:
        cmd += ["--is-closed-cmd", is_closed_cmd]
    if merge_commit is not None:
        cmd += ["--merge-commit", merge_commit]
    if merge_style is not None:
        cmd += ["--merge-style", merge_style]
    return subprocess.run(cmd, capture_output=True, text=True, env=landing_env(env))


def merge_pr(l, squash=False):
    """The developer merges the PR on origin from a third clone; return the hash."""
    other = l.root / "merger"
    sh("git", "clone", "--quiet", str(l.origin), str(other), cwd=l.root)
    sh("git", "config", "user.name", "Merger", cwd=other)
    sh("git", "config", "user.email", "merger@example.com", cwd=other)
    if squash:
        sh("git", "merge", "--squash", "origin/%s" % BRANCH, cwd=other)
        sh("git", "commit", "--quiet", "-m", "Merge pull request #1", cwd=other)
    else:
        sh(
            "git",
            "merge",
            "--no-ff",
            "--quiet",
            "-m",
            "Merge pull request #1",
            "origin/%s" % BRANCH,
            cwd=other,
        )
    sh("git", "push", "--quiet", "origin", "master", cwd=other)
    return sh("git", "rev-parse", "HEAD", cwd=other)


class CheckTest(unittest.TestCase):
    def test_check_pushes_the_branch_and_holds_the_ticket_for_landing(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            origin_before = sh("git", "rev-parse", "master", cwd=l.origin)
            local_before = sh("git", "rev-parse", "master", cwd=l.repo)
            tip = branch_tip(l)

            r = check(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "pushed #7 %s\n" % tip)
            # The branch is on origin at its local tip; nothing was merged, so
            # master is untouched both on origin and in the main checkout.
            self.assertEqual(sh("git", "ls-remote", "--heads", "origin", BRANCH, cwd=l.repo).split()[0], tip)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.repo), local_before)
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landing")

    def test_await_approval_leaves_the_ticket_waiting_on_the_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)

            r = check(l, await_approval=True)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(
                ledger("get", "7", "state", state=l.state).stdout.strip(), "awaiting-approval"
            )

    def test_a_broken_precondition_stops_before_the_branch_is_pushed(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            dirty_worktree(l)

            r = check(l)

            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("worktree has uncommitted changes", r.stderr)
            self.assertEqual(sh("git", "ls-remote", "--heads", "origin", BRANCH, cwd=l.repo), "")
            self.assertNotEqual(ledger("get", "7", state=l.state).returncode, 0)

    def test_a_bad_record_stops_before_the_branch_is_pushed(self):
        cases = [
            ("record for another tree", suite_record_for_another_tree, "is not orch-7's tree"),
            ("record with a failing verdict", suite_record_failed, "verdict 'fail', not pass"),
        ]
        for name, mutate, phrase in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                l = make_landing(tmp)
                mutate(l)

                r = check(l)

                self.assertEqual(r.returncode, 3, r.stderr)
                self.assertIn(phrase, r.stderr)
                self.assertEqual(sh("git", "ls-remote", "--heads", "origin", BRANCH, cwd=l.repo), "")
                self.assertNotEqual(ledger("get", "7", state=l.state).returncode, 0)

    def test_check_and_finish_help_exit_zero(self):
        for args in (["check", "--help"], ["finish", "--help"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(LAND), *args], capture_output=True, text=True
                )
                self.assertEqual(r.returncode, 0, r.stderr)


class FinishBeforeMergeTest(unittest.TestCase):
    def test_finish_before_the_pr_is_merged_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l, await_approval=True).returncode, 0)
            origin_before = sh("git", "rev-parse", "master", cwd=l.origin)

            r = finish(l)

            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("the PR for #7 is not merged on origin/master", r.stderr)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
            self.assertEqual(
                ledger("get", "7", "state", state=l.state).stdout.strip(), "awaiting-approval"
            )
            self.assertFalse((l.state / "landing" / "7.finish.log").exists())
            self.assertTrue(l.wt.exists())
            self.assertFalse(l.calls.exists())


class FinishWithoutRecordTest(unittest.TestCase):
    def test_finish_without_its_suite_record_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l, await_approval=True).returncode, 0)
            merge_pr(l)
            l.record.unlink()

            r = finish(l)

            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("the suite record %s is missing" % l.record, r.stderr)
            # Nothing changed: the ledger still waits, there is no journal, the
            # ticket was not touched and the worktree is still there.
            self.assertEqual(
                ledger("get", "7", "state", state=l.state).stdout.strip(), "awaiting-approval"
            )
            self.assertFalse((l.state / "landing" / "7.finish.log").exists())
            self.assertFalse(l.calls.exists())
            self.assertTrue(l.wt.exists())


class FinishAfterMergeTest(unittest.TestCase):
    def test_finish_confirms_the_merge_then_closes_comments_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l, await_approval=True).returncode, 0)
            merged = merge_pr(l)

            r = finish(l, is_closed_cmd="exit 1")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "landed #7 %s\n" % merged)
            # The main checkout fast-forwards to the merge commit on origin.
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.repo), merged)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), merged)
            # Close first, then the resolution comment.
            self.assertEqual(
                l.calls.read_text(),
                "close 7\ncomment 7 Finished #7: the worktree adds two.\n",
            )
            self.assertFalse(l.wt.exists())
            self.assertEqual(
                sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                "",
            )
            # awaiting-approval was cleared on the way to landed.
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")
            self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), merged)
            self.assertFalse((l.state / "landing" / "7.finish.log").exists())


class AlreadyClosedTest(unittest.TestCase):
    def test_a_ticket_the_tracker_already_closed_gets_only_the_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l).returncode, 0)
            merge_pr(l)

            r = finish(l, is_closed_cmd="exit 0")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(l.calls.read_text(), "comment 7 Finished #7: the worktree adds two.\n")


class SquashFinishTest(unittest.TestCase):
    def test_a_squash_merge_without_the_merge_commit_stops_before_anything_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l).returncode, 0)
            merge_pr(l, squash=True)
            origin_before = sh("git", "rev-parse", "master", cwd=l.origin)

            r = finish(l, merge_style="squash")

            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("a squash-merged PR needs --merge-commit", r.stderr)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.origin), origin_before)
            self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landing")
            self.assertFalse((l.state / "landing" / "7.finish.log").exists())
            self.assertFalse(l.calls.exists())

    def test_a_squash_merge_lands_at_the_given_merge_commit_and_deletes_the_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l).returncode, 0)
            squashed = merge_pr(l, squash=True)

            r = finish(l, merge_style="squash", merge_commit=squashed)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "landed #7 %s\n" % squashed)
            self.assertEqual(sh("git", "rev-parse", "master", cwd=l.repo), squashed)
            self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), squashed)
            self.assertFalse(l.wt.exists())
            self.assertEqual(
                sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                "",
            )


FINISH_STEPS = ["confirmed", "synced", "closed", "commented", "cleaned"]


class FinishCrashAndResumeTest(unittest.TestCase):
    def test_a_crash_after_any_finish_step_resumes_without_repeating_it(self):
        for step in FINISH_STEPS:
            with self.subTest(step=step), tempfile.TemporaryDirectory() as tmp:
                l = make_landing(tmp)
                self.assertEqual(check(l).returncode, 0)
                merged = merge_pr(l)

                r = finish(l, env={"MARQUE_LAND_CRASH_AFTER": step})

                self.assertEqual(r.returncode, 70, r.stderr)
                self.assertEqual(
                    ledger("get", "7", "state", state=l.state).stdout.strip(), "landing"
                )

                r = finish(l)

                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout, "landed #7 %s\n" % merged)
                # Each tracker call happened exactly once.
                self.assertEqual(
                    l.calls.read_text(),
                    "close 7\ncomment 7 Finished #7: the worktree adds two.\n",
                )
                self.assertEqual(sh("git", "rev-parse", "master", cwd=l.repo), merged)
                self.assertFalse(l.wt.exists())
                self.assertEqual(
                    sh("git", "branch", "--list", "--format=%(refname:short)", BRANCH, cwd=l.repo),
                    "",
                )
                self.assertEqual(ledger("get", "7", "state", state=l.state).stdout.strip(), "landed")
                self.assertEqual(ledger("get", "7", "landed", state=l.state).stdout.strip(), merged)
                self.assertFalse((l.state / "landing" / "7.finish.log").exists())


class FinishAlreadyLandedTest(unittest.TestCase):
    def test_check_and_finish_on_a_landed_ticket_only_report_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            l = make_landing(tmp)
            self.assertEqual(check(l).returncode, 0)
            merged = merge_pr(l)
            self.assertEqual(finish(l).returncode, 0)
            calls = l.calls.read_text()

            r = check(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "landed #7 %s\n" % merged)

            r = finish(l)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "landed #7 %s\n" % merged)
            self.assertEqual(l.calls.read_text(), calls)


if __name__ == "__main__":
    unittest.main()
