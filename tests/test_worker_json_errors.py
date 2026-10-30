"""Stable version-1 failures for the public ``choir worker --json`` API."""

from __future__ import annotations

import json
import subprocess

import pytest

from choir_cli import main
from client import cli as worker
from client import fork as fork_mod
from client import github as gh
from client import release as release_mod
from client import submit as submit_mod
from client._subprocess import CompletedRun
from client.lease import ClaimOutcome, ClaimResult
from client.release import ReleaseError
from client.submit import SubmitError
from client.workspace import LeaseMetadata, WorkspaceError

REPO = "example/project"


def _read_failure(capsys, exit_code: int) -> dict[str, object]:
    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert set(payload) == {"schema_version", "ok", "operation", "error"}
    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "retryable", "details"}
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["retryable"], bool)
    assert isinstance(error["details"], dict)
    return payload


@pytest.mark.parametrize(
    ("operation", "argv", "target"),
    [
        ("list", ["list", REPO, "--json"], "list_available_issues"),
        ("claim", ["claim", REPO, "17", "--json"], "claim"),
        (
            "heartbeat",
            ["heartbeat", REPO, "17", "--json"],
            "heartbeat_for_issue",
        ),
        ("release", ["release", REPO, "17", "--json"], "release_for_issue"),
        ("submit", ["submit", REPO, "17", "--json"], "submit_for_issue"),
    ],
)
def test_unknown_exception_is_safe_internal_error_for_every_operation(
    monkeypatch, capsys, operation, argv, target
):
    secret = "ghp_do_not_leak /private/secret/workspace"

    def fail(*_args, **_kwargs):
        raise RuntimeError(secret)

    if target == "list_available_issues":
        monkeypatch.setattr(worker.gh, target, fail)
    else:
        monkeypatch.setattr(worker, target, fail)

    payload = _read_failure(capsys, main(["worker", *argv]))
    assert payload["operation"] == operation
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["retryable"] is False
    assert secret not in json.dumps(payload)
    expected_state = "not_applicable" if operation == "list" else "unknown"
    assert payload["error"]["details"] == {"mutation_state": expected_state}


@pytest.mark.parametrize("position", ["before", "after"])
def test_argument_failure_is_json_wherever_flag_appears(capsys, position):
    argv = (
        ["worker", "--json", "claim", REPO, "not-an-integer"]
        if position == "before"
        else ["worker", "claim", REPO, "not-an-integer", "--json"]
    )
    payload = _read_failure(capsys, main(argv))
    assert payload["operation"] == "claim"
    assert payload["error"] == {
        "code": "invalid_arguments",
        "message": "The worker command arguments are invalid.",
        "retryable": False,
        "details": {"mutation_state": "not_started"},
    }


def test_unknown_subcommand_does_not_borrow_later_operation_name(capsys):
    payload = _read_failure(
        capsys,
        main(["worker", "bogus", "list", "--json"]),
    )
    assert payload["operation"] == "worker"
    assert payload["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize(
    "argv",
    [
        ["list", "not-a-repo"],
        ["claim", REPO, "0"],
        ["heartbeat", REPO, "-1"],
        ["release", "not-a-repo", "17"],
        ["submit", REPO, "0"],
    ],
)
def test_repo_and_issue_values_are_validated_before_operation(capsys, argv):
    payload = _read_failure(capsys, main(["worker", *argv, "--json"]))
    assert payload["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize(
    ("operation", "args"),
    [
        ("list", ["list", REPO]),
        ("claim", ["claim", REPO, "17"]),
        ("heartbeat", ["heartbeat", REPO, "17"]),
        ("release", ["release", REPO, "17"]),
        ("submit", ["submit", REPO, "17"]),
    ],
)
def test_parser_rejects_unknown_option_with_envelope(capsys, operation, args):
    payload = _read_failure(
        capsys,
        main(["worker", *args, "--unknown-worker-option", "--json"]),
    )
    assert payload["operation"] == operation
    assert payload["error"]["code"] == "invalid_arguments"
    expected_state = "not_applicable" if operation == "list" else "not_started"
    assert payload["error"]["details"] == {"mutation_state": expected_state}


