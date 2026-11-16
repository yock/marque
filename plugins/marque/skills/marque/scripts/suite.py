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

`--runner beam` runs the command — or each of the block's commands, one
sandbox each — on Beam instead, with Marque owning the whole lifecycle:
build the image, create the containers, upload the exact tree, run, tear
down, account. It needs `--state-dir`, `--rate` and `--cap`, and takes
`--concurrency`, the account's limit on live sandboxes: a run without a free
slot waits. Every paid run reserves its worst case against `--cap` first and
settles it at teardown.

Exit codes: 0 pass; 1 fail; 2 refused before starting (dirty worktree, not a
git worktree, no command, a missing Beam term), nothing written; 3 paid
compute refused when the block says `local fallback: no`.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
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


class RunLog:
    """The run's one log, shared by every part without their output interleaving.

    A worker tags itself with the part it is running; each chunk beam() prints
    is written under the log's lock with that part's prefix.
    """

    def __init__(self, handle):
        self._handle = handle
        self._lock = threading.Lock()
        self._local = threading.local()

    def for_part(self, part):
        """Tag this thread's output with the part it belongs to; None to clear."""
        self._local.part = part

    def write(self, chunk):
        if not chunk:
            return
        part = getattr(self._local, "part", None)
        with self._lock:
            if part is None:
                self._handle.write(chunk)
            else:
                self._handle.write("[part %d] %s" % (part, chunk))
            self._handle.flush()

    def flush(self):
        with self._lock:
            self._handle.flush()


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


def cached_image(log, dockerfile, state):
    """The cached image ID while the cache file and `image get` still name it.

    None means the image has to be built. `image get` is free and allowlisted,
    so a run can ask before it reserves anything.
    """
    digest = hashlib.sha256(Path(dockerfile).read_bytes()).hexdigest()
    cache = Path(state) / "beam" / "images" / digest
    if not cache.exists():
        return None
    image_id = cache.read_text(encoding="utf-8").strip()
    if not image_id:
        return None
    r = beam(log, "image", "get", image_id)
    data = json_of(r)
    if r.returncode == 0 and data and data.get("exists"):
        return image_id
    return None


def build_image(log, dockerfile, worktree, state):
    """Build the image from the Dockerfile and cache its ID by the file's hash."""
    digest = hashlib.sha256(Path(dockerfile).read_bytes()).hexdigest()
    cache = Path(state) / "beam" / "images" / digest
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


class Discard:
    """A log that goes nowhere: the pre-check runs before the record or log exist."""

    def write(self, chunk):
        pass

    def flush(self):
        pass


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


# The commission's ledger: one row per paid run's reservation and settlement.
# It is append-only under a file lock, so runs sharing a state dir share the
# cap without trusting each other's read-modify-write.
LEDGER_HEADER = "time\tkind\trun\tamount\tnote"


def new_run_id():
    """A run id unique across processes: the time, this pid and some randomness."""
    return "%s-%d-%s" % (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        os.getpid(),
        os.urandom(4).hex(),
    )


