"""The tracker core Marque's scripts share: one normalised ticket, one backend at a time.

Every backend reaches its tracker through the CLI's raw REST passthrough (`tea api`,
`gh api`, `glab api`). Calls are made one at a time on purpose: parallel `tea api`
calls were seen to return intermittent auth errors.

A normalised ticket is a plain dict:
    number:int, title:str, state:"open"|"closed", labels:[str], assignees:[str],
    body:str, comments:int, blockers:[Ref] or None, parent:Ref or None
`blockers` and `parent` are the backend's *native* relations: None means the backend
has no such relation, [] means native and empty. A Ref is
    {"number": int|None, "repo": "owner/name", "state": "open"|"closed"|None, "raw": str}

No CLI here: scripts import this module and own their own argument parsing.
"""
import json
import os
import re
import subprocess


class TrackerError(Exception):
    """A tracker call that failed. `cmd` is the exact command line, for the caller's report."""

    def __init__(self, cmd, reason):
        self.cmd = list(cmd)
        self.reason = reason
        super().__init__(f"{' '.join(self.cmd)} failed: {reason}")


def _preview(data):
    text = json.dumps(data) if not isinstance(data, str) else data
    return text[:200]


ACTIVE = {"open": "open", "opened": "open", "OPEN": "open"}
CLOSED = {"closed": "closed", "CLOSED": "closed"}


def _state(value):
    """The normalised state for a tracker's spelling of it."""
    return ACTIVE.get(value) or CLOSED.get(value)


class _Backend:
    """What every backend shares: one call at a time, JSON only, a shape check."""

    def __init__(self, repo, login=None, host=None):
        self.repo = repo
        self.login = login
        self.host = host

    def _cmd(self, path):
        raise NotImplementedError

    def _env(self):
        """The environment for a call; None inherits the caller's."""
        return None

    def _fetch(self, cmd, expect):
        """Run `cmd` and return its JSON, refusing anything but the expected shape."""
        r = subprocess.run(cmd, capture_output=True, text=True, env=self._env())
        if r.returncode != 0:
            raise TrackerError(cmd, (r.stderr.strip() or f"exit {r.returncode}")[:300])
        try:
            data = json.loads(r.stdout or "null")
        except json.JSONDecodeError:
            raise TrackerError(cmd, f"did not return JSON: {r.stdout[:200]!r}")
        if expect == "list" and not isinstance(data, list):
            raise TrackerError(cmd, f"expected a list, got {_preview(data)}")
        if expect == "dict" and not isinstance(data, dict):
            raise TrackerError(cmd, f"expected an object, got {_preview(data)}")
        if expect == "issue":
            if isinstance(data, dict) and "number" in data:
                return data
            if (isinstance(data, dict) and "not found" in str(data.get("message", "")).lower()):
                return data
            raise TrackerError(cmd, f"expected an issue, got {_preview(data)}")
        return data

    def _call(self, path, expect):
        return self._fetch(self._cmd(path), expect)


class Gitea(_Backend):
    """Gitea, through `tea api`. `login` names the `tea` login to use, when given."""

    def _cmd(self, path):
        return (["tea", "api"] + (["--login", self.login] if self.login else [])
                + [path])

    # --- issues -------------------------------------------------------------
    def open_issues(self, label=None):
        """Every open issue, PRs dropped, paged; optionally only those with `label`."""
        out, page = [], 1
        while True:
            q = f"repos/{self.repo}/issues?state=open&page={page}&limit=50&type=issues"
            if label:
                q += f"&labels={label}"
            batch = self._call(q, "list")
            out += [i for i in batch if not i.get("pull_request")]
            if len(batch) < 50:
                return [self._normalise(i) for i in out]
            page += 1

    def issue(self, n):
        """One ticket, or None when the tracker says it does not exist."""
        data = self._call(f"repos/{self.repo}/issues/{n}", "issue")
        if "number" not in data:
            return None
        return self._normalise(data)

    def comments(self, n):
        out, page = [], 1
        while True:
            batch = self._call(f"repos/{self.repo}/issues/{n}/comments?page={page}&limit=50", "list")
            out += [{"body": c.get("body") or ""} for c in batch]
            if len(batch) < 50:
                return out
            page += 1

    def dependencies(self, n):
        """The native blockers of `n`, as Refs."""
        batch = self._call(f"repos/{self.repo}/issues/{n}/dependencies", "list")
        return [self._ref(i) for i in batch]

    def native_parent(self, ticket):
        """Gitea has no sub-issues: there is never a native parent."""
        return None

    # --- shaping ------------------------------------------------------------
    def _normalise(self, i):
        return {
            "number": int(i["number"]),
            "title": i.get("title") or "",
            "state": i.get("state") or "open",
            "labels": [lab.get("name") for lab in i.get("labels") or []],
            "assignees": [a.get("login") for a in i.get("assignees") or []],
            "body": i.get("body") or "",
            "comments": int(i.get("comments") or 0),
            "blockers": None,
            "parent": None,
        }

    def _ref(self, i):
        number = int(i["number"])
        repo = ((i.get("repository") or {}).get("full_name")) or self.repo
        raw = f"#{number}" if repo == self.repo else f"{repo}#{number}"
        return {"number": number, "repo": repo, "state": i.get("state"), "raw": raw}


