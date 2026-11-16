"""suite.py's CLI against a temporary git repo, with the record outside it."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts" / "suite.py"
STUBS = Path(__file__).resolve().parent / "stubs"


def beam_env(tmp):
    """The env a Beam run needs: the stub first on PATH and its state dir."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("STUB_BEAM")}
    env["PATH"] = str(STUBS) + os.pathsep + env.get("PATH", "")
    env["STUB_BEAM_STATE"] = str(Path(tmp) / "stub")
    env["STUB_BEAM_ID_DIR"] = str(Path(tmp) / "state" / "beam" / "containers")
    return env


def beam_calls(tmp):
    path = Path(tmp) / "stub" / "calls.log"
    return path.read_text().splitlines() if path.exists() else []


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


BEAM_BLOCK = """## Runner

runner: beam
dockerfile: Dockerfile
cpu: 2
memory: 4096
max wall time: 3600
commands:
- make test
"""


def make_beam_repo(tmp, block=BEAM_BLOCK):
    """The make_repo repo plus a committed Dockerfile and a `## Runner` block."""
    repo, record = make_repo(tmp)
    (repo / "Dockerfile").write_text("FROM scratch\n")
    (repo / "docs" / "agents").mkdir(parents=True)
    (repo / "docs" / "agents" / "marque.md").write_text(block)
    sh("git", "add", "-A", cwd=repo)
    sh("git", "commit", "--quiet", "-m", "Add the Beam runner block", cwd=repo)
    return repo, record


TWO_PART_BLOCK = """## Runner

runner: beam
dockerfile: Dockerfile
cpu: 2
memory: 4096
boxes: %d
max wall time: 3600
commands:
- make part-one
- make part-two
"""


def two_part_block(boxes):
    """ping's model case: two halves of one suite, each with its own box."""
    return TWO_PART_BLOCK % boxes


def run_suite(repo, record, command):
    return subprocess.run(
        [sys.executable, str(SUITE), "run", "--record", str(record), "--", *command],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def run_beam(repo, record, tmp, *args, command=None, env=None):
    """Run a Beam suite; callers pass the flags they want to exercise."""
    cmd = [sys.executable, str(SUITE), "run", "--record", str(record), *args]
    if command:
        cmd += ["--", *command]
    return subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=beam_env(tmp) if env is None else env,
    )


def record_lines(record):
    return record.read_text().splitlines()


def record_values(record):
    return dict(line.split(": ", 1) for line in record_lines(record))


class HelpTest(unittest.TestCase):
    def test_help_and_run_help_exit_zero(self):
        for args in (["--help"], ["run", "--help"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(SUITE), *args], capture_output=True, text=True
                )
                self.assertEqual(r.returncode, 0, r.stderr)


