"""Check documented task records and public CLI outcomes without GitHub writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from choir_cli import main
from client import cli as worker
from client.lease import ClaimOutcome, ClaimResult
from client.release import ReleaseResult
from client.submit import SubmitResult
from client.workspace import WorkspaceError
from gate.state.intake import ParseSuccess, parse_issue_body
from gate.state.intake_cli import build_payload
from orchestrator.tasks import api

REPO = "kmehltretter82/tndlib"
BASE = "a" * 40


def documented_task() -> str:
    text = Path("docs/API.md").read_text()
    return text.split("```yaml\n", 1)[1].split("\n```", 1)[0]


def test_documented_task_roundtrips_and_matches_approved_sample():
    parsed = parse_issue_body(documented_task(), expected_repo=REPO,
                              allowed_extensions=(".lean",))
    assert isinstance(parsed, ParseSuccess)
    approved = json.loads(Path("audit/tasks.json").read_text())["tasks"][0]
    assert parsed.record.target_file == approved["source_path"]
    assert parsed.record.target_decl in approved["expected_exports"]
    assert parsed.record.project_ref.commit == BASE
    assert parsed.record.project_ref.toolchain == Path("lean-toolchain").read_text().strip()


def test_request_and_draft_templates_do_not_self_approve():
    request = yaml.safe_load(Path(".github/ISSUE_TEMPLATE/request.yml").read_text())
    assert request.get("labels") == ["tnd/proposal"]
    assert not any(label.startswith("choir/") for label in request["labels"])
    assert "proposal" in request["body"][0]["attributes"]["value"].lower()
    template = Path(".github/ISSUE_TEMPLATE/choir-task.md").read_text()
    _, metadata, body = template.split("---", 2)
    assert not yaml.safe_load(metadata).get("labels")
    body = body.replace("APPROVED_TASK", "map_exists").replace(
        "APPROVED_DECLARATION", "mapExists"
    ).replace("PASTE_HEAD_SHA_HERE", BASE)
    assert isinstance(parse_issue_body(body, expected_repo=REPO,
                                       allowed_extensions=(".lean",)), ParseSuccess)


def test_intake_rejection_has_documented_machine_readable_code():
    rejected = build_payload(documented_task().replace("deps: []", "unexpected: true"),
                             repo=REPO, allowed_extensions=(".lean",))
    assert rejected["status"] == "error"
    assert {e["code"] for e in rejected["errors"]} == {"missing_field", "unknown_field"}
    assert "choir/available" in rejected["remove_labels"]
    assert all(set(e) == {"code", "field", "message", "hint"} for e in rejected["errors"])


def test_documented_owner_publish_command_serializes_approved_task(monkeypatch, capsys):
    calls = []

    def fake_gh(*args):
        calls.append(args)
        return f"https://github.com/{REPO}/issues/17\n"

    monkeypatch.setattr(api, "_gh", fake_gh)
    assert main([
        "orch", "--repo", REPO, "--prover", "lean4", "create-task",
        "--title", "Prove TNDTask.mapExists", "--type", "prove",
        "--target-file", "tasks/map_exists.lean", "--target-decl", "TNDTask.mapExists",
        "--commit", BASE, "--toolchain", "leanprover/lean4:v4.35.0",
        "--prose", "Source and explanation reviewed by the owner.",
    ]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "created": True, "number": 17, "title": "Prove TNDTask.mapExists",
    }
    assert len(calls) == 1
    args = calls[0]
    assert args[:2] == ("issue", "create")
    body = args[args.index("--body") + 1]
    assert isinstance(parse_issue_body(body, expected_repo=REPO), ParseSuccess)
    assert "choir/task" in args and "choir/available" in args


@pytest.mark.parametrize("outcome", [
    ClaimOutcome.LOST_RACE, ClaimOutcome.SKIPPED, ClaimOutcome.ERROR,
])
def test_claim_nonwinning_json_outcomes_exit_zero(monkeypatch, capsys, outcome):
    monkeypatch.setattr(worker, "claim", lambda *_: ClaimResult(outcome, "diagnostic"))
    assert main(["worker", "claim", REPO, "17", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == outcome.name
    assert result["prepared"] is None
    assert result["reason"] == "diagnostic"


def test_won_claim_with_failed_setup_does_not_claim_prepared_workspace(monkeypatch, capsys):
    monkeypatch.setattr(worker, "claim", lambda *_: ClaimResult(ClaimOutcome.WON, session="a" * 16))

    def failed(*args, **kwargs):
        raise WorkspaceError("fixture setup failure")

    monkeypatch.setattr(worker, "prepare_task", failed)
    assert main(["worker", "claim", REPO, "17", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "WON"
    assert result["prepared"] is None
    assert result["session"] == "a" * 16
    assert result["setup_failed"] == "fixture setup failure"


def test_heartbeat_false_is_not_hidden_by_success_exit(monkeypatch, capsys):
    monkeypatch.setattr(worker, "heartbeat_for_issue", lambda *args, **kwargs: (False, None))
    assert main(["worker", "heartbeat", REPO, "17", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "refreshed": False, "repo": REPO, "issue": 17, "session": None,
    }


def test_documented_release_preserves_workspace(monkeypatch, capsys):
    def release(repo, issue, *, keep_workspace):
        assert (repo, issue, keep_workspace) == (REPO, 17, True)
        return ReleaseResult(comment_posted=True, workspace_removed=False)

    monkeypatch.setattr(worker, "release_for_issue", release)
    assert main(["worker", "release", REPO, "17", "--keep-workspace", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "comment_posted": True, "workspace_removed": False,
    }


def test_resubmission_returns_existing_pr_metadata(monkeypatch, capsys):
    url = f"https://github.com/{REPO}/pull/18"
    monkeypatch.setattr(worker, "submit_for_issue", lambda *_: SubmitResult(18, url, True))
    assert main(["worker", "submit", REPO, "17", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "pr_number": 18, "pr_url": url, "reused_existing_pr": True,
    }


def test_every_registered_task_matches_its_admission_policy_and_placeholder():
    registry = json.loads(Path("audit/tasks.json").read_text())["tasks"]
    policy = {
        entry["id"]: entry
        for entry in json.loads(Path("audit/admission/policy.json").read_text())["task_files"]
    }
    assert {task["id"] for task in registry} == set(policy)
    assert len(registry) == 7
    for task in registry:
        entry = policy[task["id"]]
        text = Path(task["source_path"]).read_bytes()
        assert entry["source_path"] == task["source_path"]
        assert entry["declarations"] == task["expected_exports"]
        assert hashlib.sha256(text).hexdigest() == entry["challenge_sha256"]
        assert b"sorry" in text
        # The comparator compares statements, so a definition cannot be a task.
        assert b"\ntheorem " in text and b"\ndef " not in text