PARENT_URL = re.compile(r"repos/([^/]+/[^/]+)/issues/(\d+)")


class GitHub(_Backend):
    """GitHub, through `gh api`. `login` names the gh user whose token signs every call."""

    def __init__(self, repo, login=None, host=None):
        super().__init__(repo, login, host)
        self._token = None

    # --- the one place a call is made --------------------------------------
    def _cmd(self, path):
        return (["gh", "api"] + (["--hostname", self.host] if self.host else [])
                + [path])

    def _env(self):
        """Sign every call with the `--login` user's token, fetched once.

        The token travels in the environment only: never in argv, never in an error.
        """
        if not self.login:
            return None
        if self._token is None:
            cmd = ["gh", "auth", "token", "--user", self.login]
            if self.host:
                cmd += ["--hostname", self.host]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise TrackerError(
                    cmd, (r.stderr.strip() or f"exit {r.returncode}")[:300])
            self._token = r.stdout.strip()
        env = dict(os.environ)
        env["GH_TOKEN"] = self._token
        if self.host and self.host != "github.com":
            env["GH_ENTERPRISE_TOKEN"] = self._token
        return env

    # --- issues -------------------------------------------------------------
    def open_issues(self, label=None):
        """Every open issue, PRs dropped, paged; optionally only those with `label`."""
        out, page = [], 1
        while True:
            q = f"repos/{self.repo}/issues?state=open"
            if label:
                q += f"&labels={label}"
            q += f"&per_page=100&page={page}"
            batch = self._call(q, "list")
            out += [i for i in batch if not i.get("pull_request")]
            if len(batch) < 100:
                return [self._normalise(i) for i in out]
            page += 1

    def issue(self, n):
        """One ticket, or None when GitHub answers 404."""
        try:
            data = self._call(f"repos/{self.repo}/issues/{n}", "issue")
        except TrackerError as e:
            if "HTTP 404" in e.reason:
                return None
            raise
        return self._normalise(data)

    def comments(self, n):
        out, page = [], 1
        while True:
            batch = self._call(
                f"repos/{self.repo}/issues/{n}/comments?per_page=100&page={page}", "list")
            out += [{"body": c.get("body") or ""} for c in batch]
            if len(batch) < 100:
                return out
            page += 1

    def dependencies(self, n):
        """The native blockers of `n`, as Refs."""
        batch = self._call(f"repos/{self.repo}/issues/{n}/dependencies/blocked_by", "list")
        return [self._ref(i) for i in batch]

    def native_parent(self, ticket):
        """The parent from the ticket's `parent_issue_url`, with no extra call."""
        url = ticket.get("parent_issue_url")
        if not url:
            return None
        m = PARENT_URL.search(url)
        if not m:
            return None
        repo, number = m.group(1), int(m.group(2))
        raw = f"#{number}" if repo == self.repo else f"{repo}#{number}"
        return {"number": number, "repo": repo, "state": None, "raw": raw}

    # --- shaping ------------------------------------------------------------
    def _normalise(self, i):
        return {
            "number": int(i["number"]),
            "title": i.get("title") or "",
            "state": i.get("state") or "open",
            "labels": [lab.get("name") for lab in i.get("labels") or []],
            "assignees": [a.get("login") for a in i.get("assignees") or []],
            "body": i.get("body") or "",
            "comments": int(i.get("comments") or 0),
            "blockers": None,
            "parent": None,
            "parent_issue_url": i.get("parent_issue_url"),
        }

    def _ref(self, i):
        number = int(i["number"])
        repo = ((i.get("repository") or {}).get("full_name")) or self.repo
        raw = f"#{number}" if repo == self.repo else f"{repo}#{number}"
        return {"number": number, "repo": repo, "state": i.get("state"), "raw": raw}


BACKENDS = ("gitea", "github")


def backend(name, repo, login=None, host=None):
    """The tracker for `name`."""
    if name == "gitea":
        return Gitea(repo, login)
    if name == "github":
        return GitHub(repo, login, host)
    raise TrackerError(["tea", "api"], f"{name} is not built yet")
