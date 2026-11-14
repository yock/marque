#!/usr/bin/env python3
"""land.py: land one finished ticket as a guarded unit, in either landing mode.

`direct` merges the ticket branch into the target branch and pushes it, confirms
the merge on the remote, posts the resolution comment and closes the ticket
through the command lines the orchestrator passes in, then removes the worktree
and the branch. The tracker steps are command lines, so the script stays
tracker-neutral: their environment carries MARQUE_ISSUE and MARQUE_RESOLUTION.

`check` runs those same preconditions, pushes the ticket branch and nothing else,
and marks the ticket `landing` (or `awaiting-approval`). The orchestrator then
opens the pull request and has it merged. `finish` confirms that merge on the
remote, fast-forwards the target, closes the ticket if it is still open, posts the
resolution comment and cleans up.

Each finished step goes on the journal (DIR/landing/<N>.log for direct,
DIR/landing/<N>.finish.log for finish) before the next one starts, so a run that
dies part-way is finished by re-running the same command; no step happens twice.
The ledger says `landing` from before the merge until every step, clean-up
included, is done, and then `landed` with the merge commit.

Exit codes: 0 landed (or already landed); 3 a precondition failed and nothing
changed; 1 a step failed mid-landing.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


class StepError(Exception):
    """A step of the landing failed, so the landing stops and can be resumed."""


class GitError(StepError):
    """A git command exited non-zero."""


def crash(step):
    # Test hook, for the crash-and-resume tests only: die the moment a step is on
    # the journal, with nothing unwound, the way a power cut would. Not advertised.
    if os.environ.get("MARQUE_LAND_CRASH_AFTER") == step:
        os._exit(70)


class Journal:
    """The landing's completed steps, one line each, fsynced as they happen."""

    def __init__(self, path):
        self.path = path
        self.done = {}
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    step, _, value = line.partition(" ")
                    self.done[step] = value

    def has(self, step):
        return step in self.done

    def get(self, step):
        return self.done[step]

    def record(self, step, value=""):
        with open(str(self.path), "a") as f:
            f.write((step + " " + value) if value else step)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        self.done[step] = value


def git(repo, *args):
    """Run git in repo; return its stdout with the trailing newline dropped."""
    cmd = ["git", "-C", str(repo)] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout).strip()
        raise GitError(detail or "%s exited %d" % (" ".join(cmd), r.returncode))
    return r.stdout.strip()


def is_ancestor(repo, older, newer):
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", str(older), str(newer)],
        capture_output=True,
    ).returncode == 0


def ledger(state_dir, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "ledger.py"), "--state-dir", str(state_dir)]
        + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def ledger_field(state_dir, issue, field):
    r = ledger(state_dir, "get", issue, field)
    return r.stdout.strip() if r.returncode == 0 else None


def set_ledger(state_dir, issue, state, landed=None):
    args = ["set", issue, state] + (["--landed", landed] if landed else [])
    r = ledger(state_dir, *args)
    if r.returncode != 0:
        raise StepError(
            "ledger.py could not record %s for #%s: %s" % (state, issue, r.stderr.strip())
        )


def merge_message(a):
    return "Merge #%s: %s" % (a.issue, a.gist)


def do_merge(a):
    """Merge the branch into the target; return the merge commit's hash."""
    msg = merge_message(a)
    if a.merge_style == "squash":
        git(a.repo, "merge", "--squash", a.branch)
        git(a.repo, "commit", "-m", msg)
    else:
        git(a.repo, "merge", "--no-ff", "-m", msg, a.branch)
    return git(a.repo, "rev-parse", "HEAD")


def run_tracker(a, cmd):
    env = dict(os.environ)
    env["MARQUE_ISSUE"] = str(a.issue)
    env["MARQUE_RESOLUTION"] = str(a.resolution)
    r = subprocess.run(cmd, shell=True, cwd=str(a.repo), env=env)
    if r.returncode != 0:
        raise StepError("the tracker command %r exited %d" % (cmd, r.returncode))


def clean_up(a):
    wt = a.worktree
    if wt.exists():
        if git(wt, "status", "--porcelain"):
            raise StepError("the worktree %s has uncommitted changes; not removing it" % wt)
        git(a.repo, "worktree", "remove", "--force", str(wt))
    if git(a.repo, "branch", "--list", a.branch):
        # -D is safe only because `confirmed` proved the merge is on origin, and a
        # squash merge leaves the branch's commits unreachable from the target.
        git(a.repo, "branch", "-D" if a.merge_style == "squash" else "-d", a.branch)


