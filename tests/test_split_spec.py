"""split_spec.py's public behaviour, run as a subprocess against a stub `tea` on PATH.

Nothing here imports the scripts. The fixture is built from spec issues written in
each test; `tests/stubs/tea` answers the API paths, records every call and can fail
on demand. The expected files and `index.txt` are literals, worked out by hand from
the layout rules in the ticket.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "marque" / "skills" / "marque" / "scripts"
STUBS = Path(__file__).resolve().parent / "stubs"
SPLIT = SCRIPTS / "split_spec.py"
REPO_NAME = "o/r"

# Spec #18's body: an intro with two paragraphs, `## Problem`, `### Detail` (a line
# over 100 characters, two markdown hard breaks) and `###`-typed `## Notes`.
BODY = (
    "A spec about the thing.\n"
    "\n"
    "It explains the whole thing, briefly.\n"
    "## Problem\n"
    "\n"
    "The problem, in one paragraph longer than a hundred characters so that no tool "
    "may reflow it, clipped or padded: raw markdown, exactly as written.\n"
    "\n"
    "## Detail\n"
    "\n"
    "Detail on line one,  \n"
    "and detail on line two after a hard break.\n"
    "### Notes\n"
    "\n"
    "Notes live here.\n"
)

# The same body cut at each `##`/`###` line, byte for byte. Blank lines between
# sections stay with the section before them.
FILES = {
    "body-00-a-spec-about-the-thing.md":
        "A spec about the thing.\n"
        "\n"
        "It explains the whole thing, briefly.\n",
    "body-01-problem.md":
        "## Problem\n"
        "\n"
        "The problem, in one paragraph longer than a hundred characters so that no tool "
        "may reflow it, clipped or padded: raw markdown, exactly as written.\n"
        "\n",
    "body-02-detail.md":
        "## Detail\n"
        "\n"
        "Detail on line one,  \n"
        "and detail on line two after a hard break.\n",
    "body-03-notes.md":
        "### Notes\n"
        "\n"
        "Notes live here.\n",
    "c01.md": "First comment.\n",
    "c02.md": "",
}

# One line per file: name, character count of its content, first heading or first
# non-blank line clipped at 100. Counts are of the literals above: 63, 160, 76, 28,
# 15, 0.
INDEX = (
    "#18 Spec: Thing\n"
    "body-00-a-spec-about-the-thing.md\t63\tA spec about the thing.\n"
    "body-01-problem.md\t160\t## Problem\n"
    "body-02-detail.md\t76\t## Detail\n"
    "body-03-notes.md\t28\t### Notes\n"
    "c01.md\t15\tFirst comment.\n"
    "c02.md\t0\t\n"
)


class SplitSpecCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "state"
        self.log = self.dir / "tea.log"
        self.fixture_path = self.dir / "fixture.json"
        self.fixture = {}

    def spec(self, number, title, body, comments=()):
        """Add spec issue `number` and its comment bodies, oldest first (None is null)."""
        self.fixture[f"repos/{REPO_NAME}/issues/{number}"] = {
            "number": number,
            "title": title,
            "state": "open",
            "body": body,
            "labels": [],
            "assignees": [],
            "comments": len(comments),
            "repository": {"full_name": REPO_NAME},
        }
        self.fixture[f"repos/{REPO_NAME}/issues/{number}/comments"] = [
            {"body": body, "user": {"login": "dev"}} for body in comments]

    def run_split(self, *specs, fail=None):
        self.fixture_path.write_text(json.dumps(self.fixture))
        env = {k: v for k, v in os.environ.items() if not k.startswith("SYMPHONY")}
        env["PATH"] = str(STUBS) + os.pathsep + env.get("PATH", "")
        env["STUB_TEA_FIXTURE"] = str(self.fixture_path)
        env["STUB_TEA_LOG"] = str(self.log)
        if fail:
            env["STUB_TEA_FAIL"] = fail
        cmd = [sys.executable, str(SPLIT), "--backend", "gitea", "--repo", REPO_NAME,
               "--state-dir", str(self.state)]
        cmd += list(specs)
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, env=env)

    def calls(self):
        return [line.split() for line in self.log.read_text().splitlines()]


class LayoutTest(SplitSpecCase):
    def test_sections_and_comments_land_as_files_with_an_index(self):
        self.spec(18, "Spec: Thing", BODY, ["First comment.\n", None])

        r = self.run_split("18")

        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.state / "specs" / "18"
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(
            list(FILES) + ["index.txt"]))
        for name, content in FILES.items():
            with self.subTest(file=name):
                self.assertEqual((out / name).read_text(), content)
        self.assertEqual((out / "index.txt").read_text(), INDEX)
        self.assertEqual(
            r.stdout, f"#18: 4 body sections, 2 comments -> {out}\n")


class RerunTest(SplitSpecCase):
    def test_a_stale_file_from_the_previous_split_is_gone(self):
        self.spec(18, "Spec: Thing", BODY, ["First comment.\n", None])
        out = self.state / "specs" / "18"
        out.mkdir(parents=True)
        (out / "c09.md").write_text("stale\n")
        (out / "body-09-gone.md").write_text("stale\n")

        r = self.run_split("18")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((out / "c09.md").exists())
        self.assertFalse((out / "body-09-gone.md").exists())
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         sorted(list(FILES) + ["index.txt"]))


class SeveralSpecsTest(SplitSpecCase):
    def test_each_spec_named_on_the_command_line_is_split(self):
        # #19 is 2 sections (intro and Part) and 1 comment: worked out by hand.
        self.spec(18, "Spec: Thing", BODY, ["First comment.\n", None])
        self.spec(19, "Second spec", "Second body.\n## Part\n\nText.\n", ["One.\n"])

        r = self.run_split("18", "19")

        self.assertEqual(r.returncode, 0, r.stderr)
        first = self.state / "specs" / "18"
        second = self.state / "specs" / "19"
        self.assertEqual(sorted(p.name for p in first.iterdir()),
                         sorted(list(FILES) + ["index.txt"]))
        self.assertEqual(sorted(p.name for p in second.iterdir()), [
            "body-00-second-body.md", "body-01-part.md", "c01.md", "index.txt"])
        self.assertEqual(
            second.joinpath("index.txt").read_text(),
            "#19 Second spec\n"
            "body-00-second-body.md\t13\tSecond body.\n"
            "body-01-part.md\t15\t## Part\n"
            "c01.md\t5\tOne.\n")
        self.assertEqual(r.stdout, (
            f"#18: 4 body sections, 2 comments -> {first}\n"
            f"#19: 2 body sections, 1 comments -> {second}\n"))


class RawApiTest(SplitSpecCase):
    def test_reads_are_raw_and_sequential(self):
        self.spec(18, "Spec: Thing", BODY, ["First comment.\n", None])

        r = self.run_split("18")

        self.assertEqual(r.returncode, 0, r.stderr)
        lines = self.calls()
        self.assertEqual([c for c in lines if c[0] == "OVERLAP"], [])
        self.assertEqual([c[1] for c in lines if c[0] == "start"], [
            f"repos/{REPO_NAME}/issues/18",
            f"repos/{REPO_NAME}/issues/18/comments?page=1&limit=50",
        ])


class LoudFailureTest(SplitSpecCase):
    def test_a_failed_comments_call_leaves_the_previous_split_untouched(self):
        self.spec(18, "Spec: Thing", BODY, ["First comment.\n", None])
        self.assertEqual(self.run_split("18").returncode, 0)
        out = self.state / "specs" / "18"
        before = {p.name: p.read_text() for p in out.iterdir()}

        r = self.run_split("18", fail="comments")

        self.assertEqual(r.returncode, 1)
        self.assertIn("tea api", r.stderr)
        self.assertIn(f"repos/{REPO_NAME}/issues/18/comments", r.stderr)
        self.assertEqual({p.name: p.read_text() for p in out.iterdir()}, before)


class MissingSpecTest(SplitSpecCase):
    def test_a_spec_the_tracker_does_not_have_fails_loudly(self):
        r = self.run_split("99")

        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "split_spec.py: #99 not found\n")
        self.assertFalse((self.state / "specs" / "99").exists())
