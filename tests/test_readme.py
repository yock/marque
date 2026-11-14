"""The README: what Marque is, how it is installed, and what it needs."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"

# #35's opener is literal, backticks and all.
OPENER = "after `to-tickets`, Marque works your queue under your command"


class PositioningTest(unittest.TestCase):
    def test_the_readme_opens_with_its_one_line_and_its_three_contrasts(self):
        text = README.read_text()
        self.assertIn(OPENER, text)
        for marker in ("implement-spec", "Sandcastle", "Nelson"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


class InstallAndRequirementsTest(unittest.TestCase):
    def test_the_readme_names_its_install_requirements_and_pinning(self):
        text = README.read_text()
        for marker in (
            "/marque:marque",
            "yock/marque",
            "npx skills add",
            "codex",
            "@v0.1.0",
            "#v0.1.0",
            "3.9",
            "/setup-matt-pocock-skills",
            "to-tickets",
            "1.x",
            "gitea.yock.dev",
            "best-effort",
            "examples/battery-pacing",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


class RetiredNamesTest(unittest.TestCase):
    def test_the_readme_leaves_the_retired_files_and_symlink_installs_out(self):
        text = README.read_text()
        for marker in ("symphony.toml", "brief.py", "config.example.toml", "ln -s", "symlink"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)


class PathsTest(unittest.TestCase):
    def test_every_repo_path_the_readme_names_exists(self):
        text = README.read_text()
        named = [
            span
            for span in re.findall(r"`([^`\n]+)`", text)
            if span.startswith(("skills/", "examples/", ".claude-plugin/"))
        ]
        self.assertTrue(named, "the README names no repo paths")
        for span in named:
            with self.subTest(path=span):
                self.assertTrue((REPO / span).exists(), span)
