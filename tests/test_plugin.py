"""The repo is an installable, user-invoked plugin."""
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "marque" / "SKILL.md"
PLUGIN = REPO / ".claude-plugin"


def frontmatter(path):
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    return lines[1:end]


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_is_named_marque_and_user_invoked(self):
        lines = frontmatter(SKILL)
        self.assertIn("name: marque", lines)
        self.assertIn("disable-model-invocation: true", lines)

    def test_openai_manifest_disallows_implicit_invocation(self):
        text = (SKILL.parent / "agents" / "openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", text)


class ManifestsTest(unittest.TestCase):
    def test_plugin_manifest_names_marque_at_version_0_1_0(self):
        data = json.loads((PLUGIN / "plugin.json").read_text())
        self.assertEqual(data["name"], "marque")
        self.assertEqual(data["version"], "0.1.0")

    def test_marketplace_has_one_entry_sourcing_this_repo(self):
        data = json.loads((PLUGIN / "marketplace.json").read_text())
        self.assertEqual(len(data["plugins"]), 1)
        self.assertEqual(data["plugins"][0]["name"], "marque")
        self.assertEqual(data["plugins"][0]["source"], "./")


class LicenseTest(unittest.TestCase):
    def test_license_is_mit_for_michael_yockey(self):
        text = (REPO / "LICENSE").read_text()
        self.assertEqual(text.splitlines()[0], "MIT License")
        self.assertIn("Copyright (c) 2026 Michael Yockey", text)


class NoSymlinksTest(unittest.TestCase):
    def test_the_plugin_tree_has_no_symlinks(self):
        # Codex drops symlinks when it copies the plugin (#11).
        links = [
            str(p)
            for p in REPO.rglob("*")
            if ".git" not in p.parts and p.is_symlink()
        ]
        self.assertEqual(links, [])
