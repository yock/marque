#!/usr/bin/env python3
"""ledger.py --state-dir DIR <command>: the queue's ledger, one row per ticket.

The ledger is DIR/ledger.tsv: a header row and then one tab-separated row per
ticket with the columns issue, state, branch, worktree, session, attempts, brief,
verdict, landed, note. It is kept by this script so it can't drift from its
schema.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FIELDS = [
    "issue",
    "state",
    "branch",
    "worktree",
    "session",
    "attempts",
    "brief",
    "verdict",
    "landed",
    "note",
]
HEADER = "\t".join(FIELDS)
IN_FLIGHT = ["running", "review", "retry", "orchestrator", "landing"]

STATES = [
    ("queued", "in the queue, not started"),
    ("exploring", "the read-only explore step is running"),
    ("briefed", "the brief is written; not dispatched yet"),
    ("running", "an implementer is working in the ticket's worktree"),
    ("review", "the orchestrator is reviewing the implementer's report and diff"),
    ("retry", "sent back to the same implementer session with review findings"),
    ("orchestrator", "the orchestrator is implementing the ticket itself (retries exhausted)"),
    ("landing", "the guarded landing is under way: merge, push, comment, close, clean-up"),
    ("awaiting-approval", "pr mode: the pull request is open, waiting for the developer's approval"),
    ("landed", "merged and closed; the `landed` column holds the merge commit"),
    ("needs-info", "questions are on the ticket, waiting for the developer"),
    ("blocked", "blocked by something outside the queue"),
    ("ready-for-human", "needs a human to implement it"),
    ("abandoned", "dropped; won't be done"),
]

EPILOG = """\
states, in order:
""" + "".join("  %-20s%s\n" % (state, meaning) for state, meaning in STATES) + """\

Crash recovery visits the in-flight states -- where a worktree, a session or a
half-done landing can be left behind. They are
running, review, retry, orchestrator, landing. awaiting-approval is not in
flight: the PR waits on the tracker, and the normal loop checks it every pass.
"""


def ledger_path(state_dir):
    return Path(state_dir) / "ledger.tsv"


def read_rows(state_dir):
    """The ledger's rows, header dropped, each padded to the 10 columns."""
    path = ledger_path(state_dir)
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    if lines and lines[0].split("\t")[0] == "issue":
        lines = lines[1:]
    rows = []
    for line in lines:
        if not line:
            continue
        row = line.split("\t")
        rows.append(row + [""] * (len(FIELDS) - len(row)))
    return rows


def write_rows(state_dir, rows):
    path = ledger_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join([HEADER] + ["\t".join(row[: len(FIELDS)]) for row in rows]) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ledger.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # Test hook, for the interruption test only: die between the write and
        # the rename, leaving the old ledger and the temp file as a kill would.
        if os.environ.get("MARQUE_LEDGER_CRASH_BEFORE_RENAME"):
            os._exit(70)
        os.replace(tmp, str(path))
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        print(f"ledger.py: cannot write {path}: {e}", file=sys.stderr)
        raise SystemExit(1)


def row_for(rows, n):
    for row in rows:
        if row[0] == str(n):
            return row
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--state-dir", required=True, metavar="DIR")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("get", help="print one ticket's row, or one field of it")
    p.add_argument("n", type=int)
    p.add_argument("field", nargs="?", choices=FIELDS)

    p = sub.add_parser("set", help="create or update one ticket's row")
    p.add_argument("n", type=int)
    p.add_argument("state")
    for field in FIELDS[2:]:
        p.add_argument("--" + field, metavar="V")

    p = sub.add_parser("list", help="print every row, optionally only one state's")
    p.add_argument("--state")

    sub.add_parser(
        "recover",
        help=(
            "print the in-flight rows crash recovery must visit, then sweep "
            "orphaned Beam sandboxes"
        ),
    )

    a = ap.parse_args()
    rows = read_rows(a.state_dir)

    if a.cmd == "get":
        row = row_for(rows, a.n)
        if row is None:
            print(f"ledger.py: no row for #{a.n}", file=sys.stderr)
            raise SystemExit(1)
        if a.field:
            print(row[FIELDS.index(a.field)])
        else:
            print("\t".join(row))
    elif a.cmd == "set":
        if a.state not in [state for state, _ in STATES]:
            allowed = ", ".join(state for state, _ in STATES)
            print(f"ledger.py: unknown state '{a.state}'; allowed: {allowed}", file=sys.stderr)
            raise SystemExit(2)
        for field in FIELDS[2:]:
            value = getattr(a, field)
            if value is not None and ("\t" in value or "\n" in value):
                print(
                    f"ledger.py: --{field} value contains a tab or newline; refusing to write",
                    file=sys.stderr,
                )
                raise SystemExit(2)
        row = row_for(rows, a.n)
        if row is None:
            row = [""] * len(FIELDS)
            row[0] = str(a.n)
            rows.append(row)
        row[1] = a.state
        for field in FIELDS[2:]:
            value = getattr(a, field)
            if value is not None:
                row[FIELDS.index(field)] = value
        write_rows(a.state_dir, rows)
    elif a.cmd == "list":
        for row in rows:
            if a.state is None or row[1] == a.state:
                print("\t".join(row))
    elif a.cmd == "recover":
        for row in rows:
            if row[1] in IN_FLIGHT:
                print("\t".join(row))
        # The rows first, in this process's buffered stdout, then the sweep as
        # its own process: an orphaned sandbox is torn down before recovery
        # visits any worktree, and an unconfirmed stop is the exit status.
        sys.stdout.flush()
        sweep = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "suite.py"),
                "sweep",
                "--state-dir",
                a.state_dir,
            ]
        )
        return sweep.returncode


if __name__ == "__main__":
    sys.exit(main())
