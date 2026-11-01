"""Repository-tracked governance for TND reviewers, admins, and superadmin.

On a personal GitHub account repository, collaborator roles cannot distinguish
proof reviewers from near-equal admins or the superadmin.  Maintained code on
``main`` therefore reads ``.choir/governance.json`` from the trusted base tree
and enforces role and review rules before any merge or maintainer-mode check.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
GOVERNANCE_PATH = PROJECT / ".choir/governance.json"
DEFAULT_SUPERADMIN = "kmehltretter82"
GITHUB_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
MAINTAINER_PR_MARKER = "tnd-pr-mode: maintainer"
SUPERADMIN_ONLY_PATHS = frozenset({
    ".choir/governance.json",
    ".choir/certification.json",
})


class GovernanceError(ValueError):
    """A governance configuration or authorization rule was violated."""


@dataclass(frozen=True)
class GovernancePolicy:
    superadmin: str
    admins: frozenset[str]
    reviewers: frozenset[str]

    def is_superadmin(self, login: str, *, repo: str | None = None) -> bool:
        if not isinstance(login, str) or not login:
            return False
        folded = login.casefold()
        if folded == self.superadmin.casefold():
            return True
        if repo and "/" in repo:
            owner = repo.split("/", 1)[0]
            if folded == owner.casefold() and self.superadmin == DEFAULT_SUPERADMIN:
                return True
        return False

    def is_maintainer(self, login: str, *, repo: str | None = None) -> bool:
        if self.is_superadmin(login, repo=repo):
            return True
        if not isinstance(login, str) or not login:
            return False
        folded = login.casefold()
        return any(folded == admin.casefold() for admin in self.admins)

    def is_reviewer(self, login: str, *, repo: str | None = None) -> bool:
        if self.is_maintainer(login, repo=repo):
            return True
        if not isinstance(login, str) or not login:
            return False
        folded = login.casefold()
        return any(folded == reviewer.casefold() for reviewer in self.reviewers)


def _validate_login_list(value: Any, field: str) -> frozenset[str]:
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError(f"governance {field} must be a bounded list of GitHub logins")
    seen: set[str] = set()
    result: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not GITHUB_LOGIN.fullmatch(item):
            raise ValueError(f"governance {field} contains an invalid GitHub login")
        folded = item.casefold()
        if folded in seen:
            raise ValueError(f"governance {field} contains duplicate GitHub logins")
        seen.add(folded)
        result.add(item)
    return frozenset(result)


def validate_governance(
    raw: Any, *, expected_superadmin: str | None = DEFAULT_SUPERADMIN,
) -> GovernancePolicy:
    """Validate the exact governance schema and preserve the superadmin pin."""
    expected_keys = {"schema_version", "superadmin", "admins", "reviewers"}
    if (
        not isinstance(raw, Mapping)
        or set(raw) != expected_keys
        or isinstance(raw.get("schema_version"), bool)
        or raw.get("schema_version") != 1
    ):
        raise ValueError("governance policy must match schema_version 1")
    superadmin = raw.get("superadmin")
    if not isinstance(superadmin, str) or not GITHUB_LOGIN.fullmatch(superadmin):
        raise ValueError("governance superadmin must be a valid GitHub login")
    if (
        expected_superadmin is not None
        and superadmin.casefold() != expected_superadmin.casefold()
    ):
        raise ValueError(f"governance superadmin must remain {expected_superadmin}")
    admins = _validate_login_list(raw.get("admins"), "admins")
    reviewers = _validate_login_list(raw.get("reviewers"), "reviewers")
    if any(admin.casefold() == superadmin.casefold() for admin in admins):
        raise ValueError("governance superadmin must not be duplicated in admins")
    if any(reviewer.casefold() == superadmin.casefold() for reviewer in reviewers):
        raise ValueError("governance superadmin must not be duplicated in reviewers")
    if {a.casefold() for a in admins} & {r.casefold() for r in reviewers}:
        raise ValueError("governance login must not appear in both admins and reviewers")
    return GovernancePolicy(superadmin=superadmin, admins=admins, reviewers=reviewers)


def load_governance(
    path: Path | None = None,
    *,
    expected_superadmin: str | None = DEFAULT_SUPERADMIN,
) -> GovernancePolicy:
    target = GOVERNANCE_PATH if path is None else path
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("governance policy is missing or malformed") from error
    return validate_governance(raw, expected_superadmin=expected_superadmin)


def has_maintainer_marker(body: str) -> bool:
    """Whether a PR body explicitly declares maintainer PR mode on its own line."""
    return isinstance(body, str) and any(
        line.strip() == MAINTAINER_PR_MARKER for line in body.splitlines()
    )


def validate_maintainer_pr_contract(
    *,
    repo: str,
    head_repo: str,
    base_branch: str,
    author: str,
    body: str,
    linked_issues: Sequence[int],
    files: Sequence[str],
    governance: GovernancePolicy | None = None,
) -> None:
    """Fail closed unless a maintainer-marked PR meets every same-repo/role rule."""
    policy = load_governance() if governance is None else governance
    if not has_maintainer_marker(body):
        raise ValueError("PR does not declare tnd-pr-mode: maintainer")
    if base_branch != "main":
        raise ValueError("TND maintainer PRs must target main")
    if not head_repo or head_repo != repo:
        raise ValueError("TND maintainer PRs must originate from a same-repository branch")
    if linked_issues:
        raise ValueError("TND maintainer PRs must not close a Choir task issue")
    if not policy.is_maintainer(author, repo=repo):
        raise ValueError(f"PR author {author!r} is not an authorized TND maintainer")
    if not files or any(
        not path or any(part in {"", ".", ".."} for part in path.split("/"))
        for path in files
    ):
        raise ValueError("TND maintainer PR has an empty or invalid changed-file list")


def require_review_authorization(
    *,
    pr_author: str,
    actor: str | None,
    reviews: Sequence[Mapping[str, Any]],
    head_sha: str,
    is_maintainer_pr: bool,
    files: Sequence[str],
    repo: str,
    governance: GovernancePolicy | None = None,
) -> None:
    """Enforce reviewer, admin, and superadmin approval rules before merging."""
    policy = load_governance() if governance is None else governance
    if actor is not None and not policy.is_reviewer(actor, repo=repo):
        raise ValueError(f"merge actor {actor!r} is not an authorized TND reviewer or maintainer")
    if is_maintainer_pr and actor is not None and not policy.is_maintainer(actor, repo=repo):
        raise ValueError(f"merge actor {actor!r} is not an authorized TND maintainer")

    latest_state: dict[str, tuple[str, str]] = {}
    for review in reviews:
        if not isinstance(review, Mapping):
            raise ValueError("invalid GitHub pull-request review record")
        user = review.get("user")
        login = user.get("login") if isinstance(user, Mapping) else None
        state = review.get("state")
        commit_id = review.get("commit_id") or ""
        if not isinstance(login, str) or not login or not isinstance(state, str):
            raise ValueError("GitHub pull-request review has invalid user or state")
        if state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest_state[login.casefold()] = (state, str(commit_id))

    for folded_login, (state, _commit_id) in latest_state.items():
        if state == "CHANGES_REQUESTED" and policy.is_reviewer(folded_login, repo=repo):
            raise ValueError("TND merge blocked by an active CHANGES_REQUESTED review")

    touches_superadmin_paths = any(path in SUPERADMIN_ONLY_PATHS for path in files)
    if touches_superadmin_paths:
        if not is_maintainer_pr:
            raise ValueError("protected governance or certification paths require a maintainer PR")
        superadmin_approved = any(
            policy.is_superadmin(folded, repo=repo)
            and state == "APPROVED"
            and commit_id == head_sha
            for folded, (state, commit_id) in latest_state.items()
        )
        superadmin_self_dispatch = (
            policy.is_superadmin(pr_author, repo=repo)
            and (actor is None or policy.is_superadmin(actor, repo=repo))
        )
        if not (superadmin_approved or superadmin_self_dispatch):
            raise ValueError(
                "changes to .choir/governance.json or .choir/certification.json "
                "require superadmin approval on the exact PR head"
            )
        return

    if is_maintainer_pr:
        if not policy.is_maintainer(pr_author, repo=repo):
            raise ValueError("TND maintainer PR author is not an authorized maintainer")
        return

    reviewer_approved = any(
        policy.is_reviewer(folded, repo=repo)
        and state == "APPROVED"
        and commit_id == head_sha
        for folded, (state, commit_id) in latest_state.items()
    )
    if reviewer_approved or actor is None or policy.is_reviewer(actor, repo=repo):
        return
    raise ValueError("TND proof PR requires approval or dispatch by an authorized reviewer")
