#!/usr/bin/env python3
"""suite.py run --record FILE [--runner local|beam] [-- CMD [ARG...]]: run a suite.

`run` runs one command — or the commands in the project's `## Runner` block —
inside the git worktree that contains it, and writes a suite record: the tree
and commit it tested, the runner, when it started and ended, each command's
exit status, the verdict and the cost. It refuses a dirty worktree before
anything starts, and writes the tree down before the command runs, so the
record is evidence and not a claim made afterwards. The command's output goes
to a log beside the record.

The record is one `key: value` per line: a small file beside its log, not the
log itself.

`--runner beam` runs the command on a Beam sandbox instead, with Marque owning
the whole lifecycle: build the image, create the container, upload the exact
tree, run, tear down, account. It needs `--state-dir` and `--rate`.

Exit codes: 0 pass; 1 fail; 2 refused before starting (dirty worktree, not a
git worktree, no command, a missing Beam term), nothing written; 3 reserved for
paid compute, refused with no fallback possible.
"""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# A sandbox's TTL is the max wall time plus this margin, so the provider does
# not stop the box while the suite is still running or being torn down.
MARGIN = 600

# The only beam commands Marque may call. `beam status` is absent on purpose:
# it prints a token prefix. Every call goes through beam() below.
ALLOWED = (
    ("image", "build"),
    ("image", "get"),
    ("container", "create"),
    ("container", "cp"),
    ("container", "exec"),
    ("container", "stop"),
    ("container", "list"),
)


class Interrupted(Exception):
    """A handled signal, carried to the teardown in run_beam's finally."""

    def __init__(self, signum):
        super().__init__("interrupted by signal %d" % signum)
        self.signum = signum


class BeamError(Exception):
    """A beam step that failed; status is the exit code the run reports."""

    def __init__(self, status):
        super().__init__("beam exited %s" % status)
        self.status = status


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


def now_dt():
    """UTC now, as a datetime, for arithmetic on Beam's start times."""
    return datetime.now(timezone.utc)


def log_of(record):
    """The log beside the record: its path with the suffix replaced by .log."""
    path = Path(record)
    if not path.suffix:
        return path.with_name(path.name + ".log")
    return path.with_suffix(".log")


def write_lines(f, lines):
    """Append the lines, then flush and fsync, so a record is on disk as written."""
    for line in lines:
        f.write(line + "\n")
    f.flush()
    os.fsync(f.fileno())


def status_of(returncode):
    """A command killed by a signal reports the shell's 128 + signum."""
    return 128 - returncode if returncode < 0 else returncode


def read_runner_block(worktree):
    """The project's `## Runner` block as a dict, or {} when there is none.

    `<worktree>/docs/agents/marque.md` holds one `key: value` per line.
    `commands:` starts a list of `- ` items; blank lines and code fences are
    ignored; the block ends at the next `## ` heading or at end of file.
    """
    path = Path(worktree) / "docs" / "agents" / "marque.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    block = {}
    inside = False
    in_commands = False
    for line in lines:
        if not inside:
            if line.strip() == "## Runner":
                inside = True
            continue
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        if stripped == "commands:":
            block["commands"] = []
            in_commands = True
            continue
        if in_commands and stripped.startswith("- "):
            block["commands"].append(stripped[2:].strip())
            continue
        if ": " in stripped:
            key, value = stripped.split(": ", 1)
            block[key.strip()] = value.strip()
            in_commands = False
    return block