class StdlibOnlyTest(unittest.TestCase):
    def test_the_script_runs_without_site_packages(self):
        # -I isolates from the environment and -S drops site-packages: the
        # script must still start, so it imports nothing but the stdlib.
        r = subprocess.run(
            [sys.executable, "-I", "-S", str(SUITE), "--help"],
            capture_output=True,
            text=True,
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


class DirtyWorktreeTest(unittest.TestCase):
    def test_a_dirty_worktree_is_refused_and_nothing_is_written(self):
        cases = {
            "modified": lambda repo: (repo / "file.txt").write_text("one\ntwo\n"),
            "untracked": lambda repo: (repo / "new.txt").write_text("new\n"),
        }
        for kind, dirty in cases.items():
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, record = make_repo(tmp)
                    marker = Path(tmp) / "ran"
                    dirty(repo)
                    r = run_suite(
                        repo, record, ["sh", "-c", 'touch "$1"', "sh", str(marker)]
                    )
                    self.assertEqual(r.returncode, 2, r.stderr)
                    self.assertFalse(record.exists())
                    self.assertFalse(marker.exists())


class NoCommandTest(unittest.TestCase):
    def test_no_command_after_the_separator_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_repo(tmp)
            r = subprocess.run(
                [sys.executable, str(SUITE), "run", "--record", str(record)],
                cwd=str(repo),
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("--", r.stderr)
            self.assertFalse(record.exists())


class BeamStubAllowlistTest(unittest.TestCase):
    def test_a_command_outside_the_allowlist_exits_99_and_is_logged(self):
        # The seven allowed pairs are `image build|get` and `container
        # create|cp|exec|stop|list`; `beam status` prints a token prefix and
        # must never run (ticket #44).
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [str(STUBS / "beam"), "status"],
                capture_output=True,
                text=True,
                env=beam_env(tmp),
            )
            self.assertEqual(r.returncode, 99, r.stderr)
            violations = [line for line in beam_calls(tmp) if line.startswith("VIOLATION")]
            self.assertEqual(len(violations), 1, beam_calls(tmp))
            self.assertIn("status", violations[0])


def beam_ok(repo, record, tmp, *args, env=None):
    state = str(Path(tmp) / "state")
    return run_beam(
        repo,
        record,
        tmp,
        "--runner", "beam",
        "--state-dir", state,
        "--rate", "1.0",
        *args,
        env=env,
    )


class BeamRefusalTest(unittest.TestCase):
    def test_a_beam_run_missing_a_required_term_is_refused_before_anything(self):
        cases = {
            "no rate": (BEAM_BLOCK, ["--state-dir", "{state}"], "--rate"),
            "no state dir": (BEAM_BLOCK, ["--rate", "1.0"], "--state-dir"),
            "no max wall time": (
                BEAM_BLOCK.replace("max wall time: 3600\n", ""),
                ["--state-dir", "{state}", "--rate", "1.0"],
                "max wall time",
            ),
            "boxes not a positive integer": (
                BEAM_BLOCK.replace(
                    "max wall time: 3600\n", "boxes: none\nmax wall time: 3600\n"
                ),
                ["--state-dir", "{state}", "--rate", "1.0"],
                "positive integer",
            ),
            "missing dockerfile": (
                BEAM_BLOCK.replace("Dockerfile", "tools/missing.Dockerfile"),
                ["--state-dir", "{state}", "--rate", "1.0"],
                "does not exist",
            ),
        }
        for name, (block, flags, marker) in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, record = make_beam_repo(tmp, block)
                    args = [a.replace("{state}", str(Path(tmp) / "state")) for a in flags]
                    r = run_beam(repo, record, tmp, "--runner", "beam", *args)
                    self.assertEqual(r.returncode, 2, r.stderr)
                    self.assertIn(marker, r.stderr)
                    self.assertFalse(record.exists())
                    self.assertEqual(beam_calls(tmp), [])


class BeamCase(unittest.TestCase):
    """A Beam repo, its state dir and the stub's call log."""

    BLOCK = BEAM_BLOCK

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.repo, self.record = make_beam_repo(self.tmp, self.BLOCK)
        self.state = Path(self.tmp) / "state"

    def run_it(self, *args, **kwargs):
        return beam_ok(self.repo, self.record, self.tmp, *args, **kwargs)

    def calls(self):
        return beam_calls(self.tmp)

    def assert_no_violations(self):
        # The stub logs a VIOLATION for anything outside the allowlist, for a
        # create without --ttl, for an exec without --timeout and for an upload
        # of a container the state dir does not hold.
        violations = [line for line in self.calls() if "VIOLATION" in line]
        self.assertEqual(violations, [], self.calls())


def live_containers(tmp):
    path = Path(tmp) / "stub" / "containers.json"
    return json.loads(path.read_text()) if path.exists() else {}


class BeamSandboxTest(BeamCase):
    def test_every_create_passes_a_ttl_of_max_wall_plus_600_seconds(self):
        # The block's 3600 s plus the agreed 600 s margin: 4200.
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        creates = [call for call in self.calls() if call.startswith("container create")]
        self.assertEqual(len(creates), 1, self.calls())
        self.assertIn("--ttl 4200", creates[0])
        self.assert_no_violations()

    def test_every_exec_carries_the_max_wall_time_as_its_timeout(self):
        # The CLI's default is 300 s, which would kill a suite; every exec,
        # the extraction included, names the block's 3600 s.
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        execs = [call for call in self.calls() if call.startswith("container exec")]
        self.assertGreaterEqual(len(execs), 2, self.calls())
        for call in execs:
            with self.subTest(call=call):
                self.assertIn("--timeout 3600", call)
        self.assert_no_violations()

    def test_the_container_is_recorded_in_the_state_dir_before_the_upload(self):
        # The stub fails the upload when `<state>/beam/containers/<id>` is
        # missing, so a clean run is the proof; a confirmed stop clears it.
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_no_violations()
        self.assertEqual(list((self.state / "beam" / "containers").iterdir()), [])

    def test_a_normal_exit_stops_the_box_and_confirms_it_gone(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        stop = calls.index("container stop box-1")
        self.assertTrue(
            any(call.startswith("container list") for call in calls[stop + 1:]),
            calls,
        )
        self.assertEqual(live_containers(self.tmp), {})
        self.assertIn("teardown.1: confirmed", record_lines(self.record))
        self.assert_no_violations()

    def test_the_beam_record_names_the_runner_the_container_the_cost_and_teardown(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = record_lines(self.record)
        self.assertEqual(
            [line.split(": ", 1)[0] for line in lines],
            [
                "tree", "commit", "runner", "started", "container.1",
                "ended", "exit.1", "verdict", "cost", "teardown.1", "log",
            ],
        )
        values = record_values(self.record)
        self.assertEqual(values["runner"], "beam")
        self.assertEqual(values["container.1"], "box-1")
        self.assertRegex(values["cost"], r"^\d+\.\d{4}$")
        self.assertEqual(values["teardown.1"], "confirmed")
        self.assert_no_violations()


class BeamParallelPartsTest(BeamCase):
    """A block's commands are parts, each on its own sandbox."""

    BLOCK = two_part_block(2)

    def test_two_commands_run_on_two_sandboxes_at_once_and_both_pass(self):
        # The stub sleeps 2 s in every command exec, so the run can only end
        # in that time if both boxes are live together (boxes: 2).
        env = beam_env(self.tmp)
        env["STUB_BEAM_EXEC_SLEEP"] = "2"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        creates = [i for i, call in enumerate(calls) if call.startswith("container create")]
        stops = [i for i, call in enumerate(calls) if call.startswith("container stop")]
        self.assertEqual(len(creates), 2, calls)
        self.assertEqual(len(stops), 2, calls)
        for create in creates:
            self.assertLess(create, stops[0], calls)
        values = record_values(self.record)
        self.assertEqual(
            sorted([values["container.1"], values["container.2"]]), ["box-1", "box-2"]
        )
        self.assertEqual(values["exit.1"], "0")
        self.assertEqual(values["exit.2"], "0")
        self.assertEqual(values["verdict"], "pass")
        self.assertEqual(values["teardown.1"], "confirmed")
        self.assertEqual(values["teardown.2"], "confirmed")
        self.assertEqual(live_containers(self.tmp), {})
        self.assertEqual(list((self.state / "beam" / "containers").iterdir()), [])
        keys = [line.split(": ", 1)[0] for line in record_lines(self.record)]
        self.assertEqual(keys[:4], ["tree", "commit", "runner", "started"])
        self.assertEqual(sorted(keys[4:6]), ["container.1", "container.2"])
        self.assertEqual(
            keys[6:],
            ["ended", "exit.1", "exit.2", "verdict", "cost", "teardown.1",
             "teardown.2", "log"],
        )
        self.assert_no_violations()

    def test_a_failing_part_fails_the_verdict_and_the_others_still_pass(self):
        # The stub fails only execs whose text contains the match, with the
        # STUB_BEAM_EXEC_STATUS it was given; 5 is that part's exit status.
        env = beam_env(self.tmp)
        env["STUB_BEAM_FAIL_MATCH"] = "part-two"
        env["STUB_BEAM_EXEC_STATUS"] = "5"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 1, r.stderr)
        values = record_values(self.record)
        self.assertEqual(values["exit.1"], "0")
        self.assertEqual(values["exit.2"], "5")
        self.assertEqual(values["verdict"], "fail")
        self.assertEqual(values["teardown.1"], "confirmed")
        self.assertEqual(values["teardown.2"], "confirmed")
        self.assertEqual(live_containers(self.tmp), {})
        self.assert_no_violations()

    def test_cost_is_summed_over_the_boxes(self):
        # The stub ages every box 600 s = 10 wall-minutes; at 1.0 per minute
        # two boxes cost 20.0000 plus the couple of seconds the run takes. A
        # worst-case charge per box would be 2 x 4200/60 = 140.0000.
        env = beam_env(self.tmp)
        env["STUB_BEAM_STARTED_AGO"] = "600"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        cost = float(record_values(self.record)["cost"])
        self.assertGreaterEqual(cost, 20.0000)
        self.assertLessEqual(cost, 22.0000)
        self.assert_no_violations()


class BeamSerialPartsTest(BeamCase):
    """`boxes: 1` runs the parts one after the other."""

    BLOCK = two_part_block(1)

    def test_boxes_one_runs_the_parts_one_after_the_other(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        creates = [i for i, call in enumerate(calls) if call.startswith("container create")]
        stops = [i for i, call in enumerate(calls) if call.startswith("container stop")]
        self.assertEqual(len(creates), 2, calls)
        self.assertEqual(len(stops), 2, calls)
        self.assertLess(stops[0], creates[1], calls)
        self.assertEqual(record_values(self.record)["verdict"], "pass")
        self.assert_no_violations()


class BeamImageCacheTest(BeamCase):
    def test_the_image_is_built_once_per_dockerfile_hash_and_reused(self):
        for _ in range(2):
            r = self.run_it()
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            len([c for c in self.calls() if c.startswith("image build")]), 1
        )
        (self.repo / "Dockerfile").write_text("FROM scratch\n# v2\n")
        sh("git", "commit", "-am", "Change the Dockerfile", cwd=self.repo)
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            len([c for c in self.calls() if c.startswith("image build")]), 2
        )
        self.assert_no_violations()


class BeamLogTest(BeamCase):
    def test_a_second_run_at_the_same_record_path_truncates_the_log(self):
        # #41 fixed the log to be truncated at the start of a run; the stub
        # prints one `stub ran:` line per run command, so a reused path must
        # hold exactly one.
        for _ in range(2):
            r = self.run_it()
            self.assertEqual(r.returncode, 0, r.stderr)
        log = Path(str(self.record.with_suffix(".log")))
        self.assertEqual(log.read_text().count("stub ran:"), 1)


class BeamFailureTest(BeamCase):
    def test_a_failing_command_is_a_failed_run_that_still_tears_down(self):
        # `exit 7` from the stub stands for a failing build: the remote status
        # is the run's status, and the box is still stopped and confirmed.
        env = beam_env(self.tmp)
        env["STUB_BEAM_EXEC_STATUS"] = "7"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 1, r.stderr)
        values = record_values(self.record)
        self.assertEqual(values["exit.1"], "7")
        self.assertEqual(values["verdict"], "fail")
        self.assertEqual(values["teardown.1"], "confirmed")
        self.assertIn("container stop box-1", self.calls())
        self.assertEqual(live_containers(self.tmp), {})
        self.assert_no_violations()


