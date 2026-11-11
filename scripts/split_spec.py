#!/usr/bin/env python3
"""split_spec.py [--config PATH] SPEC...: split a spec issue and its comments into files an agent can grep.

Writes state.dir/specs/<n>/:
  body-NN-<slug>.md   one per `##`/`###` section of the issue body (body-00 is the intro);
  cNN.md              each comment, 1-based, in order (comments amend the body; latest word wins);
  index.txt           file, size, first heading or first line.
Raw markdown from the REST API, not the CLI's reflowed view. Re-running replaces the files.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from symphony_lib import Project  # noqa: E402


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("spec", nargs="+", type=int)
    a = ap.parse_args()
    pr = Project(a.config)
    for n in a.spec:
        out = pr.state / "specs" / str(n)
        out.mkdir(parents=True, exist_ok=True)
        for f in out.glob("*.md"):
            f.unlink()
        issue = pr.issue(n)
        comments = pr.comments(n)
        index = [f"#{n} {issue['title']}"]
        parts = re.split(r"(?m)^(?=#{2,3} )", issue["body"])
        for i, p in enumerate(parts):
            head = p.splitlines()[0] if p.strip() else ""
            name = f"body-{i:02d}-{slug(head.lstrip('#')) or 'intro'}.md"
            (out / name).write_text(p)
            index.append(f"{name}\t{len(p)}\t{head[:100]}")
        for i, c in enumerate(comments, 1):
            body = c.get("body") or ""
            name = f"c{i:02d}.md"
            (out / name).write_text(body)
            first = next((ln for ln in body.splitlines() if ln.strip()), "")
            index.append(f"{name}\t{len(body)}\t{first[:100]}")
        (out / "index.txt").write_text("\n".join(index) + "\n")
        print(f"#{n}: {len(parts)} body sections, {len(comments)} comments -> {out}")


if __name__ == "__main__":
    main()
