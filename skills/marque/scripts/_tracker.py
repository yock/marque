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
from pathlib import Path
from urllib.parse import quote


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
            if isinstance(data, dict) and ("number" in data or "iid" in data):
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


GRAPHQL_PARENT = (
    'query{project(fullPath:"%s"){workItems(iids:["%d"]){nodes{iid widgets{... on '
    'WorkItemWidgetHierarchy{parent{iid state webUrl}}}}}}}')


class GitLab(_Backend):
    """GitLab, through `glab api`. `login` names the env var holding the token."""

    # --- the one place a call is made --------------------------------------
    def _cmd(self, path):
        return (["glab", "api"] + (["--hostname", self.host] if self.host else [])
                + [path])

    def _env(self):
        """Send the orchestrator's token, named by `login`, with every call.

        glab has no per-call user: the token travels in the environment only, never
        in argv or an error message. `GITLAB_HOST` decides which host accepts it.
        """
        if not self.login:
            return None
        value = os.environ.get(self.login)
        if not value:
            raise TrackerError(["glab", "api"],
                               f"--login names the variable {self.login}, which is not set")
        env = dict(os.environ)
        env["GITLAB_TOKEN"] = value
        if self.host:
            env["GITLAB_HOST"] = self.host
        return env

    # --- issues -------------------------------------------------------------
    def open_issues(self, label=None):
        """Every open issue, paged; optionally only those with `label`."""
        out, page = [], 1
        while True:
            q = f"projects/{self.project}/issues?state=opened&scope=all"
            if label:
                q += f"&labels={label}"
            q += f"&per_page=100&page={page}"
            batch = self._call(q, "list")
            out += batch
            if len(batch) < 100:
                return [self._normalise(i) for i in out]
            page += 1

    def issue(self, n):
        """One ticket, or None when GitLab answers 404."""
        try:
            data = self._call(f"projects/{self.project}/issues/{n}", "issue")
        except TrackerError as e:
            if "HTTP 404" in e.reason:
                return None
            raise
        return self._normalise(data)

    def comments(self, n):
        out, page = [], 1
        while True:
            batch = self._call(
                f"projects/{self.project}/issues/{n}/notes"
                f"?sort=asc&order_by=created_at&per_page=100&page={page}", "list")
            out += [{"body": c.get("body") or ""} for c in batch if not c.get("system")]
            if len(batch) < 100:
                return out
            page += 1

    def dependencies(self, n):
        """The links that block `n`: `is_blocked_by`, not `blocks`."""
        batch = self._call(f"projects/{self.project}/issues/{n}/links", "list")
        return [self._ref(i) for i in batch if i.get("link_type") == "is_blocked_by"]

    def native_parent(self, ticket):
        """The parent from one GraphQL call: GitLab has no REST parent."""
        n = ticket["number"]
        cmd = self._cmd("graphql") + ["-f", "query=" + GRAPHQL_PARENT % (self.repo, n)]
        data = self._fetch(cmd, "dict")
        if data.get("errors"):
            raise TrackerError(cmd, _preview(data["errors"]))
        project = (data.get("data") or {}).get("project") or {}
        nodes = (project.get("workItems") or {}).get("nodes") or []
        for node in nodes:
            for widget in node.get("widgets") or []:
                parent = (widget or {}).get("parent")
                if not parent:
                    continue
                number = int(parent["iid"])
                repo = self._url_repo(parent.get("webUrl")) or self.repo
                raw = f"#{number}" if repo == self.repo else f"{repo}#{number}"
                return {"number": number, "repo": repo,
                        "state": _state(parent.get("state")), "raw": raw}
        return None

    # --- shaping ------------------------------------------------------------
    @property
    def project(self):
        """The project id GitLab's REST paths use: the path, URL-encoded."""
        return quote(self.repo, safe="")

    @staticmethod
    def _url_repo(url):
        """`o/r` from a work item's web URL: the path before `/-/`."""
        m = re.search(r"https?://[^/]+/(.+?)/-/", url or "")
        return m.group(1) if m else None

    def _normalise(self, i):
        return {
            "number": int(i["iid"]),
            "title": i.get("title") or "",
            "state": _state(i.get("state")) or "open",
            "labels": list(i.get("labels") or []),
            "assignees": [a.get("username") for a in i.get("assignees") or []],
            "body": i.get("description") or "",
            "comments": int(i.get("user_notes_count") or 0),
            "blockers": None,
            "parent": None,
        }

    def _ref(self, i):
        number = int(i["iid"])
        full = ((i.get("references") or {}).get("full")) or f"{self.repo}#{number}"
        repo = full.split("#", 1)[0]
        raw = f"#{number}" if repo == self.repo else f"{repo}#{number}"
        return {"number": number, "repo": repo, "state": _state(i.get("state")), "raw": raw}


