"""`choir` — the contributor-side CLI.

The primitives a worker agent drives. Each one does a single mechanical
step and stops; deciding what to claim, how to prove it, and when to
submit is the agent's.

  - `choir worker list <repo>`              — show claimable tasks
  - `choir worker claim <repo> <issue>`     — claim a task, set up the workspace
  - `choir worker heartbeat <repo> <issue>` — refresh the lease on a long task
  - `choir worker submit [repo] [issue]`    — push the branch + open the PR
  - `choir worker release [repo] [issue]`   — graceful unwind of a claim
  - `choir worker status`                   — list local workspaces
  - `choir update`                          — pull the checkout, reinstall deps

Every one is also importable: a harness that wants them in-process calls
`client.lease.claim`, `client.submit.submit_for_issue` and so on directly.

`--json` (before or after the worker operation) is the agent contract. It
prints the same objects the library returns, and puts the **outcome in the
payload rather than the exit code**: losing a claim race is a routine answer,
not a failure, so `choir worker claim <repo> <issue> --json` exits 0 with
``{"outcome": "LOST_RACE", "winner": ...}``. Under `--json` a non-zero exit
means only that no answer was produced — bad arguments, or GitHub failing.
Without it the prose output and its exit codes are unchanged, for when a
person is watching. Public worker failures in JSON mode use the version-1
envelope documented in ``docs/API.md``; operation outcomes keep their original
payloads and zero exits.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from argparse import Namespace
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit

from client import github as gh
from client.fork import ForkError, split_repo
from client.heartbeat import heartbeat_for_issue
from client.lease import ClaimOutcome, ClaimResult, claim
from client.release import ReleaseError, release_for_issue, release_from_cwd
from client.repo_store import RepoStoreError
from client.scheduling import order_candidates
from client.status import format_table, list_workspaces
from client.submit import SubmitError, submit_for_issue, submit_from_cwd
from client.task import prepare_task
from client.update import UpdateError, run_update
from client.workspace import (
    WorkspaceError,
    workspace_path,
    workspace_profile,
)
from gate.jsonio import emit as _emit
from gate.provers import ProverProfile
from gate.state.intake import ParseSuccess, parse_issue_body
from gate.state.labels import Priority, parse_difficulty, parse_priority
from gate.state.task_record import TaskRecord


class WorkerErrorCode(Enum):
    """Closed code set for the version-1 public worker failure envelope."""

    INVALID_ARGUMENTS = "invalid_arguments"
    AUTHENTICATION_REQUIRED = "authentication_required"
    AUTHORIZATION_DENIED = "authorization_denied"
    TRANSPORT_ERROR = "transport_error"
    REMOTE_PROTOCOL_ERROR = "remote_protocol_error"
    WORKSPACE_ERROR = "workspace_error"
    INTERNAL_ERROR = "internal_error"


_PUBLIC_OPERATIONS = frozenset({"list", "claim", "heartbeat", "release", "submit"})
_MUTATING_OPERATIONS = frozenset({"claim", "heartbeat", "release", "submit"})


class _InvalidWorkerArguments(ValueError):
    """A command-level relationship argparse cannot express directly."""


class _ArgumentParseFailure(Exception):
    def __init__(self, parser: argparse.ArgumentParser, message: str) -> None:
        super().__init__(message)
        self.parser = parser
        self.message = message


class _WorkerArgumentParser(argparse.ArgumentParser):
    """Let ``main`` serialize parse failures when JSON was requested."""

    def error(self, message: str) -> None:
        raise _ArgumentParseFailure(self, message)


_ERROR_MESSAGES = {
    WorkerErrorCode.INVALID_ARGUMENTS: "The worker command arguments are invalid.",
    WorkerErrorCode.AUTHENTICATION_REQUIRED: "GitHub authentication is required.",
    WorkerErrorCode.AUTHORIZATION_DENIED: "GitHub denied this operation.",
    WorkerErrorCode.TRANSPORT_ERROR: "The remote service could not be reached reliably.",
    WorkerErrorCode.REMOTE_PROTOCOL_ERROR: (
        "The remote service returned an invalid or unexpected response."
    ),
    WorkerErrorCode.WORKSPACE_ERROR: "The local workspace operation failed.",
    WorkerErrorCode.INTERNAL_ERROR: "The worker command failed unexpectedly.",
}


def _json_requested(argv: list[str]) -> bool:
    """The output mode knowable before parsing (needed for parse failures)."""
    if "--json" in argv:
        return True
    if "--text" in argv:
        return False
    return not sys.stdout.isatty()


def _operation_hint(argv: list[str]) -> str:
    for token in argv:
        if token in {"--json", "--text"}:
            continue
        return token if token in _PUBLIC_OPERATIONS else "worker"
    return "worker"


def _repo_argument(value: str) -> str:
    try:
        split_repo(value)
    except ForkError as error:
        raise argparse.ArgumentTypeError("expected a GitHub repo as owner/name") from error
    return value


def _positive_issue(value: str) -> int:
    try:
        issue = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a positive issue number") from error
    if issue <= 0:
        raise argparse.ArgumentTypeError("expected a positive issue number")
    return issue


def _failure_details(
    operation: str,
    *,
    command_started: bool,
    error: Exception | None = None,
) -> dict[str, object]:
    if isinstance(error, SubmitError) and error.public_error_details is not None:
        details = error.public_error_details
        number = details.get("pr_number")
        url = details.get("pr_url")
        reused = details.get("reused_existing_pr")
        if (
            details.get("mutation_state") == "completed"
            and isinstance(number, int)
            and not isinstance(number, bool)
            and number > 0
            and isinstance(url, str)
            and isinstance(reused, bool)
            and _safe_github_pr_url(url, number)
        ):
            return {
                "mutation_state": "completed",
                "pr_number": number,
                "pr_url": url,
                "reused_existing_pr": reused,
            }
    if isinstance(error, ReleaseError) and error.public_error_details is not None:
        details = error.public_error_details
        if (
            details.get("mutation_state") == "completed"
            and details.get("comment_posted") is True
            and details.get("workspace_removed") is False
        ):
            return {
                "mutation_state": "completed",
                "comment_posted": True,
                "workspace_removed": False,
            }
    if operation not in _MUTATING_OPERATIONS:
        return {"mutation_state": "not_applicable"}
    if not command_started:
        return {"mutation_state": "not_started"}
    # At the outer boundary there is deliberately no attempt to infer which
    # line failed. A remote write may have landed even when its response did
    # not, so mutation commands must make that uncertainty explicit.
    return {"mutation_state": "unknown"}


_GITHUB_PR_PATH = re.compile(
    r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/([1-9][0-9]*)"
)


def _safe_github_pr_url(url: str, number: int) -> bool:
    """Whether ``url`` is a public, credential-free github.com PR URL."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    match = _GITHUB_PR_PATH.fullmatch(parsed.path)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and port is None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and match is not None
        and int(match.group(1)) == number
    )


