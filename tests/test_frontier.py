"""frontier.py's public behaviour, run as a subprocess against a stub `tea` on PATH.

Nothing here imports the scripts. The fixture is built from tickets written in each
test; `tests/stubs/tea` answers the API paths, records every call and can fail on
demand.
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


class FrontierCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "tea.log"
        self.fixture_path = self.dir / "fixture.json"
        self.fixture = {}

    def issues(self, tickets, deps=None, comments=None):
        """Write the fixture from ticket dicts.

        Each ticket: number, title, state ("open"), labels, assignees, body, comments.
        `deps` maps a ticket number to the numbers of its native blockers.
        `comments` maps a ticket number to its comment bodies, oldest first.
        """
        raw = {}
        for t in tickets:
            raw[t["number"]] = {
                "number": t["number"],
                "title": t.get("title", f"ticket {t['number']}"),
                "state": t.get("state", "open"),
                "body": t.get("body", ""),
                "labels": [{"name": x} for x in t.get("labels", [])],
                "assignees": [{"login": x} for x in t.get("assignees", [])],
                "comments": t.get("comments", 0),
                "repository": {"full_name": REPO_NAME},
            }
        open_issues = [i for i in raw.values() if i["state"] == "open"]
        self.fixture[f"repos/{REPO_NAME}/issues"] = open_issues
        self.fixture[f"repos/{REPO_NAME}/issues?labels=ready-for-agent"] = [
            i for i in open_issues
            if any(lab["name"] == "ready-for-agent" for lab in i["labels"])]
        for number, issue in raw.items():
            self.fixture[f"repos/{REPO_NAME}/issues/{number}"] = issue
        for number, blockers in (deps or {}).items():
            self.fixture[f"repos/{REPO_NAME}/issues/{number}/dependencies"] = [
                raw[b] for b in blockers if b in raw]
        for number, bodies in (comments or {}).items():
            self.fixture[f"repos/{REPO_NAME}/issues/{number}/comments"] = [
                {"body": body, "user": {"login": "dev"}} for body in bodies]
        return raw

    def run_frontier(self, *args, fail=None, login=None, label=None):
        self.fixture_path.write_text(json.dumps(self.fixture))
        env = {k: v for k, v in os.environ.items() if not k.startswith("SYMPHONY")}
        env["PATH"] = str(STUBS) + os.pathsep + env.get("PATH", "")
        env["STUB_TEA_FIXTURE"] = str(self.fixture_path)
        env["STUB_TEA_LOG"] = str(self.log)
        if fail:
            env["STUB_TEA_FAIL"] = fail
        cmd = [sys.executable, str(FRONTIER), "--backend", "gitea", "--repo", REPO_NAME]
        if login:
            cmd += ["--login", login]
        if label:
            cmd += ["--label", label]
        cmd += list(args)
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, env=env)

    def calls(self):
        return [line.split() for line in self.log.read_text().splitlines()]


class FrontierTest(FrontierCase):
    def test_a_queued_ticket_with_a_closed_blocker_is_on_the_frontier(self):
        self.issues(
            [{"number": 3, "title": "done", "state": "closed"},
             {"number": 5, "title": "Ready to go", "labels": ["ready-for-agent"]}],
            deps={5: [3]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 1  frontier 1  externally blocked 0", r.stdout)
        self.assertIn("#    5  fan   0  parent     -  c0  Ready to go", r.stdout)
        self.assertNotIn("READ BY HAND", r.stdout)

    def test_hand_written_blockers_and_parent_come_from_the_body(self):
        # Native dependencies are empty: the edges are the hand-written forms.
        # #6's two blockers are closed; #7 waits on the open #9, which is not queued.
        self.issues(
            [{"number": 1, "title": "The spec"},
             {"number": 3, "state": "closed"},
             {"number": 4, "state": "closed"},
             {"number": 6, "title": "Line form", "labels": ["ready-for-agent"],
              "body": "Part of #1\n\nBlocked by: #3, #4"},
             {"number": 7, "title": "Section form", "labels": ["ready-for-agent"],
              "body": "Part of #1\n\n## Blocked by\n\n- #8\n- #9"},
             {"number": 8, "state": "closed"},
             {"number": 9, "state": "open"}],
            deps={6: [], 7: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 2  frontier 1  externally blocked 1", r.stdout)
        self.assertIn("#    6  fan   0  parent #   1  c0  Line form", r.stdout)
        self.assertNotIn("#    7  fan", r.stdout)
        self.assertIn("externally blocked: #7<-#9", r.stdout)
        self.assertNotIn("READ BY HAND", r.stdout)

    def test_a_failed_tracker_call_exits_nonzero_and_names_the_call(self):
        self.issues(
            [{"number": 5, "labels": ["ready-for-agent"]}],
            deps={5: []},
        )

        r = self.run_frontier(fail="dependencies")

        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertIn("tea api", r.stderr)
        self.assertIn("repos/o/r/issues/5/dependencies", r.stderr)

    def test_a_not_found_answer_where_a_list_belongs_is_a_failure(self):
        # No dependencies fixture for #5: the stub answers {"message": "not found"} with rc 0.
        self.issues([{"number": 5, "labels": ["ready-for-agent"]}], deps={})

        r = self.run_frontier()

        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertIn("not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
