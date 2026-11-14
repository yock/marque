"""The prompt assets keep their placeholders honest."""
import re
import unittest
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "skills" / "marque" / "assets"
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def split_header(name):
    """The header comment (before the first ``-->``) and the body after it."""
    text = (ASSETS / name).read_text()
    start = text.find("<!--")
    end = text.find("-->", start)
    return text[start:end], text[end + 2:]


class AssetPlaceholderTest(unittest.TestCase):
    def test_each_asset_lists_exactly_the_placeholders_it_uses(self):
        for name in ("brief-tail.md", "explore.md"):
            with self.subTest(asset=name):
                header, body = split_header(name)
                self.assertEqual(
                    sorted(set(PLACEHOLDER.findall(header))),
                    sorted(set(PLACEHOLDER.findall(body))),
                )


class BriefTailTest(unittest.TestCase):
    def test_retired_placeholders_are_gone(self):
        # The brief tail takes build and test rules from AGENTS.md and names
        # the target branch; it no longer splices a rules file or says main.
        header, body = split_header("brief-tail.md")
        for retired in ("PROJECT_RULES", "MASTER", "CONTEXT.md"):
            self.assertNotIn(retired, header + body)


class ExploreTest(unittest.TestCase):
    def test_the_ticket_is_read_with_the_tracker_docs_command(self):
        header, body = split_header("explore.md")
        self.assertNotIn("tea ", header + body)
        self.assertNotIn("{{API}}", header + body)