def _emit_failure(
    operation: str,
    code: WorkerErrorCode,
    *,
    command_started: bool,
    exit_code: int = 1,
    error: Exception | None = None,
) -> int:
    retryable = code is WorkerErrorCode.TRANSPORT_ERROR and operation == "list"
    _emit(
        {
            "schema_version": 1,
            "ok": False,
            "operation": operation,
            "error": {
                "code": code.value,
                "message": _ERROR_MESSAGES[code],
                "retryable": retryable,
                "details": _failure_details(
                    operation,
                    command_started=command_started,
                    error=error,
                ),
            },
        }
    )
    return exit_code


def _exception_chain(error: Exception) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _github_code(kind: gh.GitHubFailureKind) -> WorkerErrorCode:
    return {
        gh.GitHubFailureKind.AUTHENTICATION: WorkerErrorCode.AUTHENTICATION_REQUIRED,
        gh.GitHubFailureKind.AUTHORIZATION: WorkerErrorCode.AUTHORIZATION_DENIED,
        gh.GitHubFailureKind.TRANSPORT: WorkerErrorCode.TRANSPORT_ERROR,
        gh.GitHubFailureKind.REMOTE_PROTOCOL: WorkerErrorCode.REMOTE_PROTOCOL_ERROR,
        gh.GitHubFailureKind.LOCAL_SETUP: WorkerErrorCode.WORKSPACE_ERROR,
        gh.GitHubFailureKind.UNKNOWN: WorkerErrorCode.INTERNAL_ERROR,
    }[kind]


