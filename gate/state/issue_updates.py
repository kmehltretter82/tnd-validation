"""Fail-closed GitHub issue mutations for trusted lifecycle workflows.

The write-capable workflows call this maintained-base module instead of a
sequence of best-effort ``gh issue edit ... || true`` commands.  Each update
reads the current issue, applies one exact label/state transaction, and reads
the issue again before reporting success.  Candidate code is never imported.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gate.state.intake import ParseSuccess, parse_issue_body
from gate.state.intake_cli import record_hash

MAX_GH_OUTPUT = 2 * 1024 * 1024
MAX_COMMENTS = 10_000
MAX_ISSUE_BODY = 256 * 1024
MAX_COMMENT_BYTES = 2 * 1024 * 1024
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
LIFECYCLE_LABELS = {
    "choir/available",
    "choir/claimed",
    "choir/done",
    "choir/invalid",
}


class IssueUpdateError(RuntimeError):
    """A lifecycle mutation could not establish its complete postcondition."""


@dataclass(frozen=True)
class Issue:
    number: int
    state: str
    author: str
    body: str
    labels: frozenset[str]


@dataclass(frozen=True)
class IntakePayload:
    successful: bool
    add: frozenset[str]
    remove: frozenset[str]
    should_post: bool
    comment: str
    record_hash: object


def _json_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IssueUpdateError("GitHub JSON contains duplicate object keys")
        result[key] = value
    return result


def _decode(raw: str) -> Any:
    try:
        if len(raw.encode("utf-8")) > MAX_GH_OUTPUT:
            raise IssueUpdateError("GitHub response exceeds the output limit")
        return json.loads(raw, object_pairs_hook=_json_no_duplicates)
    except IssueUpdateError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IssueUpdateError("GitHub returned malformed JSON") from error


def _gh_json(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> Any:
    argv = ["gh", "api", "--method", method, endpoint]
    data = None
    if payload is not None:
        argv += ["--input", "-"]
        data = json.dumps(payload, separators=(",", ":"))
    try:
        result = subprocess.run(
            argv,
            input=data,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise IssueUpdateError("GitHub API command did not complete") from error
    if len((result.stdout + result.stderr).encode("utf-8")) > MAX_GH_OUTPUT:
        raise IssueUpdateError("GitHub command output exceeds the output limit")
    if result.returncode:
        raise IssueUpdateError(
            f"GitHub API {method} failed with status {result.returncode}: "
            f"{result.stderr.strip()[:500]}"
        )
    return _decode(result.stdout)


def _gh_comment_pages(repo: str, number: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    seen: set[int] = set()
    body_bytes = 0
    # Do not let `gh --slurp` accumulate an unbounded listing before this
    # process can enforce its limits. Each API response is independently
    # bounded by `_gh_json`, and the loop has an explicit overall cap.
    for page_number in range(1, MAX_COMMENTS // 100 + 2):
        page = _gh_json(
            "GET",
            f"repos/{repo}/issues/{number}/comments?per_page=100&page={page_number}",
        )
        if not isinstance(page, list) or len(page) > 100:
            raise IssueUpdateError("GitHub comment page is invalid")
        for item in page:
            if not isinstance(item, dict):
                raise IssueUpdateError("GitHub comment record is invalid")
            comment_id, body = item.get("id"), item.get("body")
            if (
                isinstance(comment_id, bool)
                or not isinstance(comment_id, int)
                or comment_id < 1
                or comment_id in seen
                or not isinstance(body, str)
            ):
                raise IssueUpdateError("GitHub comment record has invalid fields")
            seen.add(comment_id)
            comments.append(item)
            body_bytes += len(body.encode("utf-8"))
            if len(comments) > MAX_COMMENTS:
                raise IssueUpdateError("GitHub comment listing exceeds the comment limit")
            if body_bytes > MAX_COMMENT_BYTES:
                raise IssueUpdateError("GitHub comments exceed the aggregate byte limit")
        if len(page) < 100:
            return comments
    raise IssueUpdateError("GitHub comment listing exceeds the page limit")


def _validate_repo_issue(repo: str, number: int) -> None:
    if (
        not isinstance(repo, str)
        or not REPOSITORY.fullmatch(repo)
        or any(part in {".", ".."} for part in repo.split("/"))
        or isinstance(number, bool)
        or number < 1
    ):
        raise IssueUpdateError("invalid repository or issue number")


def _parse_issue(value: Any, expected: int) -> Issue:
    if not isinstance(value, dict) or "pull_request" in value:
        raise IssueUpdateError("lifecycle target is not an ordinary issue")
    number, state = value.get("number"), value.get("state")
    user, labels = value.get("user"), value.get("labels")
    body_value = value.get("body")
    login = user.get("login") if isinstance(user, dict) else None
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or number != expected
        or state not in {"open", "closed"}
        or (user is not None and not isinstance(user, dict))
        or (login is not None and not isinstance(login, str))
        or (body_value is not None and not isinstance(body_value, str))
        or not isinstance(labels, list)
    ):
        raise IssueUpdateError("GitHub issue response has invalid fields")
    names: set[str] = set()
    for label in labels:
        name = label.get("name") if isinstance(label, dict) else None
        if not isinstance(name, str) or not name or name in names:
            raise IssueUpdateError("GitHub issue labels are invalid or duplicated")
        names.add(name)
    return Issue(number, state, login or "", body_value or "", frozenset(names))


def _issue(repo: str, number: int) -> Issue:
    return _parse_issue(_gh_json("GET", f"repos/{repo}/issues/{number}"), number)


def _patch_issue(
    repo: str,
    issue: Issue,
    labels: set[str],
    *,
    state: str | None = None,
) -> Issue:
    payload: dict[str, Any] = {"labels": sorted(labels)}
    if state is not None:
        payload.update(state=state, state_reason="completed")
    _parse_issue(
        _gh_json("PATCH", f"repos/{repo}/issues/{issue.number}", payload),
        issue.number,
    )
    return _issue(repo, issue.number)


def _read_body(path: Path) -> str:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_ISSUE_BODY:
            raise IssueUpdateError("issue body exceeds the input limit")
        return raw.decode("utf-8")
    except IssueUpdateError:
        raise
    except (OSError, UnicodeError) as error:
        raise IssueUpdateError("issue body is unreadable") from error


def _require_labels(issue: Issue, expected: set[str], *, state: str | None = None) -> None:
    if issue.labels != frozenset(expected) or (state is not None and issue.state != state):
        raise IssueUpdateError("GitHub issue postcondition differs from the requested state")


def ensure_comment(repo: str, number: int, body: str) -> None:
    """Idempotently establish one exact issue comment and verify it by rereading."""
    _validate_repo_issue(repo, number)
    if (
        not isinstance(body, str)
        or not body
        or len(body.encode("utf-8")) > MAX_ISSUE_BODY
    ):
        raise IssueUpdateError("issue comment is invalid or exceeds the input limit")
    if any(item["body"] == body for item in _gh_comment_pages(repo, number)):
        return
    post_error: IssueUpdateError | None = None
    try:
        posted = _gh_json(
            "POST",
            f"repos/{repo}/issues/{number}/comments",
            {"body": body},
        )
        if not isinstance(posted, dict) or posted.get("body") != body:
            raise IssueUpdateError("GitHub did not return the posted issue comment")
    except IssueUpdateError as error:
        # The transport can fail after GitHub committed the write. Decide from
        # the reread postcondition, never by matching an error message.
        post_error = error
    if any(item["body"] == body for item in _gh_comment_pages(repo, number)):
        return
    if post_error is not None:
        raise post_error
    raise IssueUpdateError("issue comment postcondition is absent from the issue")


def quarantine(repo: str, number: int, *, mark_invalid: bool = False) -> None:
    """Remove claimability before parsing; optionally mark a non-owner task invalid."""
    _validate_repo_issue(repo, number)
    issue = _issue(repo, number)
    labels = set(issue.labels)
    labels.discard("choir/available")
    if mark_invalid:
        labels.add("choir/invalid")
    if labels != set(issue.labels):
        issue = _patch_issue(repo, issue, labels)
    _require_labels(issue, labels)
    if "choir/available" in issue.labels or (
        mark_invalid and "choir/invalid" not in issue.labels
    ):
        raise IssueUpdateError("issue quarantine postcondition was not established")


def _label_list(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > 32
        or not all(
            isinstance(label, str)
            and label
            and len(label.encode("utf-8")) <= 50
            and not any(char in label for char in "\r\n\0")
            for label in value
        )
        or len(value) != len(set(value))
    ):
        raise IssueUpdateError(f"intake {field} is invalid")
    return value


def _read_intake_payload(path: Path) -> IntakePayload:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IssueUpdateError("intake result is unreadable or malformed") from error
    if not isinstance(result, dict) or result.get("status") not in {"ok", "error"}:
        raise IssueUpdateError("intake result has an invalid status")
    add = frozenset(_label_list(result.get("add_labels"), "add_labels"))
    remove = frozenset(_label_list(result.get("remove_labels"), "remove_labels"))
    if add & remove:
        raise IssueUpdateError("intake label additions and removals overlap")
    should_post, comment = result.get("should_post_comment"), result.get("comment")
    if not isinstance(should_post, bool) or not isinstance(comment, str) or not comment:
        raise IssueUpdateError("intake comment contract is invalid")
    return IntakePayload(
        result["status"] == "ok",
        add,
        remove,
        should_post,
        comment,
        result.get("record_hash"),
    )


def _intake_final_labels(issue: Issue, repo: str, payload: IntakePayload) -> set[str]:
    parsed = parse_issue_body(issue.body, expected_repo=repo)
    if payload.successful:
        if issue.state != "open":
            raise IssueUpdateError("a closed issue cannot become available")
        if not isinstance(parsed, ParseSuccess):
            raise IssueUpdateError("successful intake no longer parses as a task")
        expected_add = frozenset({
            "choir/task",
            "choir/available",
            f"choir/type:{parsed.record.type.value}",
        })
        expected_hash = record_hash(parsed.record)
        if (
            payload.add != expected_add
            or payload.remove != frozenset({"choir/invalid"})
            or payload.record_hash != expected_hash
            or f"choir-intake-ack:{expected_hash}" not in payload.comment
        ):
            raise IssueUpdateError("successful intake payload does not match the task")
    else:
        expected_add = frozenset({"choir/task", "choir/invalid"})
        if (
            payload.add != expected_add
            or payload.remove != frozenset({"choir/available"})
            or not payload.should_post
        ):
            raise IssueUpdateError("rejected intake payload does not quarantine the task")
    labels = {
        label
        for label in issue.labels
        if label not in LIFECYCLE_LABELS
        and label != "choir/task"
        and not label.startswith("choir/type:")
    }
    labels.update(expected_add)
    return labels


def _intake_binding_changed(
    current: Issue,
    original: Issue,
    validated_body: str,
    successful: bool,
) -> bool:
    return (
        current.body != validated_body
        or current.author.casefold() != original.author.casefold()
        or (successful and current.state != "open")
    )


def apply_intake(repo: str, number: int, result_path: Path, body_path: Path) -> None:
    """Apply a validated intake payload and verify labels/comment postconditions."""
    _validate_repo_issue(repo, number)
    payload = _read_intake_payload(result_path)
    issue = _issue(repo, number)
    if issue.author.casefold() != repo.split("/", 1)[0].casefold():
        raise IssueUpdateError("intake target is not owner-authored")
    validated_body = _read_body(body_path)
    if issue.body != validated_body:
        raise IssueUpdateError("issue body changed after intake validation")

    labels = _intake_final_labels(issue, repo, payload)
    if labels != set(issue.labels):
        issue = _patch_issue(repo, issue, labels)
    _require_labels(issue, labels)
    current = _issue(repo, number)
    if _intake_binding_changed(current, issue, validated_body, payload.successful):
        quarantine(repo, number, mark_invalid=True)
        raise IssueUpdateError("issue changed while intake labels were being applied")
    ensure_comment(repo, number, payload.comment)
    current = _issue(repo, number)
    if _intake_binding_changed(current, issue, validated_body, payload.successful):
        quarantine(repo, number, mark_invalid=True)
        raise IssueUpdateError("issue changed while intake comment was being applied")
    _require_labels(current, labels)


def complete_task(repo: str, number: int, pr: int) -> None:
    """Close exactly one approved task and verify its final lifecycle state."""
    _validate_repo_issue(repo, number)
    if isinstance(pr, bool) or pr < 1:
        raise IssueUpdateError("invalid pull-request number")
    issue = _issue(repo, number)
    owner = repo.split("/", 1)[0]
    parsed = parse_issue_body(issue.body, expected_repo=repo)
    if (
        issue.author.casefold() != owner.casefold()
        or "choir/task" not in issue.labels
        or not isinstance(parsed, ParseSuccess)
        or not parsed.record.target_file
        or not parsed.record.target_decl
    ):
        raise IssueUpdateError("merge reference is not an owner-approved Choir task")
    labels = set(issue.labels) - LIFECYCLE_LABELS
    labels.update({"choir/task", "choir/done"})
    if issue.labels != frozenset(labels) or issue.state != "closed":
        issue = _patch_issue(repo, issue, labels, state="closed")
    _require_labels(issue, labels, state="closed")

    marker = f"<!-- tnd-merged-pr:{pr} -->"
    body = f"{marker}\nMerged in #{pr}."
    ensure_comment(repo, number, body)
    _require_labels(_issue(repo, number), labels, state="closed")


def write_comment_bodies(repo: str, number: int, output: Path) -> None:
    """Write a complete bounded comment-body snapshot for intake idempotency."""
    _validate_repo_issue(repo, number)
    bodies = [item["body"] for item in _gh_comment_pages(repo, number)]
    output.write_text("\n".join(json.dumps(body) for body in bodies) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True, type=int)
    commands = parser.add_subparsers(dest="command", required=True)
    quarantine_parser = commands.add_parser("quarantine")
    quarantine_parser.add_argument("--mark-invalid", action="store_true")
    intake_parser = commands.add_parser("apply-intake")
    intake_parser.add_argument("--result", required=True, type=Path)
    intake_parser.add_argument("--body-file", required=True, type=Path)
    complete_parser = commands.add_parser("complete")
    complete_parser.add_argument("--pr", required=True, type=int)
    comments_parser = commands.add_parser("comments")
    comments_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "quarantine":
            quarantine(args.repo, args.issue, mark_invalid=args.mark_invalid)
        elif args.command == "apply-intake":
            apply_intake(args.repo, args.issue, args.result, args.body_file)
        elif args.command == "complete":
            complete_task(args.repo, args.issue, args.pr)
        else:
            write_comment_bodies(args.repo, args.issue, args.output)
    except IssueUpdateError as error:
        print(f"lifecycle update refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