def preconditions(a):
    """Every fresh-run check, as a list of failures; empty when the landing may start."""
    fails = []

    try:
        git(a.repo, "fetch", a.remote)
    except GitError as e:
        fails.append("git fetch %s failed: %s" % (a.remote, e))

    try:
        current = git(a.repo, "rev-parse", "--abbrev-ref", "HEAD")
        if current != a.target:
            fails.append("the repo is on %r, not %s" % (current, a.target))
        local = git(a.repo, "rev-parse", a.target)
        remote_tip = git(a.repo, "rev-parse", "%s/%s" % (a.remote, a.target))
        if local != remote_tip:
            fails.append(
                "the repo's %s is not at %s/%s (%s != %s)"
                % (a.target, a.remote, a.target, local[:7], remote_tip[:7])
            )
        if not is_ancestor(a.repo, a.target, a.branch):
            fails.append("%s does not contain %s" % (a.branch, a.target))
        if git(a.repo, "status", "--porcelain"):
            fails.append("the repo has uncommitted changes")
    except GitError as e:
        fails.append("cannot inspect the repo: %s" % e)

    wt = a.worktree
    if not wt.exists():
        fails.append("the worktree %s is missing" % wt)
    else:
        try:
            if git(wt, "rev-parse", "--abbrev-ref", "HEAD") != a.branch:
                fails.append("the worktree is not on %s" % a.branch)
            if git(wt, "status", "--porcelain"):
                fails.append("the worktree has uncommitted changes")
        except GitError as e:
            fails.append("cannot inspect the worktree %s: %s" % (wt, e))

    if not a.suite_green.exists():
        fails.append("the suite log %s is missing" % a.suite_green)
    elif a.suite_green.stat().st_size == 0:
        fails.append("the suite log %s is empty" % a.suite_green)
    else:
        try:
            tip_time = int(git(a.repo, "log", "-1", "--format=%ct", a.branch))
            if a.suite_green.stat().st_mtime <= tip_time:
                fails.append(
                    "the suite log %s predates the branch tip (%s was committed later)"
                    % (a.suite_green, a.branch)
                )
        except GitError as e:
            fails.append("cannot read the time of %s's tip: %s" % (a.branch, e))

    # Safeguard 3: the resolution comment is settled before anything changes.
    if not a.resolution.exists():
        fails.append("the resolution file %s is missing" % a.resolution)
    elif a.resolution.stat().st_size == 0:
        fails.append("the resolution file %s is empty" % a.resolution)

    return fails


def repo_on_target_clean(a):
    """The repo is on the target branch with nothing uncommitted; failures otherwise."""
    fails = []
    try:
        current = git(a.repo, "rev-parse", "--abbrev-ref", "HEAD")
        if current != a.target:
            fails.append("the repo is on %r, not %s" % (current, a.target))
        if git(a.repo, "status", "--porcelain"):
            fails.append("the repo has uncommitted changes")
    except GitError as e:
        fails.append("cannot inspect the repo: %s" % e)
    return fails


def resume_preconditions(a):
    """The only checks a resume makes: after `merged`, the target differs from origin by design."""
    return repo_on_target_clean(a)


def already_merged(a):
    """The merge may have happened just before a crash, with no journal line yet."""
    if a.merge_style == "squash":
        return git(a.repo, "log", "-1", "--format=%B", a.target).strip() == merge_message(a)
    return is_ancestor(a.repo, a.branch, a.target)


def run_steps(a, journal):
    """Run every step not yet in the journal, in order; return the exit code."""
    issue = str(a.issue)
    try:
        if not journal.has("merged"):
            if already_merged(a):
                hash_ = git(a.repo, "rev-parse", a.target)
            else:
                hash_ = do_merge(a)
            journal.record("merged", hash_)
            crash("merged")
        hash_ = journal.get("merged")
        if not journal.has("pushed"):
            # A plain push: never --force, never a forced refspec. A rejected
            # push is a failed step, and the landing stops there.
            git(a.repo, "push", a.remote, a.target)
            journal.record("pushed")
            crash("pushed")
        if not journal.has("confirmed"):
            git(a.repo, "fetch", a.remote)
            if not is_ancestor(a.repo, hash_, "%s/%s" % (a.remote, a.target)):
                raise StepError("the merge %s is not on %s/%s after the push" % (hash_, a.remote, a.target))
            journal.record("confirmed")
            crash("confirmed")
        if not journal.has("commented"):
            run_tracker(a, a.comment_cmd)
            journal.record("commented")
            crash("commented")
        if not journal.has("closed"):
            run_tracker(a, a.close_cmd)
            journal.record("closed")
            crash("closed")
        if not journal.has("cleaned"):
            clean_up(a)
            journal.record("cleaned")
            crash("cleaned")
        # Every step is done, clean-up included: only now is the ticket landed.
        set_ledger(a.state_dir, issue, "landed", landed=hash_)
        journal.path.unlink()
    except (StepError, OSError) as e:
        print("land.py: step failed: %s" % e, file=sys.stderr)
        return 1
    print("landed #%s %s" % (issue, hash_))
    return 0


