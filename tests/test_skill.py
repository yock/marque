"""Marque's prose: harness-neutral, free of retired names, indexed by pointers."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "skills" / "marque"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "reference"

# Retired by #30: the config file, the brief script, the battery script, their
# library, and the old ledger markers. The harness tool names are #4's: the
# skill speaks in verbs and lets reference/harnesses.md map them.
RETIRED = (
    "symphony.toml",
    "brief.py",
    "battery.sh",
    "symphony_lib",
    "ANSWERED",
    "asked_marker",
    "opus",
    "notify_phone",
    "PushNotification",
    "SendMessage",
    "send_input",
    "wait_agent",
    "resume_agent",
    "Task(",
    "subagent(",
)

# #30 fixes these names; other tickets write some of them.
REFERENCES = {
    "commission.md",
    "extensions.md",
    "harnesses.md",
    "operations.md",
    "landing.md",
    "asking.md",
}
REFERENCE_PATH = re.compile(r"reference/[a-z-]+\.md")


class RetiredVocabularyTest(unittest.TestCase):
    def assert_clean(self, path):
        text = path.read_text()
        for retired in RETIRED:
            self.assertNotIn(retired, text)
        for line in text.splitlines():
            # ready-for-human means human implementation; the retired `blocking`
            # label spent the same place on urgency (#7 item 5).
            if "ready-for-human" in line:
                self.assertNotIn("blocking", line)

    def test_the_skill_leaves_the_retired_names_out(self):
        self.assert_clean(SKILL)

    def test_the_landing_reference_leaves_the_retired_names_out(self):
        self.assert_clean(REFERENCE_DIR / "landing.md")

    def test_the_asking_reference_leaves_the_retired_names_out(self):
        self.assert_clean(REFERENCE_DIR / "asking.md")


class TitleTest(unittest.TestCase):
    def test_the_skill_is_titled_marque(self):
        text = SKILL.read_text()
        self.assertIn("\n# Marque: ", text)
        self.assertNotIn("symphony", text.lower())


class ReferenceIndexTest(unittest.TestCase):
    def test_the_skill_points_at_exactly_its_six_references(self):
        mentioned = {Path(p).name for p in REFERENCE_PATH.findall(SKILL.read_text())}
        self.assertEqual(mentioned, REFERENCES)


class LandingReferenceTest(unittest.TestCase):
    def test_landing_names_the_guard_the_target_branch_and_the_script(self):
        text = (REFERENCE_DIR / "landing.md").read_text()
        for marker in ("--no-ff", "target branch", "land.py"):
            self.assertIn(marker, text)


class AskingReferenceTest(unittest.TestCase):
    def test_asking_names_the_label_the_map_and_the_signal(self):
        text = (REFERENCE_DIR / "asking.md").read_text()
        for marker in ("needs-info", "triage-labels.md", "ready-for-agent"):
            self.assertIn(marker, text)


class LoopCallsTest(unittest.TestCase):
    def test_the_loop_names_its_scripts_asset_and_verbs(self):
        text = SKILL.read_text()
        for name in (
            "frontier.py",
            "split_spec.py",
            "land.py",
            "ledger.py",
            "assets/brief-tail.md",
        ):
            self.assertIn(name, text)
        for verb in (
            "dispatch a background subagent",
            "resume the same session",
            "push a notification",
        ):
            self.assertIn(verb, text)


# The commission's gap-check list (#31): the operations Marque reaches for, in
# the order the reference snippets must cover them.
OPERATIONS = (
    "List by label",
    "Read an issue",
    "Parent",
    "Blocking",
    "Count open blockers",
    "Assign / unassign",
    "Comment",
    "Apply / remove labels",
    "Close",
    "Open a PR",
    "Merge a PR",
    "Read PR approval",
    "Orchestrator identity",
)
TRACKERS = ("github", "gitlab", "gitea", "local")


class TrackerSnippetTest(unittest.TestCase):
    def test_each_snippet_covers_every_operation(self):
        for tracker in TRACKERS:
            text = (REFERENCE_DIR / "trackers" / f"{tracker}.md").read_text()
            for operation in OPERATIONS:
                with self.subTest(tracker=tracker, operation=operation):
                    self.assertIn(f"\n- **{operation}**", text)


class CommissionReferenceTest(unittest.TestCase):
    def test_the_commission_stops_when_the_setup_files_are_missing(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("docs/agents/issue-tracker.md", text)
        self.assertIn("## Agent skills", text)
        self.assertIn("`/setup-matt-pocock-skills`", text)

    def test_the_commission_lists_the_defaults_and_their_one_override(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        for marker in (
            "~/.local/share/marque/<repo-name>",
            ".marque/worktrees",
            "docs/agents/marque.md",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_commission_names_marques_post_marker_and_approval_state(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        for marker in ("Posted by Marque", "awaiting-approval"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_commission_writes_every_term_to_the_plan(self):
        text = (REFERENCE_DIR / "commission.md").read_text().lower()
        for term in (
            "implementer model",
            "authority",
            "fallback",
            "concurrency",
            "paid compute",
            "target branch",
            "landing mode",
            "approval cap",
            "notifications",
            "extensions",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)


class CommissionPointersTest(unittest.TestCase):
    def test_the_commission_points_at_every_tracker_snippet(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        for tracker in TRACKERS:
            with self.subTest(tracker=tracker):
                self.assertIn(f"reference/trackers/{tracker}.md", text)
