"""Identify and maintain the contributor's fork of a project repo (spec D4).

Under D4 a contributor has no write access, so the task branch is pushed to
their own fork and the PR is opened from there. This module owns the one
question in that path that is harder than it looks: *which repository is my
fork of this project?*

**Composing `<login>/<upstream-name>` is wrong, and wrong quietly.** Three
ways, all ordinary rather than exotic:

- GitHub appends a suffix when the name is taken, so forking `org/project`
  while you already own a `project` gives you `you/project-1`.
- A fork can be renamed or transferred after it is created.
- A contributor may simply own an unrelated repository by that name — and
  then the composed name resolves to a real repository that exists, passes
  an existence check, and is not the fork. The task branch gets pushed into
  it and the PR is opened against a head that does not exist.

So the fork is **looked up, never composed**: one GraphQL query for the
authenticated user's fork of a given upstream, which answers with the fork's
true `nameWithOwner` whatever it happens to be called. `client.submit` then
points its `choir-fork` remote at that answer with `set-url`, so a rename
between one task and the next self-heals rather than pushing at a stale URL.

**One fork per project, reused forever.** `ensure_fork` creates only when the
lookup finds nothing, so a contributor working ten tasks on one project forks
once and pushes ten branches to it. That matters beyond tidiness: the
workspace is a `git worktree` of the per-project store (2026-06-20 decision),
so the remote lives in the store's config and is shared by every task in the
project — one contributor, one fork, one remote.
"""

from __future__ import annotations

import json
import re
import subprocess
import time

from client import github as gh
from client._subprocess import ToolNotFound, run


class ForkError(RuntimeError):
    """Could not determine, create, or reach the contributor's fork."""

    def __init__(
        self,
        message: str,
        *,
        github_failure_kind: gh.GitHubFailureKind | None = None,
    ) -> None:
        super().__init__(message)
        self.github_failure_kind = github_failure_kind


_GH_TIMEOUT_SECONDS = 60.0
_OWNER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,99})")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}")


def _run_gh(args: list[str]):
    """Run gh with the same bounded wait as the primary GitHub wrapper."""
    try:
        return run(["gh", *args], timeout=_GH_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        raise ForkError(
            "GitHub command timed out",
            github_failure_kind=gh.GitHubFailureKind.TRANSPORT,
        ) from e


# One GraphQL query, not a scan of `/repos/{o}/{r}/forks`: that endpoint
# paginates over *every* fork of the upstream, which for a popular project
# is thousands of pages to find one row. `ownerAffiliations: [OWNER]`
# restricts the connection to forks the viewer owns, so the answer arrives
# in a single request no matter how many forks exist.
_FORK_QUERY = """
query($owner:String!,$name:String!){
  repository(owner:$owner,name:$name){
    forks(first:1, affiliations:[OWNER], ownerAffiliations:[OWNER]){
      nodes{ nameWithOwner }
    }
  }
}
"""


def split_repo(repo: str) -> tuple[str, str]:
    """`"owner/name"` → `("owner", "name")`, or raise on a malformed value."""
    owner, _, name = repo.partition("/")
    if (
        _OWNER_RE.fullmatch(owner) is None
        or _REPOSITORY_RE.fullmatch(name) is None
        or "/" in name
    ):
        raise ForkError(f"expected a repo as 'owner/name', got {repo!r}")
    return owner, name


def authenticated_login() -> str:
    """The login `gh` is authenticated as."""
    try:
        return gh.current_user()
    except gh.GitHubError as e:
        raise ForkError(
            str(e),
            github_failure_kind=e.kind,
        ) from e


def owns_upstream(repo: str, login: str) -> bool:
    """Whether `login` is the account that owns `repo` itself.

    Load-bearing because **GitHub cannot fork a repository into the account
    that already owns it.** An overseer proving a task on their own project
    — explicitly a supported shape since the 2026-07-09 self-review decision
    — therefore has no fork to push to, and never will. `client.submit`
    checks this first and pushes to `origin` in that one case, where the
    contributor's own write access is what makes it work.

    Compared case-insensitively: GitHub logins are case-insensitive, and a
    `gh` answer of `YidiQ7` against an upstream spelled `yidiq7/…` must not
    read as a different account and send the owner down the fork path.
    """
    owner, _ = split_repo(repo)
    return owner.casefold() == login.casefold()


def find_fork(repo: str) -> str | None:
    """The authenticated user's fork of `repo` as `owner/name`, or `None`.

    Returns whatever the fork is *actually* called — including a `-1` suffix
    GitHub added at creation, or a name the contributor has since changed.
    """
    owner, name = split_repo(repo)
    try:
        result = _run_gh(
            [
                "api", "graphql",
                "-f", f"query={_FORK_QUERY}",
                "-F", f"owner={owner}",
                "-F", f"name={name}",
            ],
        )
    except ToolNotFound as e:
        raise ForkError(
            str(e),
            github_failure_kind=gh.GitHubFailureKind.LOCAL_SETUP,
        ) from e
    if not result.ok:
        raise ForkError(
            f"could not look up your fork of {repo}:\n{result.stderr.strip()}",
            github_failure_kind=gh.classify_failure(
                result.returncode, result.stderr
            ),
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e
    try:
        data = payload["data"]
        repository = data["repository"]
        forks = repository["forks"]
        nodes = forks["nodes"]
        if not all(
            isinstance(value, dict)
            for value in (payload, data, repository, forks)
        ):
            raise TypeError("fork response objects are invalid")
    except (KeyError, TypeError) as e:
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e
    if not isinstance(nodes, list):
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        )
    if not nodes:
        return None
    if not isinstance(nodes[0], dict):
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        )
    full_name = nodes[0].get("nameWithOwner")
    if not isinstance(full_name, str) or not full_name:
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        )
    try:
        split_repo(full_name)
    except ForkError as e:
        raise ForkError(
            f"unreadable response looking up your fork of {repo}",
            github_failure_kind=gh.GitHubFailureKind.REMOTE_PROTOCOL,
        ) from e
    return full_name