def beam(log, *args):
    """Run one allowlisted beam command, appending its output to the log.

    Anything outside ALLOWED raises: a call Marque did not design must never
    reach the provider, and no output carrying a token may go unlogged.
    """
    if tuple(args[:2]) not in ALLOWED:
        raise RuntimeError("beam %s is not allowlisted" % " ".join(args[:2]))
    cmd = ["beam"] + [str(a) for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except (FileNotFoundError, PermissionError) as e:
        log.write("suite.py: cannot start beam: %s\n" % e)
        log.flush()
        return subprocess.CompletedProcess(cmd, 127, "", str(e))
    log.write(r.stdout)
    log.write(r.stderr)
    log.flush()
    return r


def json_of(result):
    """The JSON beam printed, or None when it printed something else."""
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def ensure_image(log, dockerfile, worktree, state):
    """Build the image once per Dockerfile hash.

    `<state>/beam/images/<sha256>` caches the image ID. A cached ID is reused
    only while `beam image get` says it still exists.
    """
    digest = hashlib.sha256(Path(dockerfile).read_bytes()).hexdigest()
    cache = Path(state) / "beam" / "images" / digest
    if cache.exists():
        image_id = cache.read_text(encoding="utf-8").strip()
        if image_id:
            r = beam(log, "image", "get", image_id)
            data = json_of(r)
            if r.returncode == 0 and data and data.get("exists"):
                return image_id
    r = beam(
        log,
        "image",
        "build",
        "--dockerfile",
        str(dockerfile),
        "--context-dir",
        str(worktree),
        "--format",
        "json",
    )
    data = json_of(r)
    if r.returncode != 0 or not data or not data.get("success"):
        raise BeamError(status_of(r.returncode) or 1)
    image_id = data["image_id"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(image_id + "\n", encoding="utf-8")
    return image_id


def write_container(state, container_id, record):
    """Record the container the moment it exists, so an orphan can be found."""
    directory = Path(state) / "beam" / "containers"
    directory.mkdir(parents=True, exist_ok=True)
    with open(str(directory / container_id), "w") as f:
        write_lines(
            f,
            [
                "pid: %d" % os.getpid(),
                "record: %s" % Path(record).resolve(),
                "created: %s" % now(),
            ],
        )


def upload(log, worktree, tree, container_id, max_wall):
    """Upload the exact tree and extract it at /work in the sandbox."""
    scratch = Path(tempfile.mkdtemp(prefix="marque-beam-"))
    try:
        tar = scratch / "tree.tar"
        git(worktree, "archive", "--format=tar", "-o", str(tar), tree)
        r = beam(
            log,
            "container",
            "cp",
            str(tar),
            "%s:/tmp/marque-tree.tar" % container_id,
        )
        if r.returncode != 0:
            raise BeamError(status_of(r.returncode))
        r = beam(
            log,
            "container",
            "exec",
            "--timeout",
            max_wall,
            container_id,
            "--",
            "sh",
            "-c",
            "mkdir -p /work && tar -xf /tmp/marque-tree.tar -C /work",
        )
        if r.returncode != 0:
            raise BeamError(status_of(r.returncode))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def started_at_of(log, container_id):
    """When the box started, from `container list`; create does not print it."""
    r = beam(log, "container", "list", "--format", "json")
    data = json_of(r)
    if r.returncode != 0 or not isinstance(data, list):
        return None
    for entry in data:
        if entry.get("container_id") == container_id:
            value = entry.get("started_at")
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return None
    return None


def stop_container(log, container_id):
    """Stop the box and confirm it is gone; return (confirmed, stop time)."""
    beam(log, "container", "stop", container_id)
    for attempt in range(5):
        r = beam(log, "container", "list", "--format", "json")
        data = json_of(r)
        live = (
            [entry.get("container_id") for entry in data]
            if isinstance(data, list)
            else None
        )
        if r.returncode == 0 and live is not None and container_id not in live:
            return True, now_dt()
        if attempt < 4:
            time.sleep(2)
    return False, None


SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)

# Signals that arrived once teardown had started. The teardown has to finish,
# so they are noted rather than raised and folded into the record afterwards.
NOTED = []


def interrupted(signum, frame):
    """A signal becomes an exception, so the teardown in finally always runs."""
    raise Interrupted(signum)


def noting(signum, frame):
    """During teardown a signal is only noted; it must not abort the teardown."""
    NOTED.append(signum)


def install_handlers(handler):
    previous = {}
    for sig in SIGNALS:
        try:
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):
            pass
    return previous


