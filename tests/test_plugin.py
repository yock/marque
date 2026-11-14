"""The repo is a marketplace for one installable, user-invoked plugin."""
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
PLUGIN_ROOT = REPO / "plugins" / "marque"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
SKILL = PLUGIN_ROOT / "skills" / "marque" / "SKILL.md"


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
        data = json.loads(PLUGIN_MANIFEST.read_text())
        self.assertEqual(data["name"], "marque")
        self.assertEqual(data["version"], "0.1.0")

    def test_plugin_manifest_skills_resolve_inside_the_plugin(self):
        data = json.loads(PLUGIN_MANIFEST.read_text())
        for path in data["skills"]:
            with self.subTest(path=path):
                self.assertTrue((PLUGIN_ROOT / path / "SKILL.md").exists())

    def test_marketplace_has_one_entry_sourcing_the_plugin_directory(self):
        # Sourcing "./" would ship the whole repo: the dev skills, docs and
        # tests that marketplace validators flag.
        data = json.loads(MARKETPLACE.read_text())
        self.assertEqual(len(data["plugins"]), 1)
        self.assertEqual(data["plugins"][0]["name"], "marque")
        self.assertEqual(data["plugins"][0]["source"], "./plugins/marque")

    def test_no_plugin_manifest_at_the_repo_root(self):
        self.assertFalse((REPO / ".claude-plugin" / "plugin.json").exists())


class ShippedTreeTest(unittest.TestCase):
    def test_the_plugin_ships_only_its_manifest_skill_and_license(self):
        tops = {p.name for p in PLUGIN_ROOT.iterdir() if p.name != "__pycache__"}
        self.assertEqual(tops, {".claude-plugin", "skills", "LICENSE"})


class LicenseTest(unittest.TestCase):
    def test_license_is_mit_for_michael_yockey(self):
        text = (REPO / "LICENSE").read_text()
        self.assertEqual(text.splitlines()[0], "MIT License")
        self.assertIn("Copyright (c) 2026 Michael Yockey", text)

    def test_the_plugin_ships_the_same_license(self):
        self.assertEqual(
            (PLUGIN_ROOT / "LICENSE").read_text(), (REPO / "LICENSE").read_text()
        )


class NoSymlinksTest(unittest.TestCase):
    def test_the_plugin_tree_has_no_symlinks(self):
        # Codex drops symlinks when it copies the plugin (#11).
        links = [
            str(p)
            for p in REPO.rglob("*")
            if ".git" not in p.parts and p.is_symlink()
        ]
        self.assertEqual(links, [])
