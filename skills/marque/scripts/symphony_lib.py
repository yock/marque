"""Shared by symphony's scripts: the project config and the issue tracker's REST API.

The config is TOML, found by --config, $SYMPHONY_CONFIG, or by walking up from the
working directory to docs/agents/symphony.toml. Paths in it are relative to the repo
root (the directory holding docs/), except state.dir, which may use ~.

Both trackers are reached through their CLI's raw REST passthrough (`tea api`,
`gh api`), whose issue and comment JSON have the same shape for what symphony reads:
number, title, body, labels[].name, assignees[].login, comments (a count).
"""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

CONFIG_REL = Path("docs/agents/symphony.toml")


class ConfigError(SystemExit):
    pass


def find_config(explicit=None):
    if explicit:
        return Path(explicit).resolve()
    if os.environ.get("SYMPHONY_CONFIG"):
        return Path(os.environ["SYMPHONY_CONFIG"]).resolve()
    here = Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / CONFIG_REL).is_file():
            return d / CONFIG_REL
    raise ConfigError(f"symphony: no {CONFIG_REL} above {here}; pass --config or set SYMPHONY_CONFIG")


class Project:
    def __init__(self, config_path=None):
        self.config_path = find_config(config_path)
        self.root = self.config_path.parent.parent.parent
        with open(self.config_path, "rb") as f:
            c = tomllib.load(f)
        self.raw = c
        t = c.get("tracker", {})
        self.backend = t.get("backend", "gitea")
        if self.backend not in ("gitea", "github"):
            raise ConfigError(f"symphony: tracker.backend must be gitea or github, not {self.backend!r}")
        self.repo = t.get("repo") or _missing("tracker.repo")
        self.login = t.get("login", "")
        if self.backend == "gitea" and not self.login:
            raise ConfigError("symphony: tracker.login is required for gitea (pass it on every tea call)")
        lab = c.get("labels", {})
        self.ready = lab.get("ready", "ready-for-agent")
        self.blocking = lab.get("blocking", "blocking")
        s = c.get("state", {})
        self.state = Path(os.path.expanduser(s.get("dir") or _missing("state.dir")))
        self.ledger = self.state / s.get("ledger", "ledger.tsv")
        self.asked_marker = s.get("asked_marker", "QUESTIONS ON TICKET")
        b = c.get("brief", {})
        self.worktrees = self.root / b.get("worktrees", ".claude/worktrees")
        self.worktree_prefix = b.get("worktree_prefix", "orch-")
        self.brief_rules = self._opt_path(b.get("rules"))
        self.explore_notes = self._opt_path(b.get("explore_notes"))
        self.code_dir = self.root / b.get("code_dir", ".")

    def _opt_path(self, rel):
        return (self.root / rel) if rel else None

    # --- the tracker -------------------------------------------------------
    def api(self, path):
        """GET a REST path (no leading slash) and return the parsed JSON."""
        if self.backend == "gitea":
            cmd = ["tea", "api", "--login", self.login, path]
        else:
            cmd = ["gh", "api", path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"symphony: {' '.join(cmd[:2])} {path} failed: {r.stderr.strip()[:300]}")
        try:
            return json.loads(r.stdout or "null")
        except json.JSONDecodeError:
            raise SystemExit(f"symphony: {path} did not return JSON: {r.stdout[:200]!r}")

    def issue_api_cmd(self, path):
        """The shell command an agent runs to GET a path (for prompts)."""
        if self.backend == "gitea":
            return f"tea api --login {self.login} {path}"
        return f"gh api {path}"

    def open_issues(self, label=None):
        """Every open issue (not pull request), optionally with one label, paged."""
        out, page = [], 1
        per = 50 if self.backend == "gitea" else 100
        while True:
            q = f"repos/{self.repo}/issues?state=open&page={page}"
            q += f"&limit={per}&type=issues" if self.backend == "gitea" else f"&per_page={per}"
            if label:
                q += f"&labels={label}"
            batch = self.api(q) or []
            out += [i for i in batch if "pull_request" not in i or not i["pull_request"]]
            if len(batch) < per:
                return [normalise(i) for i in out]
            page += 1

    def issue(self, n):
        return normalise(self.api(f"repos/{self.repo}/issues/{n}"))

    def comments(self, n):
        out, page = [], 1
        per = 50
        while True:
            q = f"repos/{self.repo}/issues/{n}/comments?page={page}"
            q += f"&limit={per}" if self.backend == "gitea" else f"&per_page={per}"
            batch = self.api(q) or []
            out += batch
            if len(batch) < per:
                return out
            page += 1


def normalise(i):
    return {
        "number": int(i["number"]),
        "title": i.get("title", ""),
        "body": i.get("body") or "",
        "labels": [lab["name"] for lab in i.get("labels") or []],
        "assignees": [a["login"] for a in i.get("assignees") or []],
        "comments": i.get("comments", 0),
    }


def _missing(key):
    raise ConfigError(f"symphony: {key} is required in docs/agents/symphony.toml")


def warn(msg):
    print(msg, file=sys.stderr)