def restore_handlers(previous):
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def run_local(record, cwd, tree, commit, command):
    """One argv command, run in the worktree; the record #41 wrote."""
    log = log_of(record)
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
        try:
            status = status_of(
                subprocess.run(
                    command, cwd=str(cwd), stdout=out, stderr=subprocess.STDOUT
                ).returncode
            )
        except (FileNotFoundError, PermissionError) as e:
            out.write("suite.py: cannot start %s: %s\n" % (command[0], e))
            status = 127
    verdict = "pass" if status == 0 else "fail"
    with open(str(record), "a") as f:
        write_lines(
            f,
            [
                "ended: %s" % now(),
                "exit.1: %d" % status,
                "verdict: %s" % verdict,
                "cost: 0",
                "log: %s" % log.resolve(),
            ],
        )
    return 0 if verdict == "pass" else 1


def run_local_commands(record, cwd, tree, commit, commands):
    """The `## Runner` block's commands, each with `sh -c`, every one running."""
    log = log_of(record)
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
    statuses = []
    with open(str(log), "w") as out:
        for command in commands:
            try:
                statuses.append(
                    status_of(
                        subprocess.run(
                            ["sh", "-c", command],
                            cwd=str(cwd),
                            stdout=out,
                            stderr=subprocess.STDOUT,
                        ).returncode
                    )
                )
            except (FileNotFoundError, PermissionError) as e:
                out.write("suite.py: cannot start sh: %s\n" % e)
                statuses.append(127)
    verdict = "pass" if all(status == 0 for status in statuses) else "fail"
    with open(str(record), "a") as f:
        write_lines(
            f,
            ["ended: %s" % now()]
            + ["exit.%d: %d" % (i + 1, s) for i, s in enumerate(statuses)]
            + ["verdict: %s" % verdict, "cost: 0", "log: %s" % log.resolve()],
        )
    return 0 if verdict == "pass" else 1


def run_beam(record, worktree, tree, commit, block, max_wall, rate, state, text):
    """One command on a Beam sandbox, torn down on every exit path."""
    record = Path(record)
    log = log_of(record)
    state = Path(state)
    record.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    ttl = max_wall + MARGIN
    container_id = None
    started_at = None
    looked_up = False
    confirmed = None
    stopped_at = None
    status = None

    with open(str(record), "w") as f:
        write_lines(
            f,
            [
                "tree: %s" % tree,
                "commit: %s" % commit,
                "runner: beam",
                "started: %s" % now(),
            ],
        )
    NOTED.clear()
    with open(str(log), "w") as logf:
        previous = install_handlers(interrupted)
        try:
            image_id = ensure_image(
                logf, Path(worktree) / block["dockerfile"], worktree, state
            )
            # A signal between `create` returning and the ID being on disk
            # would leak a box no sweep can find. Block them across that window;
            # a pending one is delivered on unblock and the normal teardown runs.
            blocked = signal.pthread_sigmask(signal.SIG_BLOCK, SIGNALS)
            try:
                r = beam(
                    logf,
                    "container",
                    "create",
                    "--image-id",
                    image_id,
                    "--cpu",
                    block["cpu"],
                    "--memory",
                    block["memory"],
                    "--ttl",
                    ttl,
                    "--format",
                    "json",
                )
                data = json_of(r)
                if r.returncode != 0 or not data or not data.get("container_id"):
                    raise BeamError(status_of(r.returncode) or 1)
                container_id = data["container_id"]
                write_container(state, container_id, record)
                with open(str(record), "a") as f:
                    write_lines(f, ["container: %s" % container_id])
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
            upload(logf, worktree, tree, container_id, max_wall)
            r = beam(
                logf,
                "container",
                "exec",
                "--timeout",
                max_wall,
                "--cwd",
                "/work",
                container_id,
                "--",
                "sh",
                "-c",
                text,
            )
            status = status_of(r.returncode)
            started_at = started_at_of(logf, container_id)
            looked_up = True
        except Interrupted as e:
            status = 128 + e.signum
        except BeamError as e:
            status = e.status
        except OSError as e:
            logf.write("suite.py: %s\n" % e)
            logf.flush()
            status = 1
        finally:
            # From here on a signal is noted, never raised: the teardown and
            # the closing lines below have to finish.
            install_handlers(noting)
            if container_id is not None:
                if not looked_up:
                    started_at = started_at_of(logf, container_id)
                    looked_up = True
                confirmed, stopped_at = stop_container(logf, container_id)
                if confirmed:
                    Path(state, "beam", "containers", container_id).unlink(
                        missing_ok=True
                    )

    try:
        if NOTED and status in (None, 0):
            status = 128 + NOTED[0]
        if status is None:
            status = 1
        if container_id is None:
            cost = "0.0000"
        elif confirmed and started_at is not None:
            cost = "%.4f" % (rate * (stopped_at - started_at).total_seconds() / 60)
        else:
            cost = "%.4f" % (rate * ttl / 60)
        verdict = "pass" if status == 0 else "fail"
        lines = [
            "ended: %s" % now(),
            "exit.1: %d" % status,
            "verdict: %s" % verdict,
            "cost: %s" % cost,
        ]
        if container_id is not None:
            lines.append("teardown: %s" % ("confirmed" if confirmed else "unconfirmed"))
        lines.append("log: %s" % log.resolve())
        with open(str(record), "a") as f:
            write_lines(f, lines)
    finally:
        restore_handlers(previous)
    return 0 if verdict == "pass" else 1


