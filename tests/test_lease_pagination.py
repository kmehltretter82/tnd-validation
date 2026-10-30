"""Complete, bounded lease-comment pagination shared by both readers."""

from __future__ import annotations

import json

import pytest

from client import github
from gate.protocol import PROTOCOL_VERSION
from gate.state import lease_arbiter
from gate.state.lease_comment import ACTION_CLAIM, LeaseClaim, render_lease_comment
from orchestrator import leases


def row(comment_id: int, login: str = "alice") -> dict[str, object]:
    return {
        "id": comment_id,
        "login": login,
        "body": render_lease_comment(
            LeaseClaim(
                login=login,
                action=ACTION_CLAIM,
                protocol=PROTOCOL_VERSION,
                session=f"session-{comment_id}",
            )
        ),
        "updated_at": "2026-10-30T10:00:00Z",
    }


def pages(*items: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(page) for page in items)


def test_back_to_back_pages_are_flattened_without_losing_earliest_claim():
    raw = pages([row(20, "bob")], [row(10, "alice")])
    decoded = lease_arbiter.decode_lease_comment_pages(raw)
    assert [item["id"] for item in decoded] == [20, 10]
    comments = lease_arbiter.lease_comments_from_json(raw)
    decision = lease_arbiter.decide_lease(
        comments,
        stale_after_hours=24,
        now=lease_arbiter.datetime.fromisoformat("2026-10-30T11:00:00+00:00"),
    )
    assert decision.holder == "alice"


def test_one_merged_array_and_empty_thread_are_valid():
    assert [item["id"] for item in lease_arbiter.decode_lease_comment_pages(
        json.dumps([row(1), row(2)])
    )] == [1, 2]
    assert lease_arbiter.decode_lease_comment_pages("[]") == []


@pytest.mark.parametrize(
    "raw,match",
    [
        ("", "empty"),
        ("[{", "malformed or truncated"),
        ('{"id": 1}', "not a JSON array"),
        (json.dumps([{"id": 1}]), "invalid projection"),
        (json.dumps([{**row(1), "id": True}]), "invalid field types"),
        (json.dumps([{**row(1), "updated_at": "not-a-time"}]), "invalid field types"),
        (pages([row(1)], [row(1)]), "duplicate id"),
        ('[{"id":1,"id":2,"login":"a","body":"x","updated_at":"y"}]',
         "duplicate object keys"),
        (json.dumps([row(1)]) + " trailing", "malformed or truncated"),
    ],
)
def test_invalid_or_incomplete_responses_fail_closed(raw, match):
    with pytest.raises(lease_arbiter.LeaseCommentsError, match=match):
        lease_arbiter.decode_lease_comment_pages(raw)


def test_byte_and_comment_count_bounds_fail_closed(monkeypatch):
    raw = json.dumps([row(1)])
    monkeypatch.setattr(lease_arbiter, "MAX_LEASE_COMMENTS_JSON_BYTES", len(raw) - 1)
    with pytest.raises(lease_arbiter.LeaseCommentsError, match="byte limit"):
        lease_arbiter.decode_lease_comment_pages(raw)

    monkeypatch.setattr(lease_arbiter, "MAX_LEASE_COMMENTS_JSON_BYTES", 10_000)
    monkeypatch.setattr(lease_arbiter, "MAX_LEASE_COMMENTS", 1)
    with pytest.raises(lease_arbiter.LeaseCommentsError, match="comment limit"):
        lease_arbiter.decode_lease_comment_pages(json.dumps([row(1), row(2)]))


def test_both_consumers_use_the_shared_multi_page_decoder(monkeypatch):
    raw = pages([row(2, "bob")], [row(1, "alice")])
    monkeypatch.setattr(github, "_run", lambda _argv: raw)
    assert [item["id"] for item in github.list_issue_comments("owner/repo", 7)] == [2, 1]

    monkeypatch.setattr(leases, "_gh", lambda *_argv: raw)
    assert [comment.id for comment in leases.read_lease_comments("owner/repo", 7)] == [2, 1]


def test_client_wraps_decoder_failure_as_github_error(monkeypatch):
    monkeypatch.setattr(github, "_run", lambda _argv: "[{")
    with pytest.raises(github.GitHubError, match="invalid paginated"):
        github.list_issue_comments("owner/repo", 7)


def test_request_uses_explicit_get_pagination_and_page_size():
    argv = lease_arbiter.lease_comments_argv("owner/repo", 7)
    assert argv[:4] == ["api", "--method", "GET", "--paginate"]
    assert argv[argv.index("-F") + 1] == "per_page=100"