@contextlib.contextmanager
def ledger_lock(state):
    """The ledger's exclusive lock, blocking and held across a read and its append."""
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True)
    handle = open(str(state / "spend.lock"), "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def ledger_rows(state):
    """The ledger's rows as dicts; a malformed line is skipped, never fatal."""
    try:
        text = (Path(state) / "spend.tsv").read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines()[1:]:
        fields = line.split("\t")
        if len(fields) != 5:
            continue
        try:
            amount = float(fields[3])
        except ValueError:
            continue
        rows.append(
            {
                "time": fields[0],
                "kind": fields[1],
                "run": fields[2],
                "amount": amount,
                "note": fields[4],
            }
        )
    return rows


def spend_so_far(rows):
    """Each run's last settle if it has one, else its reserve, summed."""
    reserved = {}
    settled = {}
    for row in rows:
        if row["kind"] == "reserve":
            reserved[row["run"]] = row["amount"]
        elif row["kind"] == "settle":
            settled[row["run"]] = row["amount"]
    total = 0.0
    for run, amount in reserved.items():
        total += settled.get(run, amount)
    for run, amount in settled.items():
        if run not in reserved:
            total += amount
    return total


def append_ledger(state, kind, entries):
    """Append one row per (run id, amount, note); caller holds the lock."""
    path = Path(state) / "spend.tsv"
    empty = not path.exists() or path.stat().st_size == 0
    stamp = now()
    with open(str(path), "a", encoding="utf-8") as f:
        if empty:
            f.write(LEDGER_HEADER + "\n")
        for run_id, amount, note in entries:
            note = note.replace("\t", " ").replace("\n", " ")
            f.write("%s\t%s\t%s\t%.4f\t%s\n" % (stamp, kind, run_id, amount, note))
        f.flush()
        os.fsync(f.fileno())


def reserve(state, entries, cap):
    """Reserve each entry's worst case, or return why the cap refuses them."""
    with ledger_lock(state):
        spent = spend_so_far(ledger_rows(state))
        wanted = sum(amount for _, amount, _ in entries)
        if spent + wanted > cap:
            return "cap: spend %.4f + reservation %.4f > cap %.4f" % (
                spent,
                wanted,
                cap,
            )
        append_ledger(state, "reserve", entries)
    return None


def settle(state, run_id, amount, note):
    """Replace a run's reservation with what it actually spent."""
    with ledger_lock(state):
        append_ledger(state, "settle", [(run_id, amount, note)])


class Slots:
    """The account's limit on live sandboxes, held as locked files.

    One slot is one live box, from just before `container create` until its
    teardown ends. A run without a free slot waits; it is never refused. A
    process that dies releases its locks, so nothing has to reclaim them.
    """

    def __init__(self, directory, count):
        self.directory = Path(directory)
        self.count = count

    def take(self, stop):
        """Hold a free slot and return it, or None if `stop` was set first."""
        self.directory.mkdir(parents=True, exist_ok=True)
        while not stop.is_set():
            for index in range(self.count):
                handle = open(str(self.directory / str(index)), "a+")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    handle.close()
                    continue
                return handle
            stop.wait(1)
        return None

    @staticmethod
    def release(handle):
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


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


def run_local(record, cwd, tree, commit, command, refused=None):
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
            ]
            + (["refused: %s" % refused] if refused else [])
            + ["started: %s" % now()],
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


def run_local_commands(record, cwd, tree, commit, commands, refused=None):
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
            ]
            + (["refused: %s" % refused] if refused else [])
            + ["started: %s" % now()],
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