class BeamSignalTest(unittest.TestCase):
    def test_teardown_runs_and_is_confirmed_on_sigterm_and_sighup(self):
        # POSIX: a process signalled with N reports 128 + N, so SIGTERM (15)
        # records 143 and SIGHUP (1) records 129.
        for sig, code in ((signal.SIGTERM, 143), (signal.SIGHUP, 129)):
            with self.subTest(signal=sig):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, record = make_beam_repo(tmp)
                    env = beam_env(tmp)
                    env["STUB_BEAM_EXEC_SLEEP"] = "30"
                    p = subprocess.Popen(
                        [
                            sys.executable, str(SUITE), "run",
                            "--record", str(record),
                            "--runner", "beam",
                            "--state-dir", str(Path(tmp) / "state"),
                            "--rate", "1.0",
                        ],
                        cwd=str(repo),
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    try:
                        deadline = time.time() + 20
                        while time.time() < deadline:
                            if any(
                                call.startswith("container exec") and "make test" in call
                                for call in beam_calls(tmp)
                            ):
                                break
                            time.sleep(0.1)
                        else:
                            self.fail("the suite never reached the run command")
                        p.send_signal(sig)
                        p.communicate(timeout=30)
                    finally:
                        if p.poll() is None:
                            p.kill()
                            p.communicate()
                    self.assertEqual(p.returncode, 1)
                    self.assertIn("container stop box-1", beam_calls(tmp))
                    self.assertEqual(live_containers(tmp), {})
                    values = record_values(record)
                    self.assertEqual(values["exit.1"], str(code))
                    self.assertEqual(values["verdict"], "fail")
                    self.assertEqual(values["teardown.1"], "confirmed")


class BeamCostTest(BeamCase):
    def test_cost_is_settled_from_the_containers_started_at(self):
        # The stub ages the box 600 s = 10 wall-minutes; at 1.0 per minute the
        # run costs 10.0000 plus the couple of seconds the run takes. The
        # 4200 s worst case would be 70.0000.
        env = beam_env(self.tmp)
        env["STUB_BEAM_STARTED_AGO"] = "600"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        cost = float(record_values(self.record)["cost"])
        self.assertGreaterEqual(cost, 10.0000)
        self.assertLessEqual(cost, 11.0000)
        self.assert_no_violations()

    def test_an_unconfirmed_teardown_charges_the_whole_ttl_and_keeps_the_id(self):
        # 1.0 per minute for the full 4200 s TTL: 70.0000. The ID file stays
        # for the sweep to find.
        env = beam_env(self.tmp)
        env["STUB_BEAM_STOP_IGNORED"] = "1"
        r = self.run_it(env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        values = record_values(self.record)
        self.assertEqual(values["teardown.1"], "unconfirmed")
        self.assertEqual(values["cost"], "70.0000")
        self.assertEqual(
            [p.name for p in (self.state / "beam" / "containers").iterdir()],
            ["box-1"],
        )
        self.assert_no_violations()


class BeamMaxWallTest(BeamCase):
    def test_max_wall_overrides_the_blocks_max_wall_time(self):
        # --max-wall 60 plus the 600 s margin gives a 660 s TTL, and 60 s for
        # every exec timeout.
        r = self.run_it("--max-wall", "60")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        creates = [call for call in calls if call.startswith("container create")]
        self.assertIn("--ttl 660", creates[0])
        for call in calls:
            if call.startswith("container exec"):
                with self.subTest(call=call):
                    self.assertIn("--timeout 60", call)
        self.assert_no_violations()


class BeamTeardownSignalTest(unittest.TestCase):
    def test_a_signal_during_teardown_still_finishes_it_and_writes_the_record(self):
        # The first SIGTERM interrupts the run; the second lands while the
        # stub's `container stop` is still working. Teardown must finish, and
        # the closing lines must still be written. 143 is POSIX 128 + SIGTERM.
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_beam_repo(tmp)
            env = beam_env(tmp)
            env["STUB_BEAM_EXEC_SLEEP"] = "30"
            env["STUB_BEAM_STOP_SLEEP"] = "3"
            p = subprocess.Popen(
                [
                    sys.executable, str(SUITE), "run",
                    "--record", str(record),
                    "--runner", "beam",
                    "--state-dir", str(Path(tmp) / "state"),
                    "--rate", "1.0",
                ],
                cwd=str(repo),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.wait_for(
                    lambda: any(
                        call.startswith("container exec") and "make test" in call
                        for call in beam_calls(tmp)
                    ),
                    "the suite never reached the run command",
                )
                p.send_signal(signal.SIGTERM)
                self.wait_for(
                    lambda: "container stop box-1" in beam_calls(tmp),
                    "the suite never reached the teardown",
                )
                p.send_signal(signal.SIGTERM)
                p.communicate(timeout=60)
            finally:
                if p.poll() is None:
                    p.kill()
                    p.communicate()
            self.assertEqual(p.returncode, 1)
            self.assertEqual(live_containers(tmp), {})
            values = record_values(record)
            self.assertEqual(values["exit.1"], "143")
            self.assertEqual(values["verdict"], "fail")
            self.assertEqual(values["teardown.1"], "confirmed")
            self.assertIn("log", values)

    @staticmethod
    def wait_for(condition, message, seconds=20):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if condition():
                return
            time.sleep(0.1)
        raise AssertionError(message)


class LocalBlockCommandsTest(unittest.TestCase):
    def test_the_blocks_commands_run_locally_in_order_and_all_of_them_run(self):
        # POSIX: `true` exits 0 and `false` exits 1. A later failure must not
        # stop the commands after it: the record carries each exit status.
        block = "## Runner\n\ncommands:\n- true\n- false\n"
        with tempfile.TemporaryDirectory() as tmp:
            repo, record = make_beam_repo(tmp, block)
            r = subprocess.run(
                [sys.executable, str(SUITE), "run", "--record", str(record)],
                cwd=str(repo),
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, r.stderr)
            lines = record_lines(record)
            self.assertIn("exit.1: 0", lines)
            self.assertIn("exit.2: 1", lines)
            self.assertIn("verdict: fail", lines)
