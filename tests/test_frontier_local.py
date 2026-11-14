"""frontier.py on the local-files backend and the --tickets-json escape hatch.

Nothing here imports the scripts. One queue is written once, in neutral terms, and
converted into upstream's `.scratch/<feature>/issues/` shape, into a normalized
tickets JSON file, and into a stub `tea` fixture; the expected frontier is a literal
worked out by hand from that queue.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "marque" / "scripts"
STUBS = Path(__file__).resolve().parent / "stubs"
FRONTIER = SCRIPTS / "frontier.py"
REPO_NAME = "o/r"
FEATURE = ".scratch/feat"
LABEL = "ready-for-agent"


# The one queue, in neutral terms: the statuses are the to-tickets / wayfinder
# `Status:` values, `blocked_by` is the `Blocked by:` line's text.
#
#   01 resolved   the root, no blockers                     closed, so not queued
#   02            Blocked by 01, which is resolved          on the frontier, fan 2
#   03            Blocked by 02, which is open              blocked
#   04            Blocked by 03, which is open              blocked
#   05 claimed    claimed, so assigned to "local"           never on the frontier
#   06            Blocked by other/repo#9                    unparseable, read by hand
#
# #3 waits on #2 and #4 waits on #3, so fan(#2) = 2. Every other fan-out is 0.
QUEUE = [
    {"number": 1, "title": "Scaffold the schema", "status": "resolved",
     "blocked_by": "None (can start immediately)"},
    {"number": 2, "title": "Read the tracker", "status": LABEL, "blocked_by": "01"},
    {"number": 3, "title": "Rank the queue", "status": LABEL, "blocked_by": "02"},
    {"number": 4, "title": "Write the report", "status": LABEL, "blocked_by": "03"},
    {"number": 5, "title": "Claimed work", "status": "claimed",
     "blocked_by": "None (can start immediately)"},
    {"number": 6, "title": "Elsewhere", "status": LABEL, "blocked_by": "other/repo#9"},
]

# Worked out by hand from the queue above: #1 is closed and #5 is claimed, so the
# queue is #2, #3, #4 and #6. Only #2 has every blocker closed; #3 and #4 wait on
# the open #2 and #3; #6's blocker is a reference this backend cannot resolve, so it
# is read by hand and kept off the frontier.
EXPECTED = (
    "READ BY HAND #6: unparseable reference other/repo#9, treated as open\n"
    "queue 4  frontier 1  externally blocked 0\n"
    "#    2  fan   2  parent     -  c0  Read the tracker\n"
)


def slug(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def write_local(queue, root):
    """The queue as upstream's local shape: one to-tickets file per ticket."""
    issues = root / FEATURE / "issues"
    issues.mkdir(parents=True)
    for t in queue:
        (issues / f"{t['number']:02d}-{slug(t['title'])}.md").write_text(
            f"# {t['number']:02d}: {t['title']}\n"
            "\n"
            f"**What to build:** {t['title']}.\n"
            "\n"
            f"**Blocked by:** {t['blocked_by']}\n"
            "\n"
            f"**Status:** {t['status']}\n"
            "\n"
            "- [ ] the behaviour works\n")
    return issues


class LocalCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_frontier(self, *args, env=None, path=None):
        cmd = [sys.executable, str(FRONTIER)] + list(args)
        base = {k: v for k, v in os.environ.items()
                if not k.startswith(("SYMPHONY", "STUB_", "GH_", "GITLAB_", "MARQUE_"))}
        if path is not None:
            base["PATH"] = path
        base.update(env or {})
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, env=base)

    def run_local(self, *args, env=None, path=None):
        return self.run_frontier(
            "--backend", "local", "--repo", FEATURE, *args, env=env, path=path)