def test_manual_submit_argument_relationship_uses_argument_envelope(capsys):
    payload = _read_failure(
        capsys,
        main(["worker", "submit", REPO, "--json"]),
    )
    assert payload["operation"] == "submit"
    assert payload["error"]["code"] == "invalid_arguments"
    assert payload["error"]["details"] == {"mutation_state": "not_started"}


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (gh.GitHubFailureKind.AUTHENTICATION, "authentication_required"),
        (gh.GitHubFailureKind.AUTHORIZATION, "authorization_denied"),
        (gh.GitHubFailureKind.TRANSPORT, "transport_error"),
        (gh.GitHubFailureKind.REMOTE_PROTOCOL, "remote_protocol_error"),
        (gh.GitHubFailureKind.LOCAL_SETUP, "workspace_error"),
        (gh.GitHubFailureKind.UNKNOWN, "internal_error"),
    ],
)
def test_typed_github_failure_codes(monkeypatch, capsys, kind, code):
    def fail(_repo):
        raise gh.GitHubError("sensitive diagnostic", kind=kind)

    monkeypatch.setattr(worker.gh, "list_available_issues", fail)
    payload = _read_failure(
        capsys,
        main(["worker", "list", REPO, "--json"]),
    )
    assert payload["error"]["code"] == code
    assert payload["error"]["retryable"] is (code == "transport_error")
    assert "sensitive" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("returncode", "stderr", "code"),
    [
        (4, "not authenticated", "authentication_required"),
        (1, "gh: forbidden (HTTP 403)", "authorization_denied"),
        (1, "gh: unavailable (HTTP 503)", "transport_error"),
        (1, "gh: missing (HTTP 404)", "remote_protocol_error"),
        (1, "ambiguous changing prose", "internal_error"),
    ],
)
def test_real_gh_exit_classification_uses_only_stable_signals(
    monkeypatch, capsys, returncode, stderr, code
):
    def fail(cmd, **_kwargs):
        raise subprocess.CalledProcessError(returncode, cmd, stderr=stderr)

    monkeypatch.setattr(gh.subprocess, "run", fail)
    payload = _read_failure(
        capsys,
        main(["worker", "list", REPO, "--json"]),
    )
    assert payload["error"]["code"] == code


def test_non_json_and_schema_invalid_gh_success_are_remote_protocol_errors(
    monkeypatch, capsys
):
    outputs = iter(["not json", '{"unexpected":"object"}'])

    def succeed(_cmd, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=next(outputs), stderr="")

    monkeypatch.setattr(gh.subprocess, "run", succeed)
    for _ in range(2):
        payload = _read_failure(
            capsys,
            main(["worker", "list", REPO, "--json"]),
        )
        assert payload["error"]["code"] == "remote_protocol_error"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("number", "17"),
        ("number", True),
        ("title", 17),
        ("body", 17),
        ("state", 17),
        ("state", "FUTURE"),
        ("labels", {}),
        ("labels", [17]),
        ("labels", [{"name": 17}]),
        ("assignees", {}),
        ("assignees", [17]),
        ("assignees", [{"login": 17}]),
    ],
)
def test_schema_invalid_issue_fields_are_remote_protocol_errors(
    monkeypatch, capsys, field, value
):
    issue = {
        "number": 17,
        "title": "Task",
        "body": None,
        "state": "OPEN",
        "labels": [],
        "assignees": [],
    }
    issue[field] = value

    def succeed(_cmd, **_kwargs):
        return subprocess.CompletedProcess(
            [], 0, stdout=json.dumps([issue]), stderr=""
        )

    monkeypatch.setattr(gh.subprocess, "run", succeed)
    payload = _read_failure(
        capsys,
        main(["worker", "list", REPO, "--json"]),
    )
    assert payload["error"]["code"] == "remote_protocol_error"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"author": [], "state": "OPEN"},
        {"author": {"login": 17}, "state": "OPEN"},
        {"author": {"login": "worker"}, "state": 17},
        {"author": {"login": "worker"}, "state": "FUTURE"},
    ],
)
def test_schema_invalid_pr_overview_is_remote_protocol(monkeypatch, payload):
    monkeypatch.setattr(gh, "_run", lambda _cmd: json.dumps(payload))
    with pytest.raises(gh.GitHubError) as caught:
        gh.get_pr_overview(REPO, 17)
    assert caught.value.kind is gh.GitHubFailureKind.REMOTE_PROTOCOL