def run_beam(
    record,
    worktree,
    tree,
    commit,
    block,
    max_wall,
    rate,
    state,
    commands,
    boxes,
    concurrency,
    run_id,
    image_id,
):
    """The run's commands, each on its own sandbox, torn down on every exit path.

    One part per command, numbered in command order. A pool of workers pulls
    parts, and each worker owns its box from `container create` to the
    teardown: the main thread only steps in on a signal. `boxes` caps how many
    parts are live at once; the rest start as earlier ones finish, and each box
    holds one of the account's `concurrency` slots while it is live.
    """
    record = Path(record)
    log_path = log_of(record)
    state = Path(state)
    record.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ttl = max_wall + MARGIN
    parts = len(commands)

    # Shared by the main thread and the workers, all of it under `registry`.
    registry = threading.Lock()
    stop = threading.Event()
    boxes_by_part = {}  # part -> container id, in creation order
    statuses = {}  # part -> exit status
    started = {}  # part -> started_at, once read
    torn_down = {}  # part -> (confirmed, stop time)
    claimed = set()  # parts whose teardown a thread has taken on
    slots = Slots(state / "beam" / "slots", concurrency)

    def set_status(part, status):
        """Store a part's status, unless the main thread took its box away."""
        with registry:
            if part in claimed:
                return
            statuses.setdefault(part, status)

    def stop_box(container_id):
        """Stop one box, confirm it gone; return (started_at, confirmed, stop time)."""
        started_at = started_at_of(log, container_id)
        confirmed, stopped_at = stop_container(log, container_id)
        if confirmed:
            Path(state, "beam", "containers", container_id).unlink(missing_ok=True)
        return started_at, confirmed, stopped_at

    def tear_down(part):
        """Stop this part's own box, unless another thread already did."""
        with registry:
            if part in claimed:
                return
            claimed.add(part)
            container_id = boxes_by_part.get(part)
        if container_id is None:
            return
        started_at, confirmed, stopped_at = stop_box(container_id)
        with registry:
            started[part] = started_at
            torn_down[part] = (confirmed, stopped_at)

    def tear_down_all():
        """On a signal: stop every box no worker has taken, before any is lost.

        The snapshot and the stops happen under `registry`, so a worker that is
        inside `container create` registers its box before this can look past it.
        """
        with registry:
            for part, container_id in boxes_by_part.items():
                if part in claimed:
                    continue
                claimed.add(part)
                started_at, confirmed, stopped_at = stop_box(container_id)
                started[part] = started_at
                torn_down[part] = (confirmed, stopped_at)

    def run_part(part):
        """One part: a slot, a sandbox, the upload, the command, the teardown."""
        text = commands[part - 1]
        slot = slots.take(stop)
        if slot is None:
            return
        log.for_part(part)
        try:
            try:
                with registry:
                    if stop.is_set():
                        return
                    r = beam(
                        log,
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
                    boxes_by_part[part] = container_id
                    write_container(state, container_id, record)
                    with open(str(record), "a") as f:
                        write_lines(f, ["container.%d: %s" % (part, container_id)])
                upload(log, worktree, tree, container_id, max_wall)
                r = beam(
                    log,
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
                set_status(part, status_of(r.returncode))
            except BeamError as e:
                set_status(part, e.status)
            except OSError as e:
                log.write("suite.py: %s\n" % e)
                set_status(part, 1)
        finally:
            tear_down(part)
            slots.release(slot)
            log.for_part(None)

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
    signum = None
    workers = []
    build_cost = 0.0
    with open(str(log_path), "w") as handle:
        log = RunLog(handle)
        previous = install_handlers(interrupted)
        try:
            if image_id is None:
                began = time.monotonic()
                try:
                    image_id = build_image(
                        log, Path(worktree) / block["dockerfile"], worktree, state
                    )
                finally:
                    # A failed build's time was spent too.
                    build_cost = rate * (time.monotonic() - began) / 60
                    settle(state, run_id + ".build", build_cost, "build")
            remaining = queue.Queue()
            for part in range(1, parts + 1):
                remaining.put(part)

            def work():
                while not stop.is_set():
                    try:
                        part = remaining.get_nowait()
                    except queue.Empty:
                        return
                    run_part(part)

            workers = [
                threading.Thread(target=work, daemon=True)
                for _ in range(max(1, min(parts, boxes)))
            ]
            for worker in workers:
                worker.start()
            while True:
                alive = [worker for worker in workers if worker.is_alive()]
                if not alive:
                    break
                alive[0].join(0.5)
        except Interrupted as e:
            # From here on a signal is noted, never raised: the teardown
            # and the closing lines have to finish.
            signum = e.signum
            install_handlers(noting)
            stop.set()
            tear_down_all()
            for worker in workers:
                worker.join(60)
        except BeamError as e:
            for part in range(1, parts + 1):
                statuses.setdefault(part, e.status)
        except OSError as e:
            log.write("suite.py: %s\n" % e)
            for part in range(1, parts + 1):
                statuses.setdefault(part, 1)

        install_handlers(noting)
        try:
            for part in range(1, parts + 1):
                statuses.setdefault(
                    part, 128 + signum if signum is not None else 1
                )
            if NOTED:
                for part in range(1, parts + 1):
                    if statuses[part] == 0:
                        statuses[part] = 128 + NOTED[0]
            verdict = (
                "pass"
                if all(statuses[part] == 0 for part in range(1, parts + 1))
                else "fail"
            )
            cost = 0.0
            for part in boxes_by_part:
                confirmed, stopped_at = torn_down.get(part, (False, None))
                started_at = started.get(part)
                if confirmed and started_at is not None:
                    cost += rate * (stopped_at - started_at).total_seconds() / 60
                else:
                    cost += rate * ttl / 60
            # The run's settlement is the boxes' cost; the build settled its
            # own row above, and the record's cost carries both.
            settle(state, run_id, cost, str(record))
            cost += build_cost
            lines = ["ended: %s" % now()]
            lines += [
                "exit.%d: %d" % (part, statuses[part])
                for part in range(1, parts + 1)
            ]
            lines += ["verdict: %s" % verdict, "cost: %.4f" % cost]
            lines += [
                "teardown.%d: %s"
                % (
                    part,
                    "confirmed"
                    if torn_down.get(part, (False, None))[0]
                    else "unconfirmed",
                )
                for part in sorted(boxes_by_part)
            ]
            lines.append("log: %s" % log_path.resolve())
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
    if a.cap is None:
        return refuse("a beam run needs --cap")
    if not block:
        return refuse("a beam run needs the `## Runner` block in docs/agents/marque.md")
    for field in ("dockerfile", "cpu", "memory"):
        if not block.get(field):
            return refuse("the `## Runner` block has no %s" % field)
    fallback = block.get("local fallback", "yes")
    if fallback not in ("yes", "no"):
        return refuse("`local fallback` in the `## Runner` block must be yes or no")
    dockerfile = Path(worktree) / block["dockerfile"]
    if not dockerfile.exists():
        return refuse("the Dockerfile %s does not exist" % dockerfile)
    boxes = 1
    if block.get("boxes") is not None:
        try:
            boxes = int(block["boxes"])
        except ValueError:
            boxes = 0
        if boxes < 1:
            return refuse("`boxes` in the `## Runner` block is not a positive integer")
    max_wall = a.max_wall
    if max_wall is None:
        try:
            max_wall = int(block.get("max wall time", ""))
        except ValueError:
            return refuse(
                "a beam run needs a max wall time: `max wall time` in the "
                "`## Runner` block, or --max-wall"
            )
    commands = commands if from_block else [shlex.join(command)]
    image_id = cached_image(Discard(), dockerfile, a.state_dir)
    run_id = new_run_id()
    entries = [
        (run_id, len(commands) * a.rate * (max_wall + MARGIN) / 60, str(record))
    ]
    if image_id is None:
        entries.append((run_id + ".build", a.rate * MARGIN / 60, "build"))
    reason = reserve(a.state_dir, entries, a.cap)
    if reason is not None:
        print("suite.py: paid compute refused: %s" % reason, file=sys.stderr)
        if fallback == "no":
            return 3
        if from_block:
            return run_local_commands(
                record, cwd, tree, commit, commands, refused=reason
            )
        return run_local(record, cwd, tree, commit, command, refused=reason)
    return run_beam(
        record,
        worktree,
        tree,
        commit,
        block,
        max_wall,
        a.rate,
        a.state_dir,
        commands,
        boxes,
        a.concurrency,
        run_id,
        image_id,
    )


def positive_int(text):
    """An argparse type for a count that must be at least 1."""
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError("expected a positive integer, got %r" % text)
    return value


def non_negative_float(text):
    """An argparse type for an amount that must not be negative."""
    try:
        value = float(text)
    except ValueError:
        value = -1.0
    if value < 0:
        raise argparse.ArgumentTypeError("expected a non-negative amount, got %r" % text)
    return value


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
            "not a git worktree, no command, a missing Beam term), 3 paid compute "
            "refused when the block says `local fallback: no`"
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
        "--cap",
        type=non_negative_float,
        metavar="AMOUNT",
        help=(
            "the commission's paid-compute cap, in the same currency as "
            "--rate; required for beam"
        ),
    )
    p.add_argument(
        "--concurrency",
        type=positive_int,
        default=1,
        metavar="N",
        help=(
            "the account's limit on live sandboxes across runs sharing the "
            "state dir; a run without a free slot waits (default: 1)"
        ),
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
