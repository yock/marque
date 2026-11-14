"""The moved skill's scripts still run from skills/marque/."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "marque" / "scripts"
CONFIG = """\
[tracker]
backend = "gitea"
repo = "o/r"
login = "bot"

[state]
dir = "{state}"

[brief]
worktrees = ".claude/worktrees"
worktree_prefix = "orch-"
code_dir = "src"
"""


def run(script, *args, cwd):
    env = {k: v for k, v in os.environ.items() if k != "SYMPHONY_CONFIG"}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


class ScriptHelpTest(unittest.TestCase):
    def test_each_moved_script_prints_its_usage(self):
        # argparse's documented --help: exit 0 and a "usage: <prog>" line first.
        for name in ("frontier.py", "split_spec.py", "brief.py"):
            with self.subTest(script=name):
                r = run(SCRIPTS / name, "--help", cwd=REPO)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(r.stdout.startswith(f"usage: {name}"), r.stdout)


class BriefExploreTest(unittest.TestCase):
    def test_explore_fills_its_template_from_assets(self):
        # brief.py's docstring: "write the filled explore prompt to
        # state.dir/explore/N.md ... Fails if any {{PLACEHOLDER}} is left".
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "agents").mkdir(parents=True)
            state = root / "state"
            (root / "docs" / "agents" / "symphony.toml").write_text(
                CONFIG.format(state=state)
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            r = run(SCRIPTS / "brief.py", "explore", "7", "3", cwd=root)

            self.assertEqual(r.returncode, 0, r.stderr)
            out = state / "explore" / "7.md"
            self.assertEqual(r.stdout.strip(), str(out))
            text = out.read_text()
            self.assertEqual(re.findall(r"\{\{[A-Z_]+\}\}", text), [])
            # assets/explore.md renders "Ticket #{{ISSUE}}".
            self.assertIn("#7", text)
