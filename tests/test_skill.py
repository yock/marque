"""Marque's prose: harness-neutral, free of retired names, indexed by pointers."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins" / "marque" / "skills" / "marque"
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
    "runners.md",
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
    def test_the_skill_points_at_exactly_its_references(self):
        mentioned = {Path(p).name for p in REFERENCE_PATH.findall(SKILL.read_text())}
        self.assertEqual(mentioned, REFERENCES)


class LandingReferenceTest(unittest.TestCase):
    def test_landing_names_the_guard_the_target_branch_and_the_script(self):
        text = (REFERENCE_DIR / "landing.md").read_text()
        for marker in ("--no-ff", "target branch", "land.py"):
            self.assertIn(marker, text)

    def test_landing_describes_the_tree_that_landed_and_the_response(self):
        text = (REFERENCE_DIR / "landing.md").read_text()
        for marker in ("and exits **4**", "target-red rule", "suite.py run --record"):
            with self.subTest(marker=marker):
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
        self.assertIn("stall hour", text.lower())

    def test_the_gap_check_lists_every_operation(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIn(operation, text)

    def test_the_gap_check_writes_only_with_approval_and_reports_a_disagreement(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("only with the developer's approval", text)
        self.assertIn("disagree", text)

    def test_a_claim_outside_the_ledger_is_asked_about(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("yours, or orphaned?", text)

    def test_the_approval_term_is_impossible_on_the_approving_account(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("impossible", text)
        self.assertIn("approve its own PR", text)

    def test_the_commission_names_marques_post_marker_and_approval_state(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        for marker in ("Posted by Marque", "awaiting-approval"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_commission_recommends_the_up_to_date_setting_for_pr_mode(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("branch must be up to date", text)

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


class ExtensionsReferenceTest(unittest.TestCase):
    def test_extensions_names_the_five_points_the_two_files_and_approval(self):
        # #8's resolution: five points, two files, approval recorded in the plan,
        # and a mid-run change re-approved.
        text = (REFERENCE_DIR / "extensions.md").read_text()
        for point in ("commission", "dispatch", "brief", "review", "notify"):
            with self.subTest(point=point):
                self.assertIn(point, text)
        for marker in (
            "docs/agents/marque.md",
            "~/.config/marque/marque.md",
            "applies after",
            "plan.md",
            "re-approv",
            "add to or tighten",
            "ignores that part",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_notify_events_live_here_and_the_battery_example_is_gone(self):
        # #8: every ten landings is a core event; battery emergency left the list.
        text = (REFERENCE_DIR / "extensions.md").read_text()
        self.assertIn("every ten landings", text)
        self.assertIn("otherwise chat", text)
        self.assertNotIn("battery emergency", text)


EXAMPLES = REPO / "examples"


class BatteryPacingExampleTest(unittest.TestCase):
    def test_the_sample_file_has_the_three_sections_it_exercises(self):
        # #8's worked example: commission, dispatch and notify only.
        text = (EXAMPLES / "battery-pacing" / "marque.md").read_text()
        headings = [line for line in text.splitlines() if line.startswith("#")]
        self.assertEqual(headings, ["## commission", "## dispatch", "## notify"])

    def test_the_sample_policy_is_sixty_forty_twenty(self):
        # #8's worked example: the 60/40/20 % battery policy.
        text = (EXAMPLES / "battery-pacing" / "marque.md").read_text()
        for mark in ("60 %", "40 %", "20 %"):
            with self.subTest(mark=mark):
                self.assertIn(mark, text)

    def test_the_example_owns_its_variables_and_the_script_left_the_skill(self):
        # SYMPHONY names retired with the move; the script lives at the repo root.
        for path in EXAMPLES.rglob("*"):
            if path.is_file():
                with self.subTest(path=str(path)):
                    self.assertNotIn("SYMPHONY", path.read_text())
        self.assertFalse((SKILL_DIR / "scripts" / "battery.sh").exists())


class ExtensionPointersTest(unittest.TestCase):
    def test_the_skill_points_at_extensions_at_every_point_and_drops_pacing(self):
        text = SKILL.read_text()
        self.assertIsNone(re.search(r"^#+ .*Pacing", text, re.M))
        self.assertGreaterEqual(text.count("reference/extensions.md"), 5)


# #33: the neutral verbs SKILL.md dispatches in, and the three harnesses the
# reference maps them to.
HARNESS_VERBS = (
    "dispatch a background subagent",
    "resume the same session",
    "push a notification",
    "run a background command that wakes you",
)
HARNESSES = ("OpenCode", "Claude Code", "Codex")


class HarnessReferenceTest(unittest.TestCase):
    def harnesses_md(self):
        return (REFERENCE_DIR / "harnesses.md").read_text()

    def test_every_verb_skill_md_uses_is_mapped_per_harness(self):
        text = self.harnesses_md()
        for verb in HARNESS_VERBS:
            with self.subTest(verb=verb):
                self.assertIn(verb, text)
        for harness in HARNESSES:
            with self.subTest(harness=harness):
                self.assertIn(harness, text)

    def test_the_degradations_and_the_permission_settings_are_named(self):
        text = self.harnesses_md()
        for marker in ("wait_agent", "alias", "additionalDirectories", "writable_roots"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_messaging_a_running_implementer_is_an_extra_not_core(self):
        text = self.harnesses_md()
        section = re.search(r"^#+ [^\n]*\bextras?\b[^\n]*\n(.*?)(?=^#+ |\Z)", text, re.M | re.S | re.I)
        self.assertIsNotNone(section, "no heading names the per-harness extras")
        self.assertIn("messaging a running implementer", section.group(1).lower())

    def test_the_commission_points_at_the_permission_setup(self):
        text = (REFERENCE_DIR / "commission.md").read_text()
        self.assertIn("reference/harnesses.md", text)

    def test_the_harness_tools_stay_out_of_the_skill(self):
        text = SKILL.read_text()
        for name in (
            "spawn_agent",
            "send_input",
            "wait_agent",
            "resume_agent",
            "additionalDirectories",
            "writable_roots",
            "write_stdin",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, text)


# #34: the operations lessons, reworded for any stack (#15's sorting test).
PROJECT_SPECIFIC = (
    "opus",
    "ANSWERED",
    "asked_marker",
    "orch-<n>-recovery",
    "flock",
    "oomd",
    "oomctl",
    "battery",
    "systemd",
    "excess elements",
    "C row",
    "about half",
)
POSITIONAL_LESSON = (
    "Positional constructs (row tables, tuples, positional constructor calls) "
    "can merge cleanly and still be wrong. Two branches each add a field, and "
    "one side's values land in the other side's fields. Check the merged order."
)
SHARED_MACHINE_LESSON = (
    "Implementers and integration runs share one machine. If a project's full "
    "suite is heavy, suites take turns. The project's `AGENTS.md` says how, and "
    "the orchestrator's integration runs follow the same rule."
)


class OperationsReferenceTest(unittest.TestCase):
    def operations_md(self):
        return (REFERENCE_DIR / "operations.md").read_text()

    def test_the_passing_lessons_name_no_stack_tool_or_machine(self):
        text = self.operations_md()
        for marker in PROJECT_SPECIFIC:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)
        self.assertIsNone(re.search(r"\bmain\b", text))

    def test_the_operations_name_their_state_scripts_and_neighbours(self):
        text = self.operations_md()
        for marker in (
            "orchestrator",
            "marque-<n>-recovery",
            "target branch",
            "docs/agents/marque.md",
            "ledger.py",
            "reference/landing.md",
            "reference/extensions.md",
            "stall hour",
            "default 1 hour",
            POSITIONAL_LESSON,
            SHARED_MACHINE_LESSON,
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


# #44: the Beam runner's contract, its `## Runner` block and the CLI allowlist.
class RunnersReferenceTest(unittest.TestCase):
    def runners_md(self):
        return (REFERENCE_DIR / "runners.md").read_text()

    def test_the_beam_runner_reference_names_the_contract_the_block_and_the_limits(self):
        text = self.runners_md()
        for marker in (
            "--ttl",
            "--timeout",
            "started_at",
            "container list",
            "## Runner",
            "max wall time",
            "600",
            "beam status",
            "no unlimited TTL",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_beam_runner_reference_names_every_allowed_command(self):
        text = self.runners_md()
        for command in (
            "image build",
            "image get",
            "container create",
            "container cp",
            "container exec",
            "container stop",
            "container list",
        ):
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_runner_configuration_is_an_override_not_an_extension(self):
        text = (REFERENCE_DIR / "extensions.md").read_text()
        self.assertIn("not an extension", text)


# #42: green is bound to the tree (ADR 0001). The prose names the record flag and
# the seventh safeguard, and offers no second way to be green.
class SuiteRecordWordingTest(unittest.TestCase):
    def test_the_skill_and_the_landing_reference_name_the_suite_record_flag(self):
        for path in (SKILL, REFERENCE_DIR / "landing.md"):
            with self.subTest(path=path.name):
                self.assertIn("--suite-record", path.read_text())

    def test_the_landing_reference_names_the_seventh_safeguard(self):
        text = (REFERENCE_DIR / "landing.md").read_text()
        for marker in ("seven safeguards", "The landed tree is the tested tree"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_no_prose_still_offers_the_old_green(self):
        paths = [SKILL, *sorted(REFERENCE_DIR.glob("*.md"))]
        for path in paths:
            text = path.read_text()
            for retired in ("--suite-green", "mtime", "only in docs"):
                with self.subTest(path=path.name, retired=retired):
                    self.assertNotIn(retired, text)
