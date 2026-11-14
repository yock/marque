"""frontier.py on GitHub and GitLab, run as a subprocess against stub `gh` / `glab`.

Nothing here imports the scripts. One queue is written once, in neutral terms, and
converted into each tracker's API shape; the expected frontier is a literal worked
out by hand from that queue.
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
LABEL = "ready-for-agent"


# The one queue, in neutral terms: one open spec (#1), a closed #3, an open #4, a
# queue of five tickets and one assigned ticket.
#
#   #6  labelled, natively blocked by the open #4      -> externally blocked
#   #7  labelled, body `Blocked by: #3`; #3 is closed  -> on the frontier
#   #8  labelled, natively parented to #1              -> on the frontier, parent 1
#   #9  labelled, body `Part of #1`                    -> on the frontier, parent 1
#   #10 labelled, assigned to dev                      -> never on the frontier
#
# Every ticket has fan-out 0: #6 is blocked, and its blocker #4 is not queued.
QUEUE = [
    {"number": 1, "title": "The spec", "state": "open", "labels": [], "assignees": [],
     "body": "", "comments": 0, "native_blockers": [], "parent": None},
    {"number": 3, "title": "Already done", "state": "closed", "labels": [], "assignees": [],
     "body": "", "comments": 0, "native_blockers": [], "parent": None},
    {"number": 4, "title": "Still open", "state": "open", "labels": [], "assignees": [],
     "body": "", "comments": 0, "native_blockers": [], "parent": None},
    {"number": 6, "title": "Native blocked", "state": "open", "labels": [LABEL],
     "assignees": [], "body": "", "comments": 0, "native_blockers": [4], "parent": None},
    {"number": 7, "title": "Body blocked", "state": "open", "labels": [LABEL],
     "assignees": [], "body": "Blocked by: #3", "comments": 0, "native_blockers": [],
     "parent": None},
    {"number": 8, "title": "Native parent child", "state": "open", "labels": [LABEL],
     "assignees": [], "body": "", "comments": 0, "native_blockers": [], "parent": 1},
    {"number": 9, "title": "Body parent child", "state": "open", "labels": [LABEL],
     "assignees": [], "body": "Part of #1", "comments": 0, "native_blockers": [],
     "parent": None},
    {"number": 10, "title": "Assigned", "state": "open", "labels": [LABEL],
     "assignees": ["dev"], "body": "", "comments": 0, "native_blockers": [], "parent": None},
]

# Worked out by hand from the queue above: #6 is off the frontier (its blocker #4 is
# open and outside the queue), #10 is assigned; #8 and #9 come before #7 because a
# parent sorts first. All fan-outs are 0.
EXPECTED = (
    "queue 5  frontier 3  externally blocked 1\n"
    "#    8  fan   0  parent #   1  c0  Native parent child\n"
    "#    9  fan   0  parent #   1  c0  Body parent child\n"
    "#    7  fan   0  parent     -  c0  Body blocked\n"
    "externally blocked: #6<-#4\n"
)


def gitea_fixture(queue):
    """The queue in `tea api` shapes. Gitea has no native parent, so `parent` is a body line."""
    raw = {}
    for t in queue:
        body = t["body"]
        if t["parent"] is not None:
            body += f"\n\nPart of #{t['parent']}"
        raw[t["number"]] = {
            "number": t["number"], "title": t["title"], "state": t["state"], "body": body,
            "labels": [{"name": x} for x in t["labels"]],
            "assignees": [{"login": x} for x in t["assignees"]],
            "comments": t["comments"],
            "repository": {"full_name": REPO_NAME},
        }
    fixture = {
        "repos/o/r/issues": [raw[n] for n in raw if raw[n]["state"] == "open"],
        f"repos/o/r/issues?labels={LABEL}": [
            raw[n] for n in raw if raw[n]["state"] == "open" and LABEL in t_labels(raw[n])],
    }
    for n, issue in raw.items():
        fixture[f"repos/o/r/issues/{n}"] = issue
        fixture[f"repos/o/r/issues/{n}/dependencies"] = [
            raw[b] for b in blocker_numbers(queue, n)]
    return fixture


def t_labels(issue):
    return [lab["name"] for lab in issue["labels"]]


def blocker_numbers(queue, n):
    for t in queue:
        if t["number"] == n:
            return t["native_blockers"]
    return []


def github_fixture(queue):
    """The queue in GitHub's API shapes, read through `gh api`."""
    raw = {}
    for t in queue:
        raw[t["number"]] = {
            "number": t["number"], "title": t["title"], "state": t["state"], "body": t["body"],
            "labels": [{"name": x} for x in t["labels"]],
            "assignees": [{"login": x} for x in t["assignees"]],
            "comments": t["comments"],
            "repository": {"full_name": REPO_NAME},
            "parent_issue_url": (
                f"https://api.github.com/repos/{REPO_NAME}/issues/{t['parent']}"
                if t["parent"] is not None else None),
        }
    fixture = {
        "repos/o/r/issues": [raw[n] for n in raw if raw[n]["state"] == "open"],
        f"repos/o/r/issues?labels={LABEL}": [
            raw[n] for n in raw if raw[n]["state"] == "open" and LABEL in t_labels(raw[n])],
    }
    for n, issue in raw.items():
        fixture[f"repos/o/r/issues/{n}"] = issue
        fixture[f"repos/o/r/issues/{n}/dependencies/blocked_by"] = [
            raw[b] for b in blocker_numbers(queue, n)]
    return fixture


class BackendCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "calls.log"
        self.fixture_path = self.dir / "fixture.json"

    def run_frontier(self, backend, fixture, *args, extra_env=None):
        self.fixture_path.write_text(json.dumps(fixture))
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("SYMPHONY", "STUB_", "GH_", "GITLAB_"))}
        env["PATH"] = str(STUBS) + os.pathsep + env.get("PATH", "")
        stub = {"gitea": "TEA", "github": "GH", "gitlab": "GLAB"}[backend]
        env[f"STUB_{stub}_FIXTURE"] = str(self.fixture_path)
        env[f"STUB_{stub}_LOG"] = str(self.log)
        env.update(extra_env or {})
        cmd = [sys.executable, str(FRONTIER), "--backend", backend, "--repo", REPO_NAME]
        cmd += list(args)
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, env=env)

    def calls(self):
        return [line.split() for line in self.log.read_text().splitlines()]


class SameFrontierTest(BackendCase):
    def test_one_queue_yields_the_same_frontier_on_gitea_and_github(self):
        self.log.unlink(missing_ok=True)

        gitea = self.run_frontier("gitea", gitea_fixture(QUEUE))
        self.assertEqual(gitea.returncode, 0, gitea.stderr)
        self.assertEqual(gitea.stdout, EXPECTED)

        github = self.run_frontier("github", github_fixture(QUEUE))
        self.assertEqual(github.returncode, 0, github.stderr)
        self.assertEqual(github.stdout, EXPECTED)


class LoudFailureTest(BackendCase):
    def test_a_failed_github_blocked_by_call_exits_nonzero_and_names_the_call(self):
        r = self.run_frontier("github", github_fixture(QUEUE),
                              extra_env={"STUB_GH_FAIL": "blocked_by"})

        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("gh api", r.stderr)
        self.assertIn("repos/o/r/issues/6/dependencies/blocked_by", r.stderr)


if __name__ == "__main__":
    unittest.main()