def _classify_exception(error: Exception, operation: str) -> WorkerErrorCode:
    """Classify only evidence that is safe to expose as a stable code."""
    chain = _exception_chain(error)

    for item in chain:
        if isinstance(item, gh.GitHubError):
            return _github_code(item.kind)
        kind = getattr(item, "github_failure_kind", None)
        if isinstance(kind, gh.GitHubFailureKind):
            return _github_code(kind)

    if any(isinstance(item, (TimeoutError, subprocess.TimeoutExpired)) for item in chain):
        return WorkerErrorCode.TRANSPORT_ERROR

    if isinstance(error, _InvalidWorkerArguments):
        return WorkerErrorCode.INVALID_ARGUMENTS
    if isinstance(error, (WorkspaceError, RepoStoreError)):
        return WorkerErrorCode.WORKSPACE_ERROR
    if isinstance(error, SubmitError):
        if error.workspace_failure:
            return WorkerErrorCode.WORKSPACE_ERROR
        return WorkerErrorCode.INTERNAL_ERROR
    if isinstance(error, ReleaseError):
        if error.workspace_failure:
            return WorkerErrorCode.WORKSPACE_ERROR
        return WorkerErrorCode.INTERNAL_ERROR
    if isinstance(error, ForkError):
        # A ForkError with reliable GitHub evidence was handled above. The
        # remaining cases combine local state and remote behavior, so guessing
        # a transport/auth category would be unsafe.
        return WorkerErrorCode.INTERNAL_ERROR
    if isinstance(error, json.JSONDecodeError) and operation in {"submit", "release"}:
        return WorkerErrorCode.WORKSPACE_ERROR
    return WorkerErrorCode.INTERNAL_ERROR


def _json_output_suffix(output: str) -> tuple[str, str] | None:
    """Return ``(diagnostic_prefix, one_json_document)`` when possible."""
    decoder = json.JSONDecoder()
    for start, char in enumerate(output):
        if char not in "[{":
            continue
        try:
            _value, end = decoder.raw_decode(output, start)
        except json.JSONDecodeError:
            continue
        if not output[end:].strip():
            return output[:start], output[start:]
    return None


