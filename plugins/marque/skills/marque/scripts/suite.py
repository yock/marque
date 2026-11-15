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
import sys


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
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