def ensure_fork(
    repo: str,
    *,
    poll_attempts: int = 12,
    poll_delay: float = 2.5,
) -> str:
    """Return the contributor's fork of `repo`, creating it if absent.

    Idempotent: the lookup runs first, so an existing fork is reused and no
    creation is attempted. Only a contributor's genuinely first task on a
    project reaches `gh repo fork`.

    **Forking is asynchronous.** The API accepts the request and copies the
    repository in the background, so the fork can be un-pushable for a few
    seconds after the call returns — the reason for the poll rather than an
    immediate push. `gh repo fork`'s own exit code is not trusted for the
    same reason it was not trusted before: it is chatty on the
    already-exists path and its status has moved across versions. The
    lookup is the source of truth either way.
    """
    existing = find_fork(repo)
    if existing is not None:
        return existing

    try:
        created = _run_gh(
            ["repo", "fork", repo, "--clone=false", "--remote=false"]
        )
    except ToolNotFound as e:
        raise ForkError(
            str(e),
            github_failure_kind=gh.GitHubFailureKind.LOCAL_SETUP,
        ) from e

    for attempt in range(poll_attempts):
        found = find_fork(repo)
        if found is not None:
            return found
        if attempt < poll_attempts - 1:
            time.sleep(poll_delay)

    detail = (created.stderr or created.stdout or "").strip()
    raise ForkError(
        f"forked {repo} but the fork did not appear within "
        f"{poll_attempts * poll_delay:.0f}s"
        + (f":\n{detail}" if detail else ".")
        + "\nRe-run `choir submit` — the fork may just be slow to materialize."
    )


def sync_fork(fork: str, *, branch: str | None = None) -> bool:
    """Fast-forward `fork`'s default branch to its parent. Best-effort.

    Not required for correctness — a branch based on an upstream commit the
    fork has never seen pushes fine, and the PR's merge base is computed
    from the commits, not from the fork's default branch. It is here for
    cost and legibility: pushing to a fork that is months behind sends the
    whole intervening history as loose objects, which on a Mathlib-scale
    project is the difference between a fast push and a very slow one, and
    a synced fork shows a clean "N commits ahead" instead of a confusing
    "ahead and behind" on the PR page.

    Returns whether the sync succeeded. A failure is deliberately swallowed
    by the caller: this must never be the reason a finished proof cannot be
    submitted. `gh repo sync` fast-forwards and refuses to clobber, so a
    fork whose default branch has diverged (a contributor committed to it)
    fails here and is left exactly as it was.
    """
    args = ["gh", "repo", "sync", fork]
    if branch:
        args.extend(["--branch", branch])
    try:
        return run(args, timeout=_GH_TIMEOUT_SECONDS).ok
    except (ToolNotFound, subprocess.TimeoutExpired):
        return False