def land(a):
    """Run the landing from start to finish; return the process exit code."""
    issue = str(a.issue)
    if ledger_field(a.state_dir, issue, "state") == "landed":
        hash_ = ledger_field(a.state_dir, issue, "landed")
        print("landed #%s %s" % (issue, hash_))
        return 0
    journal_path = Path(a.state_dir) / "landing" / ("%s.log" % issue)
    if journal_path.exists():
        fails = resume_preconditions(a)
    else:
        fails = preconditions(a)
    if fails:
        for failure in fails:
            print("land.py: precondition failed: %s" % failure, file=sys.stderr)
        return 3
    if not journal_path.exists():
        try:
            set_ledger(a.state_dir, issue, "landing")
        except StepError as e:
            print("land.py: step failed: %s" % e, file=sys.stderr)
            return 1
        crash("landing")
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("")
    return run_steps(a, Journal(journal_path))


def check(a):
    """Push the ticket branch, and hold the ticket for the PR; nothing merges."""
    issue = str(a.issue)
    if ledger_field(a.state_dir, issue, "state") == "landed":
        hash_ = ledger_field(a.state_dir, issue, "landed")
        print("landed #%s %s" % (issue, hash_))
        return 0
    fails = preconditions(a)
    if fails:
        for failure in fails:
            print("land.py: precondition failed: %s" % failure, file=sys.stderr)
        return 3
    try:
        # A plain push, never forced. It is idempotent, so a re-run after a crash
        # is safe; check keeps no journal.
        git(a.repo, "push", a.remote, a.branch)
        set_ledger(
            a.state_dir,
            issue,
            "awaiting-approval" if a.await_approval else "landing",
        )
    except (StepError, OSError) as e:
        print("land.py: step failed: %s" % e, file=sys.stderr)
        return 1
    print("pushed #%s %s" % (issue, git(a.repo, "rev-parse", a.branch)))
    return 0


def add_pr_common(p):
    p.add_argument("--issue", required=True, metavar="N", help="the ticket's number")
    p.add_argument("--branch", required=True, metavar="B", help="the ticket's branch")
    p.add_argument("--worktree", required=True, metavar="PATH", help="the ticket's worktree")
    p.add_argument("--target", required=True, metavar="T", help="the branch the PR merges into")
    p.add_argument("--state-dir", required=True, metavar="DIR", help="where the ledger lives")
    p.add_argument("--resolution", required=True, metavar="FILE", help="the resolution comment")
    p.add_argument("--remote", default="origin", metavar="NAME")
    p.add_argument("--repo", default=".", metavar="PATH", help="the main checkout, with T checked out")


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "direct",
        help="merge, push, comment, close and clean up in one guarded run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exit codes: 0 landed, 3 a precondition failed, 1 a step failed mid-landing",
    )
    p.add_argument("--issue", required=True, metavar="N", help="the ticket's number")
    p.add_argument("--branch", required=True, metavar="B", help="the ticket's branch")
    p.add_argument("--worktree", required=True, metavar="PATH", help="the ticket's worktree")
    p.add_argument("--target", required=True, metavar="T", help="the branch to land into")
    p.add_argument("--gist", required=True, metavar="TEXT", help="the merge message's summary")
    p.add_argument("--state-dir", required=True, metavar="DIR", help="where the ledger lives")
    p.add_argument("--suite-green", required=True, metavar="LOG", help="the green suite's log")
    p.add_argument("--resolution", required=True, metavar="FILE", help="the resolution comment")
    p.add_argument("--comment-cmd", required=True, metavar="CMD", help="posts the resolution comment")
    p.add_argument("--close-cmd", required=True, metavar="CMD", help="closes the ticket")
    p.add_argument("--merge-style", choices=["no-ff", "squash"], default="no-ff")
    p.add_argument("--remote", default="origin", metavar="NAME")
    p.add_argument("--repo", default=".", metavar="PATH", help="the main checkout, with T checked out")

    p = sub.add_parser(
        "check",
        help="push the ticket branch and hold the ticket for the pull request",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exit codes: 0 pushed, 3 a precondition failed, 1 a step failed",
    )
    add_pr_common(p)
    p.add_argument("--suite-green", required=True, metavar="LOG", help="the green suite's log")
    p.add_argument(
        "--await-approval",
        action="store_true",
        help="the developer approves the PR; the ledger says awaiting-approval",
    )
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    for name in ("repo", "worktree", "resolution", "suite_green"):
        if getattr(a, name, None):
            setattr(a, name, Path(getattr(a, name)).resolve())
    if a.cmd == "direct":
        return land(a)
    if a.cmd == "check":
        return check(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
