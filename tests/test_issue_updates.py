"""Fail-closed lifecycle issue mutation tests; no GitHub calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gate.state import issue_updates
from gate.state.close_on_merge_cli import main as close_on_merge_main
from gate.state.intake_cli import build_payload

REPO = "kmehltretter82/tndlib"


def task_body() -> str:
    text = Path("docs/API.md").read_text()
    return text.split("```yaml\n", 1)[1].split("\n```", 1)[0]


def write_inputs(tmp_path, result, *, body: str | None = None):
    result_path = tmp_path / "result.json"
    body_path = tmp_path / "body.txt"
    result_path.write_text(json.dumps(result))
    body_path.write_text(task_body() if body is None else body)
    return result_path, body_path


class FakeGitHub:
    def __init__(self, *, author: str = "kmehltretter82"):
        self.issue = {
            "number": 17,
            "state": "open",
            "user": {"login": author},
            "body": task_body(),
            "labels": [
                {"name": "choir/task"},
                {"name": "choir/available"},
                {"name": "topic:logic"},
            ],
        }
        self.comments: list[dict] = []
        self.patch_payloads: list[dict] = []

    def api(self, method: str, endpoint: str, payload=None):
        if endpoint == f"repos/{REPO}/issues/17" and method == "GET":
            return json.loads(json.dumps(self.issue))
        if endpoint == f"repos/{REPO}/issues/17" and method == "PATCH":
            self.patch_payloads.append(payload)
            self.issue["labels"] = [{"name": name} for name in payload["labels"]]
            if "state" in payload:
                self.issue["state"] = payload["state"]
            return json.loads(json.dumps(self.issue))
        if endpoint == f"repos/{REPO}/issues/17/comments" and method == "POST":
            comment = {"id": len(self.comments) + 1, "body": payload["body"]}
            self.comments.append(comment)
            return dict(comment)
        raise AssertionError((method, endpoint, payload))


@pytest.fixture
def fake(monkeypatch):
    service = FakeGitHub()
    monkeypatch.setattr(issue_updates, "_gh_json", service.api)
    monkeypatch.setattr(issue_updates, "_gh_comment_pages", lambda *_: service.comments)
    return service


def test_quarantine_removes_availability_and_verifies_invalid_state(fake):
    issue_updates.quarantine(REPO, 17, mark_invalid=True)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert labels == {"choir/task", "choir/invalid", "topic:logic"}
    assert fake.patch_payloads[-1] == {"labels": sorted(labels)}


def test_quarantine_handles_null_body_before_marking_invalid(fake):
    fake.issue["body"] = None
    issue_updates.quarantine(REPO, 17, mark_invalid=True)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert "choir/available" not in labels
    assert "choir/invalid" in labels


def test_apply_intake_sets_exact_labels_and_posts_acknowledgement(fake, tmp_path):
    issue_updates.quarantine(REPO, 17)
    result = build_payload(task_body(), repo=REPO, allowed_extensions=(".lean",))
    result_path, body_path = write_inputs(tmp_path, result)
    issue_updates.apply_intake(REPO, 17, result_path, body_path)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert {"choir/task", "choir/available", "choir/type:prove"} <= labels
    assert "choir/invalid" not in labels
    assert len(fake.comments) == 1
    assert "choir-intake-ack:" in fake.comments[0]["body"]


def test_rejected_intake_cannot_restore_available_label(fake, tmp_path):
    issue_updates.quarantine(REPO, 17)
    result = build_payload(task_body().replace("deps: []", "unexpected: true"), repo=REPO)
    rejected_body = task_body().replace("deps: []", "unexpected: true")
    result_path, body_path = write_inputs(tmp_path, result, body=rejected_body)
    fake.issue["body"] = rejected_body
    issue_updates.apply_intake(REPO, 17, result_path, body_path)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert "choir/invalid" in labels
    assert "choir/available" not in labels


def test_successful_intake_clears_conflicting_lifecycle_and_type_labels(fake, tmp_path):
    fake.issue["labels"].extend(
        [
            {"name": "choir/claimed"},
            {"name": "choir/done"},
            {"name": "choir/invalid"},
            {"name": "choir/type:golf"},
        ]
    )
    result = build_payload(task_body(), repo=REPO, allowed_extensions=(".lean",))
    result_path, body_path = write_inputs(tmp_path, result)
    issue_updates.apply_intake(REPO, 17, result_path, body_path)
    assert {item["name"] for item in fake.issue["labels"]} == {
        "choir/task", "choir/available", "choir/type:prove", "topic:logic",
    }


def test_intake_refuses_body_changed_after_validation_and_leaves_quarantined(
    fake, tmp_path,
):
    issue_updates.quarantine(REPO, 17)
    result = build_payload(task_body(), repo=REPO, allowed_extensions=(".lean",))
    result_path, body_path = write_inputs(tmp_path, result)
    fake.issue["body"] += "\nchanged during run"
    with pytest.raises(issue_updates.IssueUpdateError, match="body changed"):
        issue_updates.apply_intake(REPO, 17, result_path, body_path)
    assert "choir/available" not in {item["name"] for item in fake.issue["labels"]}


def test_intake_quarantines_if_body_changes_during_label_mutation(
    fake, tmp_path, monkeypatch,
):
    result = build_payload(task_body(), repo=REPO, allowed_extensions=(".lean",))
    result_path, body_path = write_inputs(tmp_path, result)
    original = fake.api

    def body_changes_after_write(method, endpoint, payload=None):
        response = original(method, endpoint, payload)
        if method == "GET" and fake.patch_payloads:
            response["body"] = task_body() + "\nchanged during write"
        return response

    monkeypatch.setattr(issue_updates, "_gh_json", body_changes_after_write)
    with pytest.raises(issue_updates.IssueUpdateError, match="issue changed"):
        issue_updates.apply_intake(REPO, 17, result_path, body_path)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert "choir/available" not in labels
    assert "choir/invalid" in labels


def test_complete_requires_owner_task_and_establishes_one_idempotent_comment(fake):
    issue_updates.complete_task(REPO, 17, 23)
    labels = {item["name"] for item in fake.issue["labels"]}
    assert fake.issue["state"] == "closed"
    assert labels == {"choir/task", "choir/done", "topic:logic"}
    assert fake.patch_payloads[-1] == {
        "labels": sorted(labels), "state": "closed", "state_reason": "completed",
    }
    issue_updates.complete_task(REPO, 17, 23)
    assert len(fake.comments) == 1
    assert "tnd-merged-pr:23" in fake.comments[0]["body"]


def test_complete_refuses_non_owner_or_non_task(monkeypatch):
    for service in (FakeGitHub(author="contributor"), FakeGitHub()):
        if service.issue["user"]["login"] == "kmehltretter82":
            service.issue["labels"] = [{"name": "choir/available"}]
        monkeypatch.setattr(issue_updates, "_gh_json", service.api)
        monkeypatch.setattr(issue_updates, "_gh_comment_pages", lambda *_: [])
        with pytest.raises(issue_updates.IssueUpdateError, match="owner-approved"):
            issue_updates.complete_task(REPO, 17, 23)
        assert service.patch_payloads == []


def test_postcondition_mismatch_fails_closed(fake, monkeypatch):
    original = fake.api

    def lose_patch(method, endpoint, payload=None):
        result = original(method, endpoint, payload)
        if method == "GET" and fake.patch_payloads:
            result["labels"] = [{"name": "choir/available"}]
        return result

    monkeypatch.setattr(issue_updates, "_gh_json", lose_patch)
    with pytest.raises(issue_updates.IssueUpdateError, match="postcondition"):
        issue_updates.quarantine(REPO, 17)


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "error", "add_labels": ["choir/invalid"], "remove_labels": [],
         "comment": "bad", "should_post_comment": True},
        {"status": "ok", "add_labels": ["choir/available"],
         "remove_labels": ["choir/available"], "comment": "bad",
         "should_post_comment": True},
    ],
)
def test_invalid_intake_label_contract_is_rejected_before_mutation(fake, tmp_path, payload):
    result_path, body_path = write_inputs(tmp_path, payload)
    with pytest.raises(issue_updates.IssueUpdateError):
        issue_updates.apply_intake(REPO, 17, result_path, body_path)
    assert fake.patch_payloads == []


@pytest.mark.parametrize(
    ("body", "expected_count"),
    [("No link", 0), ("Closes #17 and fixes #18", 2)],
)
def test_close_extraction_refuses_anything_but_one_unique_reference(
    tmp_path, capsys, body, expected_count,
):
    body_path = tmp_path / "pr-body.txt"
    body_path.write_text(body)
    assert close_on_merge_main(["--body-file", str(body_path)]) == 1
    assert f"found {expected_count}" in capsys.readouterr().err


def test_close_extraction_emits_the_single_unique_reference(tmp_path, capsys):
    body_path = tmp_path / "pr-body.txt"
    body_path.write_text("Closes #17; also resolves #17")
    assert close_on_merge_main(["--body-file", str(body_path)]) == 0
    assert capsys.readouterr().out == "17\n"