LOCAL_STATUS = re.compile(r"(?mi)^[ \t]*(?:\*\*)?Status:(?:\*\*)?[ \t]*(.*)$")
LOCAL_BLOCKED = re.compile(r"(?mi)^[ \t]*(?:\*\*)?Blocked by:(?:\*\*)?[ \t]*(.*)$")
LOCAL_TITLE = re.compile(r"(?m)^#[ \t]*(\d+):[ \t]*(.*)$")
LOCAL_COMMENTS = re.compile(r"(?ms)^#{1,6}[ \t]*Comments[ \t]*\n(.*)")
LOCAL_NUMBER = re.compile(r"^\d+")
LOCAL_BARE = re.compile(r"^#?(\d+)$")

# The `Status:` values that mean the ticket is done; wayfinder also says `resolved`.
LOCAL_CLOSED = {"resolved", "closed", "done", "wontfix"}


class Local(_Backend):
    """Upstream's local tracker: one to-tickets markdown file per ticket, no CLI.

    `repo` is the feature directory (`.scratch/<feature>`); tickets are the numbered
    files under its `issues/`. The file is read, never written: the `Status:` line is
    the ticket's label, `claimed` is its assignee, and `resolved` (or `closed`, `done`,
    `wontfix`) closes it. `Blocked by:` names the gating tickets by number or title.
    """

    def __init__(self, repo, login=None, host=None):
        super().__init__(repo, login, host)
        self._records_cache = None

    # --- issues -------------------------------------------------------------
    def open_issues(self, label=None):
        """Every open ticket, in file-name order; optionally only those with `label`."""
        return [t for _, t, _ in self._records().values()
                if t["state"] == "open" and (label is None or label in t["labels"])]

    def issue(self, n):
        """One ticket in any state, or None when no numbered file has it."""
        record = self._records().get(n)
        return record[1] if record else None

    def comments(self, n):
        """The text under `## Comments`, as one comment (`comments` is 0 or 1)."""
        record = self._records().get(n)
        return [{"body": record[2]}] if record and record[2] else []

    def dependencies(self, n):
        """The blockers from the `Blocked by:` line, as Refs."""
        record = self._records().get(n)
        return list(record[1]["blockers"]) if record else []

    def native_parent(self, ticket):
        """Local tickets carry no number for their parent: they are parentless."""
        return None

    # --- reading ------------------------------------------------------------
    def _records(self):
        """Every numbered ticket file, by number; a duplicate number is an error."""
        if self._records_cache is not None:
            return self._records_cache
        folder = Path(self.repo) / "issues"
        if not folder.is_dir():
            raise TrackerError([str(folder)], "no such directory of ticket files")
        records = {}
        for path in sorted(folder.glob("*.md")):
            if not LOCAL_NUMBER.match(path.name):
                continue        # not a numbered ticket file
            ticket, comment = self._parse(path)
            if ticket["number"] in records:
                raise TrackerError(
                    [str(path)], f"ticket #{ticket['number']} is also "
                    f"{records[ticket['number']][0].name}")
            records[ticket["number"]] = (path, ticket, comment)
        self._records_cache = records
        return records

    def _parse(self, path):
        """One ticket file as a normalised ticket, plus its `## Comments` text."""
        text = path.read_text(encoding="utf-8")
        title = LOCAL_TITLE.search(text)
        status = LOCAL_STATUS.search(text)
        status = status.group(1).strip().lower() if status else ""
        comments = LOCAL_COMMENTS.search(text)
        comment = comments.group(1).strip() if comments else ""
        ticket = {
            "number": int(LOCAL_NUMBER.match(path.name).group(0)),
            "title": title.group(2).strip() if title else path.stem,
            "state": "closed" if status in LOCAL_CLOSED else "open",
            "labels": [status],
            "assignees": ["local"] if status == "claimed" else [],
            # The line is the native relation below; leaving it in the body too would
            # make the frontier count (and report) it twice.
            "body": LOCAL_BLOCKED.sub("", text),
            "comments": 1 if comment else 0,
            "blockers": self._blockers(text),
            "parent": None,
        }
        return ticket, comment

    def _blockers(self, text):
        """The `Blocked by:` value as Refs: bare numbers resolve, titles do not."""
        line = LOCAL_BLOCKED.search(text)
        if line is None or line.group(1).strip().lower().startswith("none"):
            return []
        refs = []
        for item in line.group(1).split(","):
            item = item.strip()
            if not item:
                continue
            number = LOCAL_BARE.match(item)
            if number:
                refs.append({"number": int(number.group(1)), "repo": self.repo,
                             "state": None, "raw": item})
            else:
                # A title names a ticket this backend cannot number, so the frontier
                # must report it as unparseable rather than silently unblocking.
                refs.append({"number": None, "repo": None, "state": None, "raw": item})
        return refs


BACKENDS = ("gitea", "github", "gitlab", "local")


def backend(name, repo, login=None, host=None):
    """The tracker for `name`."""
    if name == "gitea":
        return Gitea(repo, login)
    if name == "github":
        return GitHub(repo, login, host)
    if name == "gitlab":
        return GitLab(repo, login, host)
    if name == "local":
        return Local(repo)
    raise TrackerError(["tea", "api"], f"{name} is not built yet")
