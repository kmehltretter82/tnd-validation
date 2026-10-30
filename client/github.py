"""Thin wrapper around the `gh` CLI for the contributor side.

Authentication is delegated to `gh auth login` — Choir never sees the
contributor's GitHub credentials. If `gh` is not installed or not
authenticated, every call here raises `GitHubError`.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

from gate.state.lease_arbiter import (
    LeaseCommentsError,
    decode_lease_comment_pages,
    lease_comments_argv,
)


class GitHubFailureKind(Enum):
    """Machine-readable failure information available without parsing prose."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    TRANSPORT = "transport"
    REMOTE_PROTOCOL = "remote_protocol"
    LOCAL_SETUP = "local_setup"
    UNKNOWN = "unknown"


class GitHubError(RuntimeError):
    """A `gh` call failed, with conservative structured classification.

    ``message`` remains the human CLI diagnostic.  JSON callers never expose
    it directly: it can contain command arguments or paths.  ``kind`` is set
    only from stable evidence (gh's documented exit 4, an HTTP status, a
    timeout, or a malformed successful response); ambiguous failures stay
    ``UNKNOWN`` rather than being guessed from English stderr.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: GitHubFailureKind = GitHubFailureKind.UNKNOWN,
    ) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    assignees: list[str]


_GH_TIMEOUT_SECONDS = 60.0


def _run(cmd: list[str], *, check: bool = True) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=_GH_TIMEOUT_SECONDS,
        )
        return result.stdout
    except FileNotFoundError as e:
        raise GitHubError(
            "`gh` CLI not found in PATH — install it from https://cli.github.com",
            kind=GitHubFailureKind.LOCAL_SETUP,
        ) from e
    except subprocess.TimeoutExpired as e:
        raise GitHubError(
            "GitHub command timed out",
            kind=GitHubFailureKind.TRANSPORT,
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise GitHubError(
            f"command failed: {' '.join(cmd)}\n{stderr}",
            kind=classify_failure(e.returncode, stderr),
        ) from e


_HTTP_STATUS = re.compile(r"\bHTTP(?:/[0-9.]+)?\s+([1-5][0-9]{2})\b", re.IGNORECASE)


def classify_failure(returncode: int, diagnostic: str) -> GitHubFailureKind:
    """Classify a failed ``gh`` invocation using non-linguistic signals only.

    GitHub CLI documents exit status 4 as authentication required.  For API
    responses, its diagnostic includes an HTTP status.  Everything else is
    intentionally unknown: matching phrases such as "permission denied" or
    "connection reset" would turn changeable English into an API contract.
    """
    if returncode == 4:
        return GitHubFailureKind.AUTHENTICATION
    match = _HTTP_STATUS.search(diagnostic)
    if match is None:
        return GitHubFailureKind.UNKNOWN
    status = int(match.group(1))
    if status == 401:
        return GitHubFailureKind.AUTHENTICATION
    if status == 403:
        return GitHubFailureKind.AUTHORIZATION
    if status in {408, 425, 429} or 500 <= status < 600:
        return GitHubFailureKind.TRANSPORT
    return GitHubFailureKind.REMOTE_PROTOCOL


def _decode_json(raw: str, *, context: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise GitHubError(
            f"invalid JSON response from GitHub while {context}",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e


def _parse_issue(item: Any) -> Issue:
    try:
        if not isinstance(item, dict):
            raise TypeError("issue is not an object")
        number = item["number"]
        title = item["title"]
        body = item.get("body")
        state = item["state"]
        raw_labels = item.get("labels", [])
        raw_assignees = item.get("assignees", [])

        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise TypeError("issue number is not a positive integer")
        if not isinstance(title, str):
            raise TypeError("issue title is not a string")
        if body is not None and not isinstance(body, str):
            raise TypeError("issue body is neither a string nor null")
        if not isinstance(state, str) or state.lower() not in {"open", "closed"}:
            raise TypeError("issue state is invalid")
        if not isinstance(raw_labels, list) or not isinstance(raw_assignees, list):
            raise TypeError("issue labels or assignees are not arrays")

        labels = []
        for label in raw_labels:
            if not isinstance(label, dict) or not isinstance(label.get("name"), str):
                raise TypeError("issue label is invalid")
            labels.append(label["name"])

        assignees = []
        for user in raw_assignees:
            login = user.get("login") if isinstance(user, dict) else None
            if not isinstance(login, str) or not login:
                raise TypeError("issue assignee is invalid")
            assignees.append(login)

        return Issue(
            number=number,
            title=title,
            body=body or "",
            state=state.lower(),
            labels=labels,
            assignees=assignees,
        )
    except (KeyError, TypeError) as e:
        raise GitHubError(
            "invalid issue response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e


def current_user() -> str:
    """Return the GitHub login of the currently authenticated user."""
    out = _run(["gh", "api", "user"])
    try:
        login = _decode_json(out, context="reading the current user")["login"]
    except (KeyError, TypeError) as e:
        raise GitHubError(
            "invalid current-user response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e
    if not isinstance(login, str) or not login:
        raise GitHubError(
            "invalid current-user response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        )
    return login


def list_available_issues(repo: str) -> list[Issue]:
    """List open issues labeled `choir/available` in `repo`."""
    out = _run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            "choir/available",
            "--state",
            "open",
            "--json",
            "number,title,body,labels,assignees,state",
            "--limit",
            "200",
        ]
    )
    payload = _decode_json(out, context="listing issues")
    if not isinstance(payload, list):
        raise GitHubError(
            "invalid issue-list response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        )
    return [_parse_issue(item) for item in payload]


# There are deliberately no label or assignee *writers* here: spec D4 leaves
# a contributor with no repository write access, and GitHub refuses to assign
# a non-collaborator while silently dropping its label writes, which is worse
# than an error. The lifecycle label is the orchestrator's projection of the
# lease comments (`orchestrator/leases.py`); `Issue.assignees` is kept only
# because it comes free with the issue read — it is no longer the lease.


def get_issue(repo: str, number: int) -> Issue:
    out = _run(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,labels,assignees,state",
        ]
    )
    payload = _decode_json(out, context="reading an issue")
    if not isinstance(payload, dict):
        raise GitHubError(
            "invalid issue response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        )
    return _parse_issue(payload)


def post_comment(repo: str, number: int, body: str) -> None:
    _run(
        ["gh", "issue", "comment", str(number), "--repo", repo, "--body", body]
    )


def list_issue_comments(repo: str, number: int) -> list[dict[str, object]]:
    """Every comment on an issue, as `gate`'s shared projection returns it.

    Both the request (`lease_comments_argv`) and its interpretation
    (`lease_comments_from_api`) are `gate`'s, shared with the orchestrator's
    reader, so this wrapper's whole job is running the `gh` call.
    """
    try:
        return decode_lease_comment_pages(
            _run(["gh", *lease_comments_argv(repo, number)])
        )
    except LeaseCommentsError as error:
        raise GitHubError(
            f"invalid paginated issue-comment response: {error}",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        ) from error


def edit_comment(repo: str, comment_id: int, body: str) -> None:
    """Replace an existing issue comment's body (spec D4's heartbeat).

    A contributor may edit **their own** comment with no repository write
    access, which is what lets the heartbeat be an edit rather than a new
    comment every few minutes. GitHub answers someone else's comment with a
    403, surfacing here as `GitHubError`.

    `-f` (raw-field) rather than `-F`: `-F` applies type conversion and
    treats a leading `@` as a filename, and a comment body is neither.
    """
    _run(
        [
            "gh",
            "api",
            "--method",
            "PATCH",
            f"repos/{repo}/issues/comments/{comment_id}",
            "-f",
            f"body={body}",
        ]
    )


def get_pr_overview(repo: str, number: int) -> tuple[str, str]:
    """(author_login, state_lowercased) for a PR — one `gh` call."""
    out = _run(
        ["gh", "pr", "view", str(number), "--repo", repo, "--json", "author,state"]
    )
    data = _decode_json(out, context="reading a pull request")
    try:
        if not isinstance(data, dict) or not isinstance(data["author"], dict):
            raise TypeError("pull request is not an object")
        login = data["author"]["login"]
        raw_state = data["state"]
        if not isinstance(login, str) or not login:
            raise TypeError("pull-request author is invalid")
        if not isinstance(raw_state, str):
            raise TypeError("pull-request state is invalid")
        state = raw_state.lower()
        if state not in {"open", "closed", "merged"}:
            raise TypeError("pull-request state is invalid")
    except (KeyError, TypeError) as e:
        raise GitHubError(
            "invalid pull-request response from GitHub",
            kind=GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e
    return login, state


def post_pr_comment(repo: str, number: int, body: str) -> None:
    """Comment on a PR."""
    _run(["gh", "pr", "comment", str(number), "--repo", repo, "--body", body])


def get_file_contents(repo: str, path: str, ref: str | None = None) -> str | None:
    """Fetch a file's decoded text contents via the GitHub Contents API.

    Backs the client-side protocol pin fetch (design note 13 §6): returns
    `None` on ANY failure — 404, network/auth error, malformed JSON, a
    missing `content` field, or undecodable base64/UTF-8 — so callers can
    fail open rather than distinguish "can't read" from "stale".
    """
    endpoint = f"repos/{repo}/contents/{path}"
    if ref is not None:
        endpoint += f"?ref={ref}"
    try:
        out = _run(["gh", "api", endpoint])
    except GitHubError:
        return None
    try:
        data = json.loads(out)
        content = data["content"]
        return base64.b64decode(content).decode("utf-8")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None
