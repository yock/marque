#!/usr/bin/env python3
"""suite.py run --record FILE -- CMD [ARG...]: run a suite and write its record.

`run` runs one command in the current directory, inside the git worktree that
contains it, and writes a suite record: the tree and commit it tested, the
runner, when it started and ended, each command's exit status, the verdict and
the cost. It refuses a dirty worktree before anything starts, and writes the
tree down before the command runs, so the record is evidence and not a claim
made afterwards. The command's output goes to a log beside the record.

The record is one `key: value` per line: a small file beside its log, not the
log itself.

Exit codes: 0 pass; 1 fail; 2 refused before starting (dirty worktree, not a
git worktree, no command), nothing written; 3 reserved for paid compute, refused
with no fallback possible.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def git(repo, *args):
    """Run git in repo; return its stdout with the trailing newline dropped."""
    cmd = ["git", "-C", str(repo)] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout).strip()
        raise OSError(detail or "%s exited %d" % (" ".join(cmd), r.returncode))
    return r.stdout.strip()


def now():
    """UTC, ISO 8601 to the second with a Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_of(record):
    """The log beside the record: its path with the suffix replaced by .log."""
    path = Path(record)
    return path.with_suffix(".log") if path.suffix else path.with_name(path.name + ".log")


def write_lines(f, lines):
    """Append the lines, then flush and fsync, so a record is on disk as written."""
    for line in lines:
        f.write(line + "\n")
    f.flush()
    os.fsync(f.fileno())


def status_of(returncode):
    """A command killed by a signal reports the shell's 128 + signum."""
    return 128 - returncode if returncode < 0 else returncode


def run(a):
    """Run the command and write the suite record; return the process exit code."""
    cwd = Path.cwd()
    record = Path(a.record)
    try:
        worktree = git(cwd, "rev-parse", "--show-toplevel")
        if git(cwd, "status", "--porcelain"):
            print(
                "suite.py: refusing to run: the worktree %s has uncommitted changes"
                % worktree,
                file=sys.stderr,
            )
            return 2
        tree = git(cwd, "rev-parse", "HEAD^{tree}")
        commit = git(cwd, "rev-parse", "HEAD")
    except OSError as e:
        print("suite.py: refusing to run: %s is not inside a git worktree: %s" % (cwd, e), file=sys.stderr)
        return 2

    log = log_of(record)
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    record.parent.mkdir(parents=True, exist_ok=True)
    with open(str(record), "w") as f:
        write_lines(
            f,
            [
                "tree: %s" % tree,
                "commit: %s" % commit,
                "runner: local",
                "started: %s" % now(),
            ],
        )
    with open(str(log), "w") as out:
        subprocess.run(command, cwd=str(cwd), stdout=out, stderr=subprocess.STDOUT)
    return 0


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "run",
        help="run one command and write the suite record",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes: 0 pass, 1 fail, 2 refused before starting (dirty worktree, "
            "not a git worktree, no command), 3 reserved for paid compute"
        ),
    )
    p.add_argument("--record", required=True, metavar="FILE", help="the suite record to write")
    p.add_argument("command", nargs=argparse.REMAINDER, metavar="CMD", help="the command after --")
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    if a.cmd == "run":
        return run(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
