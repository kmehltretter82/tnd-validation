"""Post-merge sibling repinning is exhaustive, retryable, and fail-closed."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orchestrator import repin
from orchestrator.tasks.api import MaintainerError

REPO = "owner/tndlib"
OLD = "a" * 40
MERGE = "b" * 40
HEAD = "c" * 40
STRAY = "d" * 40


def handle(number: int, commit: str, target: str = "TNDLib/Logic.lean"):
    return SimpleNamespace(
        number=number,
        record=SimpleNamespace(
            target_file=target,
            project_ref=SimpleNamespace(commit=commit),
        ),
    )


@pytest.fixture
def github(monkeypatch):
    """Answer the ancestry reads; history is OLD -> MERGE -> HEAD, STRAY is off it."""
    order = [OLD, MERGE, HEAD]

    def is_ancestor(_repo, ancestor, descendant):
        return (
            ancestor in order
            and descendant in order
            and order.index(ancestor) <= order.index(descendant)
        )

    monkeypatch.setattr(repin, "current_main_head", lambda _repo: HEAD)
    monkeypatch.setattr(repin, "commit_is_ancestor", is_ancestor)


def compare_payload(status, base=OLD, merge_base=OLD):
    return {
        "status": status,
        "base_commit": {"sha": base},
        "merge_base_commit": {"sha": merge_base},
    }


def test_repin_attempts_every_eligible_task_and_aggregates_failures(
    monkeypatch, github,
):
    monkeypatch.setattr(
        repin,
        "list_choir_tasks",
        lambda *_args, **_kwargs: [handle(1, OLD), handle(2, OLD), handle(3, OLD)],
    )
    calls = []

    def set_pin(_repo, number, commit, *, expected_commit):
        calls.append((number, commit, expected_commit))
        if number == 2:
            raise MaintainerError("write refused")

    monkeypatch.setattr(repin, "set_task_pin", set_pin)
    result = repin.repin_available(REPO, MERGE, ["TNDLib/Logic.lean"])
    assert calls == [(1, HEAD, OLD), (2, HEAD, OLD), (3, HEAD, OLD)]
    assert [item["issue"] for item in result["repinned"]] == [1, 3]
    assert result["event_commit"] == MERGE
    assert result["commit"] == HEAD
    assert result["failed"] == [{
        "issue": 2,
        "target_file": "TNDLib/Logic.lean",
        "from": OLD,
        "to": HEAD,
        "reason": "write refused",
    }]


def test_retry_skips_successes_and_retries_only_the_prior_failure(monkeypatch, github):
    pins = {1: OLD, 2: OLD}
    calls = []
    fail_once = {2}

    def list_tasks(*_args, **_kwargs):
        return [handle(number, commit) for number, commit in pins.items()]

    def set_pin(_repo, number, commit, *, expected_commit):
        assert pins[number] == expected_commit
        calls.append(number)
        if number in fail_once:
            fail_once.remove(number)
            raise MaintainerError("transient write failure")
        pins[number] = commit

    monkeypatch.setattr(repin, "list_choir_tasks", list_tasks)
    monkeypatch.setattr(repin, "set_task_pin", set_pin)
    first = repin.repin_available(REPO, MERGE, ["TNDLib/Logic.lean"])
    second = repin.repin_available(REPO, MERGE, ["TNDLib/Logic.lean"])
    assert [item["issue"] for item in first["failed"]] == [2]
    assert second["failed"] == []
    assert [item["issue"] for item in second["repinned"]] == [2]
    assert calls == [1, 2, 2]
    assert pins == {1: HEAD, 2: HEAD}


def test_rerunning_an_older_merge_pins_forward_to_head_never_to_the_event(
    monkeypatch, github,
):
    written = []
    monkeypatch.setattr(
        repin,
        "list_choir_tasks",
        lambda *_args, **_kwargs: [handle(1, HEAD), handle(2, MERGE)],
    )
    monkeypatch.setattr(
        repin,
        "set_task_pin",
        lambda _repo, number, commit, *, expected_commit: written.append(
            (number, commit, expected_commit)
        ),
    )
    result = repin.repin_available(REPO, OLD, ["TNDLib/Logic.lean"])
    assert written == [(2, HEAD, MERGE)]
    assert [item["issue"] for item in result["repinned"]] == [2]


def test_event_commit_off_main_history_refuses_the_whole_batch(monkeypatch, github):
    def unreachable(*_args, **_kwargs):
        raise AssertionError("must fail before listing or writing tasks")

    monkeypatch.setattr(repin, "list_choir_tasks", unreachable)
    monkeypatch.setattr(repin, "set_task_pin", unreachable)
    with pytest.raises(MaintainerError, match="not on the current main history"):
        repin.repin_available(REPO, STRAY, ["TNDLib/Logic.lean"])


def test_task_pin_off_main_history_fails_without_a_write(monkeypatch, github):
    written = []
    monkeypatch.setattr(
        repin,
        "list_choir_tasks",
        lambda *_args, **_kwargs: [handle(1, STRAY), handle(2, OLD)],
    )
    monkeypatch.setattr(
        repin,
        "set_task_pin",
        lambda _repo, number, *_args, **_kwargs: written.append(number),
    )
    result = repin.repin_available(REPO, MERGE, ["TNDLib/Logic.lean"])
    assert written == [2]
    assert [item["issue"] for item in result["failed"]] == [1]
    assert "non-forward" in result["failed"][0]["reason"]


@pytest.mark.parametrize(
    "payload, expected",
    [
        (compare_payload("ahead"), True),
        (compare_payload("identical"), False),
        (compare_payload("behind"), False),
        (compare_payload("diverged", merge_base=STRAY), False),
        (compare_payload("ahead", base=STRAY), False),
        (compare_payload("ahead", merge_base=STRAY), False),
    ],
)
def test_ancestry_requires_github_to_confirm_the_exact_forward_move(
    monkeypatch, payload, expected,
):
    monkeypatch.setattr(repin, "_gh_json", lambda _endpoint: payload)
    assert repin.commit_is_ancestor(REPO, OLD, HEAD) is expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": "ahead", "base_commit": {"sha": OLD}},
        compare_payload("ahead", base="short"),
        compare_payload("ahead", merge_base=None),
        compare_payload("sideways"),
    ],
)
def test_malformed_comparison_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(repin, "_gh_json", lambda _endpoint: payload)
    with pytest.raises(MaintainerError):
        repin.commit_is_ancestor(REPO, OLD, HEAD)


def test_identical_commits_are_forward_without_a_github_read(monkeypatch):
    def unreachable(_endpoint):
        raise AssertionError("no read is needed for an identical commit")

    monkeypatch.setattr(repin, "_gh_json", unreachable)
    assert repin.commit_is_ancestor(REPO, OLD, OLD) is True


@pytest.mark.parametrize("value", ["abc", "A" * 40, None, 7])
def test_ancestry_rejects_non_sha_inputs_before_any_read(monkeypatch, value):
    def unreachable(_endpoint):
        raise AssertionError("no read for an invalid commit")

    monkeypatch.setattr(repin, "_gh_json", unreachable)
    with pytest.raises(MaintainerError):
        repin.commit_is_ancestor(REPO, value, HEAD)


@pytest.mark.parametrize(
    "payload", [{}, {"object": None}, {"object": {"sha": "short"}}],
)
def test_malformed_main_ref_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(repin, "_gh_json", lambda _endpoint: payload)
    with pytest.raises(MaintainerError):
        repin.current_main_head(REPO)


@pytest.mark.parametrize("failed, expected", [([], 0), ([{"issue": 2}], 1)])
def test_cli_exit_status_reflects_aggregate_failures(
    monkeypatch, tmp_path, capsys, failed, expected,
):
    files = tmp_path / "files.txt"
    files.write_text("TNDLib/Logic.lean\n")
    result = {"commit": HEAD, "repinned": [], "failed": failed}
    monkeypatch.setattr(repin, "repin_available", lambda *_: result)
    status = repin.main([
        "--repo", REPO, "--commit", MERGE, "--files-file", str(files),
    ])
    assert status == expected
    assert json.loads(capsys.readouterr().out) == result