def refuse(message):
    print("suite.py: refusing to run: %s" % message, file=sys.stderr)
    return 2


def run(a):
    """Run the suite and write the record; return the process exit code."""
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
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
        print(
            "suite.py: refusing to run: %s is not inside a git worktree: %s" % (cwd, e),
            file=sys.stderr,
        )
        return 2

    block = read_runner_block(worktree)
    from_block = not command
    commands = list(block.get("commands", []))
    if from_block and not commands:
        return refuse(
            "a command after -- is required, or `commands:` in the `## Runner` "
            "block of docs/agents/marque.md"
        )

    if a.runner == "local":
        if not from_block:
            return run_local(record, cwd, tree, commit, command)
        return run_local_commands(record, cwd, tree, commit, commands)

    if a.state_dir is None:
        return refuse("a beam run needs --state-dir")
    if a.rate is None:
        return refuse("a beam run needs --rate")
    if not block:
        return refuse("a beam run needs the `## Runner` block in docs/agents/marque.md")
    for field in ("dockerfile", "cpu", "memory"):
        if not block.get(field):
            return refuse("the `## Runner` block has no %s" % field)
    dockerfile = Path(worktree) / block["dockerfile"]
    if not dockerfile.exists():
        return refuse("the Dockerfile %s does not exist" % dockerfile)
    max_wall = a.max_wall
    if max_wall is None:
        try:
            max_wall = int(block.get("max wall time", ""))
        except ValueError:
            return refuse(
                "a beam run needs a max wall time: `max wall time` in the "
                "`## Runner` block, or --max-wall"
            )
    if from_block and len(commands) > 1:
        return refuse("several commands run in parallel parts, not yet supported")
    text = commands[0] if from_block else shlex.join(command)
    return run_beam(
        record, worktree, tree, commit, block, max_wall, a.rate, a.state_dir, text
    )


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "run",
        help="run the suite and write the suite record",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes: 0 pass, 1 fail, 2 refused before starting (dirty worktree, "
            "not a git worktree, no command, a missing Beam term), 3 reserved for "
            "paid compute"
        ),
    )
    p.add_argument("--record", required=True, metavar="FILE", help="the suite record to write")
    p.add_argument(
        "--runner",
        choices=("local", "beam"),
        default="local",
        help="where the suite runs (default: local)",
    )
    p.add_argument(
        "--state-dir", metavar="DIR", help="the state dir; required for beam"
    )
    p.add_argument(
        "--rate",
        type=float,
        metavar="PER_MINUTE",
        help="currency per wall-minute; required for beam",
    )
    p.add_argument(
        "--max-wall",
        type=int,
        metavar="SECONDS",
        help="override the `## Runner` block's max wall time",
    )
    p.add_argument("command", nargs=argparse.REMAINDER, metavar="CMD", help="the command after --")
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    if a.cmd == "run":
        return run(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
