"""The tracker core Marque's scripts share: one normalised ticket, one backend at a time.

Every backend reaches its tracker through the CLI's raw REST passthrough (`tea api`,
and later `gh api`, `glab api`). Calls are made one at a time on purpose: parallel
`tea api` calls were seen to return intermittent auth errors.

A normalised ticket is a plain dict:
    number:int, title:str, state:"open"|"closed", labels:[str], assignees:[str],
    body:str, comments:int, blockers:[Ref] or None, parent:Ref or None
`blockers` and `parent` are the backend's *native* relations: None means the backend
has no such relation, [] means native and empty. A Ref is
    {"number": int|None, "repo": "owner/name", "state": "open"|"closed"|None, "raw": str}

No CLI here: scripts import this module and own their own argument parsing.
"""
import json
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


class Gitea:
    """Gitea, through `tea api`. `login` names the `tea` login to use, when given."""

    def __init__(self, repo, login=None):
        self.repo = repo
        self.login = login

    # --- the one place a call is made --------------------------------------
    def _call(self, path, expect):
        """GET `path` and return its JSON, refusing anything but the expected shape.

        `tea api` exits 0 on HTTP errors, so a call has also failed when the output
        is not JSON, or is a `message` object where a list or an issue was expected.
        """
        cmd = ["tea", "api"] + (["--login", self.login] if self.login else []) + [path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise TrackerError(cmd, (r.stderr.strip() or f"exit {r.returncode}")[:300])
        try:
            data = json.loads(r.stdout or "null")
        except json.JSONDecodeError:
            raise TrackerError(cmd, f"did not return JSON: {r.stdout[:200]!r}")
        if expect == "list" and not isinstance(data, list):
            raise TrackerError(cmd, f"expected a list, got {_preview(data)}")
        if expect == "issue":
            if isinstance(data, dict) and "number" in data:
                return data
            if (isinstance(data, dict) and "not found" in str(data.get("message", "")).lower()):
                return data
            raise TrackerError(cmd, f"expected an issue, got {_preview(data)}")
        return data

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

    def native_parent(self, n):
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


def backend(name, repo, login=None):
    """The tracker for `name`. Only gitea is built so far."""
    if name == "gitea":
        return Gitea(repo, login)
    raise TrackerError(["frontier.py", "--backend", name],
                       f"{name} is not built yet; only gitea is")