@pytest.mark.parametrize(
    "row",
    [
        {
            "url": "https://github.com/example/project/pull/23",
            "headRefName": "branch",
            "headRepositoryOwner": {"login": 17},
        },
        {
            "url": "https://github.com/example/project/pull/23",
            "headRefName": 17,
            "headRepositoryOwner": {"login": "worker"},
        },
        {
            "url": 17,
            "headRefName": "branch",
            "headRepositoryOwner": {"login": "worker"},
        },
        {
            "url": "https://token@github.com/example/project/pull/23",
            "headRefName": "branch",
            "headRepositoryOwner": {"login": "worker"},
        },
        {
            "url": "https://github.com/other/project/pull/23",
            "headRefName": "branch",
            "headRepositoryOwner": {"login": "worker"},
        },
    ],
)
def test_schema_invalid_pr_list_rows_are_remote_protocol(monkeypatch, row):
    monkeypatch.setattr(
        submit_mod,
        "run",
        lambda *_args, **_kwargs: CompletedRun(0, json.dumps([row]), ""),
    )
    with pytest.raises(SubmitError) as caught:
        submit_mod._find_open_pr(REPO, "branch", head_owner="worker")
    assert caught.value.github_failure_kind is gh.GitHubFailureKind.REMOTE_PROTOCOL


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"defaultBranchRef":null}',
        '{"defaultBranchRef":{"name":17}}',
        '{"defaultBranchRef":{"name":"bad branch"}}',
    ],
)
def test_schema_invalid_default_branch_is_remote_protocol(monkeypatch, payload):
    monkeypatch.setattr(
        submit_mod,
        "run",
        lambda *_args, **_kwargs: CompletedRun(0, payload, ""),
    )
    with pytest.raises(SubmitError) as caught:
        submit_mod._default_branch(REPO)
    assert caught.value.github_failure_kind is gh.GitHubFailureKind.REMOTE_PROTOCOL


@pytest.mark.parametrize(
    "url",
    [
        "created pull request 23",
        "https://token@github.com/example/project/pull/23",
        "https://github.com/other/project/pull/23",
        "https://github.com/example/project/pull/not-a-number",
    ],
)
def test_schema_invalid_created_pr_url_is_remote_protocol(monkeypatch, url):
    monkeypatch.setattr(
        submit_mod,
        "run",
        lambda *_args, **_kwargs: CompletedRun(0, url, ""),
    )
    with pytest.raises(SubmitError) as caught:
        submit_mod._gh_pr_create(
            repo=REPO,
            head="worker:branch",
            base="main",
            title="title",
            body="body",
        )
    assert caught.value.github_failure_kind is gh.GitHubFailureKind.REMOTE_PROTOCOL


@pytest.mark.parametrize("name", [17, "not-a-repo", "owner/name/extra"])
def test_schema_invalid_fork_name_is_remote_protocol(monkeypatch, name):
    payload = {
        "data": {
            "repository": {
                "forks": {"nodes": [{"nameWithOwner": name}]},
            }
        }
    }
    monkeypatch.setattr(
        fork_mod,
        "_run_gh",
        lambda _args: CompletedRun(0, json.dumps(payload), ""),
    )
    with pytest.raises(fork_mod.ForkError) as caught:
        fork_mod.find_fork(REPO)
    assert caught.value.github_failure_kind is gh.GitHubFailureKind.REMOTE_PROTOCOL


def test_timeout_retryability_is_conservative_for_mutations(monkeypatch, capsys):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["gh", "api"], 60)

    monkeypatch.setattr(worker, "claim", timeout)
    payload = _read_failure(
        capsys,
        main(["worker", "claim", REPO, "17", "--json"]),
    )
    assert payload["error"]["code"] == "transport_error"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["details"] == {"mutation_state": "unknown"}


def test_workspace_failure_after_possible_release_mutation_is_explicit(
    monkeypatch, capsys
):
    mutated = False

    def release(*_args, **_kwargs):
        nonlocal mutated
        mutated = True
        raise WorkspaceError("/private/workspace must not leak")

    monkeypatch.setattr(worker, "release_for_issue", release)
    payload = _read_failure(
        capsys,
        main(["worker", "release", REPO, "17", "--json"]),
    )
    assert mutated
    assert payload["error"]["code"] == "workspace_error"
    assert payload["error"]["details"] == {"mutation_state": "unknown"}
    assert "/private" not in json.dumps(payload)