class LocalFrontierTest(LocalCase):
    def test_the_queue_gives_the_hand_worked_frontier_from_local_files(self):
        write_local(QUEUE, self.dir)

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, EXPECTED)

    def test_plain_and_bold_status_lines_both_carry_the_triage_label(self):
        issues = write_local([], self.dir)
        (issues / "01-plain.md").write_text(
            "# 01: Plain\n\n**Blocked by:** None (can start immediately)\n\n"
            "Status: ready-for-agent\n")
        (issues / "02-bold.md").write_text(
            "# 02: Bold\n\n**Blocked by:** None (can start immediately)\n\n"
            "**Status:** ready-for-agent\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[1:], [
            "#    1  fan   0  parent     -  c0  Plain",
            "#    2  fan   0  parent     -  c0  Bold",
        ])

    def test_a_bold_none_blocker_declares_nothing_and_is_not_read_by_hand(self):
        issues = write_local([], self.dir)
        (issues / "05-free.md").write_text(
            "# 05: Free\n\n**What to build:** the behaviour.\n\n"
            "**Blocked by:** None (can start immediately)\n\n"
            "**Status:** ready-for-agent\n\n- [ ] it works\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("READ BY HAND", r.stdout)
        self.assertIn("#    5  fan   0  parent     -  c0  Free", r.stdout)

    def test_a_resolved_status_frees_the_tickets_blocked_by_it(self):
        # #1 is resolved, so #2 and #3 (which waits on #2) are freed in turn; only #2
        # is on the frontier because #3 still waits on the open #2.
        issues = write_local([], self.dir)
        (issues / "01-done.md").write_text(
            "# 01: First\n\n**Blocked by:** None (can start immediately)\n\n"
            "**Status:** resolved\n")
        (issues / "02-second.md").write_text(
            "# 02: Second\n\n**Blocked by:** 01\n\n**Status:** ready-for-agent\n")
        (issues / "03-third.md").write_text(
            "# 03: Third\n\n**Blocked by:** 02\n\n**Status:** ready-for-agent\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (
            "queue 2  frontier 1  externally blocked 0\n"
            "#    2  fan   1  parent     -  c0  Second\n"))

    def test_a_title_blocker_is_reported_as_unparseable_and_blocks(self):
        issues = write_local([], self.dir)
        (issues / "01-first.md").write_text(
            "# 01: First\n\n**Blocked by:** None (can start immediately)\n\n"
            "**Status:** ready-for-agent\n")
        (issues / "02-second.md").write_text(
            "# 02: Second\n\n**Blocked by:** First\n\n**Status:** ready-for-agent\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (
            "READ BY HAND #2: unparseable reference First, treated as open\n"
            "queue 2  frontier 1  externally blocked 0\n"
            "#    1  fan   0  parent     -  c0  First\n"))

    def test_a_well_formed_blocked_by_line_is_not_also_a_body_declaration(self):
        # The to-tickets template's bold line, and the plain one, are the file's
        # native edge: neither may be read a second time as a body declaration, which
        # would report native and body blockers that disagree.
        issues = write_local([], self.dir)
        for name, number, line in (("01-first.md", "01", "First"),
                                   ("02-second.md", "02", "Second"),
                                   ("03-bold.md", "03", "Bold")):
            (issues / name).write_text(
                f"# {number}: {line}\n\n**Blocked by:** None (can start immediately)\n\n"
                "**Status:** resolved\n")
        (issues / "04-waits.md").write_text(
            "# 04: Waits on both\n\n**Blocked by:** 01, 03\n\n"
            "**Status:** ready-for-agent\n")
        (issues / "05-plain.md").write_text(
            "# 05: Plain line\n\nBlocked by: 02\n\n**Status:** ready-for-agent\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("READ BY HAND", r.stdout)
        self.assertEqual(r.stdout.splitlines()[1:], [
            "#    4  fan   0  parent     -  c0  Waits on both",
            "#    5  fan   0  parent     -  c0  Plain line",
        ])

    def test_questions_under_the_comments_heading_need_the_waiting_label(self):
        issues = write_local([], self.dir)
        (issues / "09-asked.md").write_text(
            "# 09: Asked\n\n**Blocked by:** None (can start immediately)\n\n"
            "**Status:** ready-for-agent\n\n- [ ] it works\n\n"
            "## Comments\n\nSomebody asked:\n\n### Questions\n\n- which database?\n")

        r = self.run_local()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: has questions but no needs-info label", r.stdout)
        self.assertIn("#    9  fan   0  parent     -  c1  Asked", r.stdout)


class NoTrackerCliTest(LocalCase):
    def test_the_local_backend_runs_no_tracker_cli_at_all(self):
        write_local(QUEUE, self.dir)
        marker = self.dir / "cli-was-called"
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        for name in ("tea", "gh", "glab"):
            cli = bin_dir / name
            cli.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
            cli.chmod(0o755)

        r = self.run_local(path=str(bin_dir))

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, EXPECTED)
        self.assertFalse(marker.exists(), "the local backend called a tracker CLI")


if __name__ == "__main__":
    unittest.main()
