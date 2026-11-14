"""The repo is an installable, user-invoked plugin."""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "marque" / "SKILL.md"


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