def test_won_claim_setup_failure_remains_operation_data_and_clean_json(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        worker,
        "claim",
        lambda *_args: ClaimResult(ClaimOutcome.WON, session="a" * 16),
    )

    def fail_setup(*_args, **_kwargs):
        print("setup diagnostic before failure")
        raise WorkspaceError("setup failed")

    monkeypatch.setattr(worker, "prepare_task", fail_setup)
    assert main(["worker", "claim", REPO, "17", "--json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["outcome"] == "WON"
    assert payload["setup_failed"] == "setup failed"
    assert payload["prepared"] is None
    assert "setup diagnostic before failure" in captured.err


def test_known_submit_mutation_is_not_hidden_by_later_failure(monkeypatch, capsys):
    error = SubmitError(
        "issue comment failed after PR creation",
        github_failure_kind=gh.GitHubFailureKind.TRANSPORT,
        public_error_details={
            "mutation_state": "completed",
            "pr_number": 23,
            "pr_url": "https://github.com/example/project/pull/23",
            "reused_existing_pr": False,
        },
    )

    def fail(*_args):
        raise error

    monkeypatch.setattr(worker, "submit_for_issue", fail)
    payload = _read_failure(
        capsys,
        main(["worker", "submit", REPO, "17", "--json"]),
    )
    assert payload["error"]["code"] == "transport_error"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["details"] == error.public_error_details


def test_submit_source_preserves_pr_result_when_final_comment_fails(
    monkeypatch, tmp_path
):
    LeaseMetadata(
        repo=REPO,
        issue=17,
        branch="choir/17-task",
        pinned_commit="a" * 40,
        claimed_at="2026-10-30T00:00:00+00:00",
        claimed_by="example",
        target_file="Task.lean",
        target_decl="Task.result",
        task_type="prove",
    ).write(tmp_path / ".choir-lease.json")
    monkeypatch.setattr(submit_mod, "_commits_ahead", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(fork_mod, "authenticated_login", lambda: "example")
    monkeypatch.setattr(submit_mod, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        submit_mod,
        "_find_open_pr",
        lambda *_args, **_kwargs: "https://github.com/example/project/pull/23",
    )
    monkeypatch.setattr(
        gh,
        "post_comment",
        lambda *_args: (_ for _ in ()).throw(
            gh.GitHubError(
                "timeout after write",
                kind=gh.GitHubFailureKind.TRANSPORT,
            )
        ),
    )
    with pytest.raises(SubmitError) as caught:
        submit_mod.submit_at(tmp_path)
    assert caught.value.github_failure_kind is gh.GitHubFailureKind.TRANSPORT
    assert caught.value.public_error_details == {
        "mutation_state": "completed",
        "pr_number": 23,
        "pr_url": "https://github.com/example/project/pull/23",
        "reused_existing_pr": True,
    }


def test_known_release_mutation_is_not_hidden_by_cleanup_failure(monkeypatch, capsys):
    error = ReleaseError(
        "cleanup failed after comment",
        workspace_failure=True,
        public_error_details={
            "mutation_state": "completed",
            "comment_posted": True,
            "workspace_removed": False,
        },
    )

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(worker, "release_for_issue", fail)
    payload = _read_failure(
        capsys,
        main(["worker", "release", REPO, "17", "--json"]),
    )
    assert payload["error"]["code"] == "workspace_error"
    assert payload["error"]["details"] == error.public_error_details


def test_release_source_preserves_posted_comment_when_cleanup_fails(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(gh, "current_user", lambda: "worker")
    monkeypatch.setattr(release_mod, "lease_holder", lambda *_args: ("worker", "held"))
    monkeypatch.setattr(gh, "post_comment", lambda *_args: None)
    monkeypatch.setattr(release_mod, "workspace_path", lambda *_args: workspace)
    monkeypatch.setattr(
        release_mod.repo_store,
        "remove_workspace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup")),
    )
    with pytest.raises(ReleaseError) as caught:
        release_mod.release_for_issue(REPO, 17)
    assert caught.value.workspace_failure
    assert caught.value.public_error_details == {
        "mutation_state": "completed",
        "comment_posted": True,
        "workspace_removed": False,
    }


def test_untrusted_completed_submit_details_cannot_leak_credentials(
    monkeypatch, capsys
):
    error = SubmitError(
        "late failure",
        github_failure_kind=gh.GitHubFailureKind.TRANSPORT,
        public_error_details={
            "mutation_state": "completed",
            "pr_number": 23,
            "pr_url": "https://ghp_secret@github.com/example/project/pull/23",
            "reused_existing_pr": False,
        },
    )

    def fail(*_args):
        raise error

    monkeypatch.setattr(worker, "submit_for_issue", fail)
    payload = _read_failure(
        capsys,
        main(["worker", "submit", REPO, "17", "--json"]),
    )
    assert payload["error"]["details"] == {"mutation_state": "unknown"}
    assert "ghp_secret" not in json.dumps(payload)


def test_text_mode_retains_human_error_behavior(monkeypatch, capsys):
    monkeypatch.setattr(
        worker.gh,
        "list_available_issues",
        lambda _repo: (_ for _ in ()).throw(gh.GitHubError("human diagnostic")),
    )
    assert main(["worker", "list", REPO, "--text"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: human diagnostic\n"


def test_success_payload_is_not_wrapped(monkeypatch, capsys):
    monkeypatch.setattr(worker.gh, "list_available_issues", lambda _repo: [])
    assert main(["worker", "list", REPO, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []

