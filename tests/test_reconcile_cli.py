"""Fail-closed reconciliation writer tests; no GitHub calls."""

from __future__ import annotations

import json

import pytest

from gate.reconcile import cli
from gate.reconcile.stale_claims import IssueView, StaleClaim

REPO = "owner/tndlib"


class FakeIssue:
    def __init__(self):
        self.labels = {
            "choir/claimed", "choir/heartbeat:2026-01-01", "topic:logic",
        }
        self.assignees = {"alice", "bob"}
        self.label_error_after_write = False
        self.label_error_without_write = False

    def gh(self, *args: str) -> str:
        if args[:2] == ("issue", "view"):
            return json.dumps({
                "state": "OPEN",
                "labels": [{"name": name} for name in sorted(self.labels)],
                "assignees": [{"login": login} for login in sorted(self.assignees)],
            })
        if "--remove-assignee" in args:
            self.assignees.discard(args[args.index("--remove-assignee") + 1])
            return ""
        if args[:2] == ("issue", "edit"):
            if not self.label_error_without_write:
                for index, value in enumerate(args[:-1]):
                    if value == "--remove-label":
                        self.labels.discard(args[index + 1])
                self.labels.add(args[args.index("--add-label") + 1])
            if self.label_error_after_write or self.label_error_without_write:
                raise RuntimeError("opaque gh failure")
            return ""
        raise AssertionError(args)


@pytest.fixture
def stale():
    issue = IssueView(
        number=17,
        labels=["choir/claimed", "choir/heartbeat:2026-01-01", "topic:logic"],
        updated_at="2026-01-01T00:00:00Z",
        assignees=["alice", "bob"],
    )
    claim = StaleClaim(17, "heartbeat expired", "choir/heartbeat:2026-01-01")
    return issue, claim


def test_reconciliation_establishes_exact_labels_assignees_and_comment(
    monkeypatch, stale,
):
    service = FakeIssue()
    comments = []
    monkeypatch.setattr(cli, "_gh", service.gh)
    monkeypatch.setattr(cli, "ensure_comment", lambda *args: comments.append(args))
    issue, claim = stale
    cli.apply_stale(REPO, claim, issue)
    assert service.labels == {"choir/available", "topic:logic"}
    assert service.assignees == set()
    assert comments and "back to `choir/available`" in comments[0][2]


def test_reconciliation_accepts_transport_error_only_when_postcondition_holds(
    monkeypatch, stale,
):
    service = FakeIssue()
    service.label_error_after_write = True
    monkeypatch.setattr(cli, "_gh", service.gh)
    monkeypatch.setattr(cli, "ensure_comment", lambda *_: None)
    cli.apply_stale(REPO, stale[1], stale[0])
    assert service.labels == {"choir/available", "topic:logic"}


def test_reconciliation_fails_when_label_postcondition_is_absent(monkeypatch, stale):
    service = FakeIssue()
    service.label_error_without_write = True
    monkeypatch.setattr(cli, "_gh", service.gh)
    monkeypatch.setattr(cli, "ensure_comment", lambda *_: None)
    with pytest.raises(RuntimeError, match="opaque gh failure"):
        cli.apply_stale(REPO, stale[1], stale[0])


def test_reconciliation_command_returns_failure_if_any_write_fails(monkeypatch, stale):
    monkeypatch.setattr(cli, "fetch_claimed", lambda *_: [stale[0]])
    monkeypatch.setattr(cli, "identify_stale", lambda *_args, **_kwargs: [stale[1]])
    monkeypatch.setattr(cli, "apply_stale", lambda *_: (_ for _ in ()).throw(
        RuntimeError("write failed")
    ))
    assert cli.main(["--repo", REPO, "--threshold-days", "7"]) == 1


def test_claimed_issue_listing_fails_instead_of_silently_truncating(monkeypatch):
    issue = {"number": 1, "labels": [], "updatedAt": "", "assignees": []}
    monkeypatch.setattr(
        cli,
        "_gh",
        lambda *_: json.dumps([issue] * (cli.MAX_CLAIMED + 1)),
    )
    with pytest.raises(RuntimeError, match="safety bound"):
        cli.fetch_claimed(REPO)