def _run_json_operation(args: Namespace) -> int:
    """One boundary for every public worker JSON command.

    Buffering matters: a setup helper may print an advisory before raising.
    On failure those partial lines are discarded so stdout is exactly one
    JSON document. Successful command output is replayed byte-for-byte.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = args.func(args)
    except Exception as error:
        code = _classify_exception(error, args.cmd)
        invalid_arguments = code is WorkerErrorCode.INVALID_ARGUMENTS
        return _emit_failure(
            args.cmd,
            code,
            command_started=not invalid_arguments,
            exit_code=2 if invalid_arguments else 1,
            error=error,
        )

    if result != 0:
        # A future handler that forgets to raise on JSON failure must still not
        # escape the contract as prose/empty stdout.
        return _emit_failure(
            args.cmd,
            WorkerErrorCode.INTERNAL_ERROR,
            command_started=True,
        )
    separated = _json_output_suffix(stdout.getvalue())
    if separated is None:
        return _emit_failure(
            args.cmd,
            WorkerErrorCode.INTERNAL_ERROR,
            command_started=True,
        )
    diagnostic, document = separated
    if diagnostic:
        sys.stderr.write(diagnostic)
    sys.stdout.write(document)
    sys.stderr.write(stderr.getvalue())
    return result


def cmd_list(args: Namespace) -> int:
    try:
        issues = gh.list_available_issues(args.repo)
    except gh.GitHubError as e:
        if args.json:
            raise
        print(f"error: {e}", file=sys.stderr)
        return 1

    ordered = order_candidates(issues)
    if args.json:
        rows = []
        for issue in ordered:
            parsed = parse_issue_body(issue.body, expected_repo=args.repo)
            rows.append({
                "number": issue.number,
                "title": issue.title,
                "labels": issue.labels,
                "priority": parse_priority(issue.labels).name,
                "difficulty": (d.name if (d := parse_difficulty(issue.labels)) else None),
                "record": (parsed.record if isinstance(parsed, ParseSuccess) else None),
            })
        return _emit(rows)

    if not issues:
        print(f"No claimable tasks in {args.repo}.")
        return 0

    print(f"Available tasks in {args.repo}:\n")
    for issue in ordered:
        parsed = parse_issue_body(issue.body, expected_repo=args.repo)
        pr = parse_priority(issue.labels)
        d = parse_difficulty(issue.labels)
        tags = ""
        if pr != Priority.NORMAL:
            tags += f"  ({pr.name.lower()} priority)"
        if d is not None:
            tags += f"  [{d.name.lower()}]"
        if isinstance(parsed, ParseSuccess):
            r = parsed.record
            print(f"  #{issue.number:>4}  [{r.type.value}]  {r.target_decl}{tags}")
        else:
            print(f"  #{issue.number:>4}  [INVALID]  {issue.title}{tags}")
    return 0


def cmd_claim(args: Namespace) -> int:
    try:
        result = claim(args.repo, args.issue)
    except gh.GitHubError as e:
        if args.json:
            raise
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.json:
        return _claim_json(args.repo, args.issue, result)

    if result.outcome == ClaimOutcome.SKIPPED and "protocol" in result.reason:
        return _handle_protocol_stale_skip(result)

    if result.outcome != ClaimOutcome.WON:
        return _print_non_won_outcome(result)

    return _setup_after_claim(args.repo, args.issue, result.session)


def _claim_json(repo: str, issue: int, result: ClaimResult) -> int:
    """The claim, as data. Never prompts: an agent has no tty to answer.

    Every outcome exits 0 — LOST_RACE especially, which means "someone
    else holds this, take another task" and is the case that made the
    library the documented surface in the first place.
    """
    payload: dict[str, object] = {
        "outcome": result.outcome.name,
        "reason": result.reason,
        "winner": result.winner,
        "session": result.session,
        "prepared": None,
    }
    if result.outcome != ClaimOutcome.WON:
        if result.outcome == ClaimOutcome.SKIPPED and "protocol" in result.reason:
            payload["hint"] = "run 'choir update', then claim again"
        return _emit(payload)
    try:
        ready = prepare_task(repo, issue, session=result.session)
    except (WorkspaceError, gh.GitHubError) as e:
        payload["setup_failed"] = str(e)
        payload["workspace"] = str(workspace_path(repo, issue))
        return _emit(payload)
    payload["prepared"] = ready
    return _emit(payload)


_UPDATE_HINT = "  Run 'choir update', then re-run the claim."


def _handle_protocol_stale_skip(result: ClaimResult) -> int:
    """A SKIPPED claim whose reason names a protocol mismatch (note 13 §6).

    Interactive (a human at a tty) gets a one-keystroke offer to update
    now; non-tty (a script, a headless invocation) just gets the hint.
    Either way the claim is NOT retried in-process, even right after a
    successful update: this interpreter already loaded the old client
    code, so re-running the claim here would silently keep using it. The
    caller must re-invoke `choir claim`.
    """
    print(f"- Skipped: {result.reason}")

    if not sys.stdin.isatty():
        print(_UPDATE_HINT)
        return 2

    try:
        answer = input("update now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Ctrl-D / Ctrl-C at the prompt is a decline, not a traceback.
        print()
        print(_UPDATE_HINT)
        return 2
    if answer not in ("", "y", "yes"):
        print(_UPDATE_HINT)
        return 2

    try:
        update_result = run_update()
    except UpdateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"  updated: {update_result.old_sha[:7]} -> {update_result.new_sha[:7]}")
    print(
        "  This process is still running the old code — re-run the claim "
        "to pick it up."
    )
    return 2


def _setup_after_claim(repo: str, issue_number: int, session: str = "") -> int:
    """Build the workspace for a won claim and print what happened.

    `session` comes from the winning `ClaimResult` and is persisted with the
    workspace, so later beats and re-claims present the identity the lease
    was taken under.
    """
    try:
        ready = prepare_task(repo, issue_number, session=session)
    except (WorkspaceError, gh.GitHubError) as e:
        ws_path = workspace_path(repo, issue_number)
        print(f"✓ Claimed #{issue_number}, but setup failed: {e}", file=sys.stderr)
        print(
            f"  To retry: remove {ws_path}, then claim again. The lease is "
            f"held — 'choir release {repo} {issue_number}' gives it up.",
            file=sys.stderr,
        )
        return 2

    print(f"✓ Claimed #{issue_number} in {repo}.")
    print(f"  Workspace: {ready.path}")
    print(f"  Branch:    {ready.branch}")
    for advisory in ready.advisories:
        print()
        print(advisory)

    _print_claim_next_steps(ready.path, ready.record, workspace_profile(ready.path))
    return 0


def _print_claim_next_steps(
    path: Path, record: TaskRecord, profile: ProverProfile
) -> None:
    """Print the post-claim "Next:" hint.

    Every task type carries a `target_file` (the type-branched review
    task that pointed at a PR instead was removed by spec D1); uses the
    resolved profile's build command instead of a hardcoded lean4
    `lake build`.
    """
    print()
    print("  Next:")
    print(f"    cd {path}")
    build_cmd = " ".join(profile.build_command)
    print(f"    # read TASK.md, edit {record.target_file}, run {build_cmd}, commit")
    print("    choir submit")


def _print_non_won_outcome(result: ClaimResult) -> int:
    if result.outcome == ClaimOutcome.LOST_RACE:
        print(f"✗ Lost race to @{result.winner}. Try another issue.")
        return 1
    if result.outcome == ClaimOutcome.SKIPPED:
        print(f"- Skipped: {result.reason}")
        return 2
    print(f"! Error: {result.reason}", file=sys.stderr)
    return 3


def cmd_submit(args: Namespace) -> int:
    try:
        if args.repo and args.issue is not None:
            result = submit_for_issue(args.repo, args.issue)
        elif args.repo or args.issue is not None:
            if args.json:
                raise _InvalidWorkerArguments(
                    "provide both repo and issue, or neither"
                )
            print(
                "error: provide both repo and issue, or neither (to infer from cwd)",
                file=sys.stderr,
            )
            return 1
        else:
            result = submit_from_cwd(Path.cwd())
    except (SubmitError, gh.GitHubError) as e:
        if args.json:
            raise
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        return _emit(result)
    print(f"✓ Submitted as {result.pr_url}")
    return 0


def cmd_release(args: Namespace) -> int:
    try:
        if args.repo and args.issue is not None:
            result = release_for_issue(
                args.repo, args.issue, keep_workspace=args.keep_workspace
            )
        elif args.repo or args.issue is not None:
            if args.json:
                raise _InvalidWorkerArguments(
                    "provide both repo and issue, or neither"
                )
            print(
                "error: provide both repo and issue, or neither (to infer from cwd)",
                file=sys.stderr,
            )
            return 1
        else:
            result = release_from_cwd(
                Path.cwd(), keep_workspace=args.keep_workspace
            )
    except (ReleaseError, gh.GitHubError) as e:
        if args.json:
            raise
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.json:
        return _emit(result)
    print("✓ Released claim.")
    if not result.workspace_removed:
        if args.keep_workspace:
            print("  (workspace preserved per --keep-workspace)")
    else:
        print("  Local workspace removed.")
    return 0


def cmd_status(args: Namespace) -> int:
    entries = list_workspaces()
    if args.json:
        return _emit(entries)
    sys.stdout.write(format_table(entries))
    return 0


def cmd_heartbeat(args: Namespace) -> int:
    """Refresh the lease on a claimed task.

    A lease goes stale after 24 hours. A single proof finishes well inside
    that; an agent working a long task, or looping over several, calls this
    to keep its claim alive.

    The session the claim was made under is read from the lease's workspace,
    since a beat must present it to be recognised as the holder's. Use
    `--session` to beat from outside the workspace.
    """
    written, session = heartbeat_for_issue(
        args.repo, args.issue, session=args.session, start=Path.cwd()
    )
    if args.json:
        return _emit(
            {
                "refreshed": written,
                "repo": args.repo,
                "issue": args.issue,
                "session": session,
            }
        )
    if written:
        print(f"ok: lease refreshed on {args.repo}#{args.issue}")
        return 0
    if session is None:
        print(
            f"note: no workspace for {args.repo}#{args.issue} on this machine, so the "
            "session the claim was made under is unknown — pass --session to beat anyway",
            file=sys.stderr,
        )
        return 1
    print(
        f"note: no beat written for {args.repo}#{args.issue} "
        "(you may not hold the lease)",
        file=sys.stderr,
    )
    return 1


def cmd_update(args: Namespace) -> int:
    try:
        result = run_update()
    except UpdateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        return _emit(result)
    if result.changed:
        print(f"updated: {result.old_sha[:7]} -> {result.new_sha[:7]}")
    else:
        print("already up to date")
    if result.entry_point is None:
        print(
            "warning: could not write the `choir` entry point to ~/.local/bin — "
            "commands still work as <checkout>/.venv/bin/choir",
            file=sys.stderr,
        )
    return 0


def _add_format_flags(
    parser: argparse.ArgumentParser, *, after_subcommand: bool = False
) -> None:
    """Register `--json` / `--text` on `parser`.

    Registered on the top-level parser and on every subcommand, so the flag
    means the same wherever it is written — appending it is what both people
    and agents reach for first. The subcommand copies suppress their default:
    argparse applies defaults after parsing, so a `False` default here would
    overwrite a `--json` given before the subcommand.
    """
    default = {"default": argparse.SUPPRESS} if after_subcommand else {}
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument(
        "--json", dest="force_json", action="store_true",
        help="force JSON (the default when stdout is not a terminal)", **default,
    )
    fmt.add_argument(
        "--text", dest="force_text", action="store_true",
        help="force the human-readable output", **default,
    )


def main(argv: list[str] | None = None, *, prog: str = "choir worker") -> int:
    # `prog` so the router can lend this parser's `update` to the top-level
    # `choir update` without its help claiming to be a worker command.
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _WorkerArgumentParser(
        prog=prog,
        description="Choir worker commands",
    )
    _add_format_flags(parser)
    sub = parser.add_subparsers(dest="cmd", required=True)

    list_p = sub.add_parser("list", help="List claimable tasks in a repo")
    list_p.add_argument("repo", type=_repo_argument, help="GitHub repo as owner/name")
    list_p.set_defaults(func=cmd_list)

    claim_p = sub.add_parser(
        "claim", help="Claim an issue and set up the working directory"
    )
    claim_p.add_argument("repo", type=_repo_argument, help="GitHub repo as owner/name")
    claim_p.add_argument("issue", type=_positive_issue, help="Issue number")
    claim_p.set_defaults(func=cmd_claim)

    submit_p = sub.add_parser(
        "submit", help="Push the branch and open the PR"
    )
    submit_p.add_argument(
        "repo",
        nargs="?",
        type=_repo_argument,
        help="GitHub repo as owner/name (default: infer from cwd)",
    )
    submit_p.add_argument(
        "issue",
        nargs="?",
        type=_positive_issue,
        help="Issue number (default: infer from cwd)",
    )
    submit_p.set_defaults(func=cmd_submit)

    release_p = sub.add_parser(
        "release", help="Release a claim (post a release comment, tear down the workspace)"
    )
    release_p.add_argument(
        "repo",
        nargs="?",
        type=_repo_argument,
        help="GitHub repo as owner/name (default: infer from cwd)",
    )
    release_p.add_argument(
        "issue",
        nargs="?",
        type=_positive_issue,
        help="Issue number (default: infer from cwd)",
    )
    release_p.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the local workspace directory after release",
    )
    release_p.set_defaults(func=cmd_release)

    status_p = sub.add_parser(
        "status", help="List local workspaces (claims held on this machine)"
    )
    status_p.set_defaults(func=cmd_status)

    heartbeat_p = sub.add_parser(
        "heartbeat", help="Refresh the lease on a claimed task"
    )
    heartbeat_p.add_argument("repo", type=_repo_argument, help="owner/name")
    heartbeat_p.add_argument("issue", type=_positive_issue, help="issue number")
    heartbeat_p.add_argument(
        "--session",
        default=None,
        help="session id the claim was made under (default: read from the workspace)",
    )
    heartbeat_p.set_defaults(func=cmd_heartbeat)

    update_p = sub.add_parser(
        "update", help="Pull the Choir checkout to latest and reinstall deps"
    )
    update_p.set_defaults(func=cmd_update)


    for subparser in sub.choices.values():
        _add_format_flags(subparser, after_subcommand=True)

    try:
        args = parser.parse_args(raw_argv)
    except _ArgumentParseFailure as error:
        if _json_requested(raw_argv):
            return _emit_failure(
                _operation_hint(raw_argv),
                WorkerErrorCode.INVALID_ARGUMENTS,
                command_started=False,
                exit_code=2,
            )
        error.parser.print_usage(sys.stderr)
        error.parser.exit(
            2,
            f"{error.parser.prog}: error: {error.message}\n",
        )
        raise AssertionError("argparse.exit returned") from error
    # JSON unless a person is watching. An agent captures stdout, so it gets
    # the machine contract without having to know a flag exists; a human at a
    # terminal gets prose. Either can be forced.
    args.json = args.force_json or (not args.force_text and not sys.stdout.isatty())
    if args.json and args.cmd in _PUBLIC_OPERATIONS:
        return _run_json_operation(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
