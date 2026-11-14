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
    def test_native_edges_and_parent_sections_rank_by_fanout(self):
        # to-tickets shape: native dependencies and a `## Parent` section, no body
        # `Blocked by`. #22 waits on the closed #20 and blocks #23, which blocks #24:
        # fan(#22) = 2 (#23, #24). #40 waits on nothing. Both are children of #18.
        self.issues(
            [{"number": 18, "title": "The spec"},
             {"number": 20, "state": "closed"},
             {"number": 22, "title": "First", "labels": ["ready-for-agent"],
              "body": "## Parent\n\n#18"},
             {"number": 23, "title": "Second", "labels": ["ready-for-agent"],
              "body": "## Parent\n\n#18"},
             {"number": 24, "title": "Third", "labels": ["ready-for-agent"],
              "body": "## Parent\n\n#18"},
             {"number": 40, "title": "Fourth", "labels": ["ready-for-agent"],
              "body": "## Parent\n\n#18"}],
            deps={22: [20], 23: [22], 24: [23], 40: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 4  frontier 2  externally blocked 0", r.stdout)
        body = r.stdout.splitlines()[1:]
        self.assertEqual(body, [
            "#   22  fan   2  parent #  18  c0  First",
            "#   40  fan   0  parent #  18  c0  Fourth",
        ])
        self.assertNotIn("READ BY HAND", r.stdout)

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

    def test_a_declaration_of_none_declares_no_blockers(self):
        self.issues(
            [{"number": 5, "title": "Line says none", "labels": ["ready-for-agent"],
              "body": "Blocked by: None"},
             {"number": 6, "title": "Section says none", "labels": ["ready-for-agent"],
              "body": "## Blocked by\n\n- None (can start immediately)"}],
            deps={5: [], 6: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 2  frontier 2  externally blocked 0", r.stdout)
        self.assertIn("#    5  fan   0  parent     -  c0  Line says none", r.stdout)
        self.assertIn("#    6  fan   0  parent     -  c0  Section says none", r.stdout)
        self.assertNotIn("READ BY HAND", r.stdout)

    def test_native_and_body_blockers_that_disagree_are_both_counted(self):
        # The tracker says #5 blocks #9; the body says #6. Union: both block, and the
        # mismatch is reported. #5 is open, #6 is closed.
        self.issues(
            [{"number": 5, "state": "open"},
             {"number": 6, "state": "closed"},
             {"number": 9, "title": "Unsure", "labels": ["ready-for-agent"],
              "body": "Blocked by: #6"}],
            deps={9: [5]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: native [5] vs body [6] (both counted)", r.stdout)
        self.assertNotIn("#    9  fan", r.stdout)
        self.assertIn("externally blocked: #9<-#5", r.stdout)

    def test_parent_order_breaks_a_fanout_tie(self):
        # All four have fan-out 0. Parents: #7, #18, #18, none.
        # Rank says parented first, ascending by parent, then parentless.
        self.issues(
            [{"number": 7, "title": "Spec seven"},
             {"number": 18, "title": "Spec eighteen"},
             {"number": 30, "title": "Child of 18", "labels": ["ready-for-agent"],
              "body": "Part of #18"},
             {"number": 31, "title": "Child of 7", "labels": ["ready-for-agent"],
              "body": "## Parent\n\n#7"},
             {"number": 32, "title": "Parentless", "labels": ["ready-for-agent"]},
             {"number": 33, "title": "Also child of 18", "labels": ["ready-for-agent"],
              "body": "Part of #18"}],
            deps={30: [], 31: [], 32: [], 33: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[1:], [
            "#   31  fan   0  parent #   7  c0  Child of 7",
            "#   30  fan   0  parent #  18  c0  Child of 18",
            "#   33  fan   0  parent #  18  c0  Also child of 18",
            "#   32  fan   0  parent     -  c0  Parentless",
        ])

    def test_an_assigned_ticket_is_never_on_the_frontier(self):
        self.issues(
            [{"number": 5, "title": "Claimed", "labels": ["ready-for-agent"],
              "assignees": ["dev"]},
             {"number": 6, "title": "Free", "labels": ["ready-for-agent"]}],
            deps={5: [], 6: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 2  frontier 1  externally blocked 0", r.stdout)
        self.assertIn("#    6  fan   0  parent     -  c0  Free", r.stdout)
        self.assertNotIn("#    5  fan", r.stdout)

    def test_json_prints_the_frontier_and_the_login_reaches_every_call(self):
        self.issues(
            [{"number": 7, "title": "Child", "labels": ["ready-for-agent"],
              "body": "Part of #18", "comments": 2},
             {"number": 8, "title": "Parentless", "labels": ["ready-for-agent"]},
             {"number": 18, "title": "Spec"}],
            deps={7: [], 8: []},
            comments={7: ["one", "two"]},
        )

        r = self.run_frontier("--json", login="bot")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [
            {"number": 7, "title": "Child", "fanout": 0, "parent": 18, "comments": 2, "hand": []},
            {"number": 8, "title": "Parentless", "fanout": 0, "parent": None, "comments": 0,
             "hand": []},
        ])
        self.assertTrue(self.log.read_text().splitlines()[0].endswith(" login=bot"))

    def test_a_url_and_a_cross_repo_reference_are_reported_and_block(self):
        self.issues(
            [{"number": 9, "title": "URL", "labels": ["ready-for-agent"],
              "body": "Blocked by: https://git.example/o/r/issues/4"},
             {"number": 10, "title": "Cross repo", "labels": ["ready-for-agent"],
              "body": "Blocked by: other/repo#2"}],
            deps={9: [], 10: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: unparseable reference "
                      "https://git.example/o/r/issues/4, treated as open", r.stdout)
        self.assertIn("READ BY HAND #10: unparseable reference other/repo#2, treated as open",
                      r.stdout)
        self.assertIn("queue 2  frontier 0  externally blocked 0", r.stdout)

    def test_a_reference_to_a_missing_issue_is_treated_as_open(self):
        self.issues(
            [{"number": 9, "title": "Gone", "labels": ["ready-for-agent"],
              "body": "Blocked by: #99"}],
            deps={9: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: reference #99 not found, treated as open", r.stdout)
        self.assertIn("queue 1  frontier 0  externally blocked 1", r.stdout)
        self.assertIn("externally blocked: #9<-#99", r.stdout)

    def test_a_blocker_labelled_as_a_map_is_not_a_ticket(self):
        self.issues(
            [{"number": 50, "title": "A map", "labels": ["wayfinder:map"]},
             {"number": 9, "title": "Task", "labels": ["ready-for-agent"]}],
            deps={9: [50]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: blocked by #50, a map or spec, not a ticket", r.stdout)
        self.assertNotIn("#    9  fan", r.stdout)
        self.assertIn("externally blocked: #9<-#50", r.stdout)

    def test_a_blocker_that_is_a_queued_tickets_parent_is_a_spec(self):
        # #18 is an ordinary open issue, but #22 is `Part of #18`, so #18 is a spec.
        self.issues(
            [{"number": 9, "title": "Waits on the spec", "labels": ["ready-for-agent"]},
             {"number": 18, "title": "The spec"},
             {"number": 22, "title": "A child", "labels": ["ready-for-agent"],
              "body": "Part of #18"}],
            deps={9: [18], 22: []},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: blocked by #18, a map or spec, not a ticket", r.stdout)
        self.assertIn("#   22  fan   0  parent #  18  c0  A child", r.stdout)

    def test_questions_in_the_newest_comment_need_the_waiting_label(self):
        self.issues(
            [{"number": 9, "title": "Needs an answer", "labels": ["ready-for-agent"],
              "comments": 1}],
            deps={9: []},
            comments={9: ["## Questions\n\n- which database?"]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: has questions but no needs-info label", r.stdout)
        # Read-by-hand tickets stay on the frontier when they are otherwise eligible.
        self.assertIn("#    9  fan   0  parent     -  c1  Needs an answer", r.stdout)

    def test_a_questioning_ticket_with_the_waiting_label_waits(self):
        self.issues(
            [{"number": 9, "title": "Asked", "labels": ["ready-for-agent", "needs-info"],
              "comments": 1}],
            deps={9: []},
            comments={9: ["## Questions\n\n- which database?"]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WAITING #9 (needs-info)", r.stdout)
        self.assertIn("queue 1  frontier 0  externally blocked 0", r.stdout)
        self.assertNotIn("READ BY HAND", r.stdout)
        self.assertNotIn("#    9  fan", r.stdout)

    def test_only_the_newest_comment_is_read_for_questions(self):
        self.issues(
            [{"number": 9, "title": "Answered", "labels": ["ready-for-agent"],
              "comments": 2}],
            deps={9: []},
            comments={9: ["## Questions\n\n- which database?", "## Answer\n\n- postgres"]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("READ BY HAND", r.stdout)
        self.assertIn("#    9  fan   0  parent     -  c2  Answered", r.stdout)

    def test_tracker_calls_are_made_one_at_a_time_starting_with_the_two_lists(self):
        # #7 waits on the closed #5 and has one comment, so it reads comments too.
        self.issues(
            [{"number": 5, "state": "closed"},
             {"number": 7, "labels": ["ready-for-agent"], "comments": 1}],
            deps={7: [5]},
            comments={7: ["## Notes\n\nall good"]},
        )

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        log = self.log.read_text().splitlines()
        self.assertNotIn("OVERLAP", log)
        kinds = [line.split()[0] for line in log]
        self.assertEqual(kinds, ["start", "end"] * (len(kinds) // 2))
        paths = [line.split()[1] for line in log if line.startswith("start ")]
        self.assertEqual(paths[:2], [
            "repos/o/r/issues?state=open&page=1&limit=50&type=issues&labels=ready-for-agent",
            "repos/o/r/issues?state=open&page=1&limit=50&type=issues",
        ])

    def test_limit_caps_the_frontier_lines(self):
        self.issues(
            [{"number": n, "title": f"Ticket {n}", "labels": ["ready-for-agent"]}
             for n in (5, 6, 7)],
            deps={5: [], 6: [], 7: []},
        )

        r = self.run_frontier("--limit", "1")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue 3  frontier 3  externally blocked 0", r.stdout)
        self.assertEqual(r.stdout.splitlines()[1:], ["#    5  fan   0  parent     -  c0  Ticket 5"])

    def test_a_native_blocker_from_another_repo_is_unparseable(self):
        # The native endpoint can name an issue in another repo; this repo cannot
        # resolve it, so it is reported and counted as open.
        self.issues(
            [{"number": 9, "title": "Elsewhere", "labels": ["ready-for-agent"]}],
            deps={9: []},
        )
        self.fixture[f"repos/{REPO_NAME}/issues/9/dependencies"] = [
            {"number": 2, "state": "open", "repository": {"full_name": "other/repo"}}]

        r = self.run_frontier()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ BY HAND #9: unparseable reference other/repo#2, treated as open",
                      r.stdout)
        self.assertIn("queue 1  frontier 0  externally blocked 0", r.stdout)

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
