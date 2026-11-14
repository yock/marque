#!/usr/bin/env python3
"""split_spec.py --backend gitea|github|gitlab --repo OWNER/NAME [--host H]
--state-dir DIR SPEC...: split specs into greppable files.

Writes DIR/specs/<n>/:
  body-NN-<slug>.md   one per `##`/`###` section of the issue body (body-00 is the intro);
  cNN.md              each comment, 1-based, in order (comments amend the body; latest word wins);
  index.txt           file, size, first heading or first line.
The tracker's facts arrive as flags; this script reads no config file and no
environment. Raw markdown comes from the REST API, not the CLI's reflowed view.
Re-running replaces the files.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tracker import BACKENDS, TrackerError, backend  # noqa: E402


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--login",
                    help="tea login name / gh user / name of the env var holding the "
                         "GitLab token")
    ap.add_argument("--host", help="the tracker host, for gh and glab (gitea ignores it)")
    ap.add_argument("--state-dir", required=True, help="the state directory to write under")
    ap.add_argument("spec", nargs="+", type=int)
    return ap.parse_args(argv)


def write_spec(n, issue, comments, root):
    """Write one spec's sections, comments and index under root, replacing the old split."""
    out = root / "specs" / str(n)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.md"):
        f.unlink()
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


def split(a):
    """Split each spec, in the order given; stop at the first one that fails."""
    tracker = backend(a.backend, a.repo, a.login, a.host)
    root = Path(a.state_dir)
    for n in a.spec:
        issue = tracker.issue(n)
        if issue is None:
            print(f"split_spec.py: #{n} not found", file=sys.stderr)
            return 1
        comments = tracker.comments(n)
        write_spec(n, issue, comments, root)
    return 0


def main(argv=None):
    a = parse_args(argv)
    try:
        return split(a)
    except TrackerError as e:
        print(f"split_spec.py: {' '.join(e.cmd)} failed: {e.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
