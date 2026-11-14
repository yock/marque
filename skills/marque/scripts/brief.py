#!/usr/bin/env python3
"""brief.py: render symphony's templates for one ticket.

  brief.py brief N BRANCH            append the filled brief tail to state.dir/briefs/N.md
                                      (write the ticket part there first); prints the worktree
  brief.py explore N SPEC [--in-flight TEXT]
                                      write the filled explore prompt to state.dir/explore/N.md

The worktree is <brief.worktrees>/<brief.worktree_prefix>N under the repo root. The
project's brief rules file (brief.rules) is spliced in at {{PROJECT_RULES}} and its
own placeholders filled too. Fails if any {{PLACEHOLDER}} is left.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from symphony_lib import Project  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "assets"
LEFT = re.compile(r"\{\{[A-Z_]+\}\}")


def fill(text, values):
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def check(text, where):
    left = sorted(set(LEFT.findall(text)))
    if left:
        raise SystemExit(f"brief.py: unfilled {', '.join(left)} in {where}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief")
    b.add_argument("issue", type=int)
    b.add_argument("branch")
    e = sub.add_parser("explore")
    e.add_argument("issue", type=int)
    e.add_argument("spec", type=int)
    e.add_argument("--in-flight", default="", help="the in-flight tickets to check collisions against")
    a = ap.parse_args()
    pr = Project(a.config)
    worktree = pr.worktrees / f"{pr.worktree_prefix}{a.issue}"
    values = {
        "ISSUE": str(a.issue),
        "WORKTREE": str(worktree),
        "MASTER": str(pr.root),
        "PROJECT": pr.root.name,
        "REPO": pr.repo,
        "API": pr.issue_api_cmd("").strip(),
        "SPECS": str(pr.state / "specs"),
        "CODE": str(pr.code_dir),
    }

    if a.cmd == "brief":
        values["BRANCH"] = a.branch
        rules = pr.brief_rules.read_text() if pr.brief_rules else ""
        values["PROJECT_RULES"] = fill(rules, values).strip()
        tail = (TEMPLATES / "brief.md").read_text()
        tail = tail.split("\n---\n", 1)[1]  # drop the maintainer's header comment
        tail = fill(tail, values)
        check(tail, "the brief tail")
        out = pr.state / "briefs" / f"{a.issue}.md"
        if not out.is_file() or not out.read_text().strip():
            raise SystemExit(f"brief.py: write the ticket part to {out} first")
        if "# How to do this work" in out.read_text():
            raise SystemExit(f"brief.py: {out} already has the tail")
        with open(out, "a") as f:
            f.write("\n---\n" + tail)
        check(out.read_text(), str(out))
        print(worktree)
    else:
        values["SPEC"] = str(a.spec)
        notes = pr.explore_notes.read_text().strip() if pr.explore_notes else ""
        values["EXPLORE_NOTES"] = fill(notes, values)
        values["IN_FLIGHT"] = (f"\nIn flight (check collisions): {a.in_flight}" if a.in_flight else "")
        text = fill((TEMPLATES / "explore.md").read_text(), values)
        check(text, "the explore prompt")
        out = pr.state / "explore" / f"{a.issue}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(out)


if __name__ == "__main__":
    main()
