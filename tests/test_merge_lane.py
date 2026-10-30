"""The serialized merge lane adds no authority and stays off until validated."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from orchestrator import merge_lane, prs

REPO = "owner/tndlib"
HEAD = "a" * 40
WORKFLOWS = Path(".github/workflows")


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def test_candidate_is_bound_to_the_requested_head_with_no_override(monkeypatch):
    calls = []
    monkeypatch.setattr(
        merge_lane, "merge_pr", lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    merge_lane.merge_candidate(REPO, "7", HEAD)
    assert calls == [((REPO, 7), {"prover": "lean4", "expected_head_sha": HEAD})]


@pytest.mark.parametrize(
    "number, head",
    [
        ("0", HEAD), ("-1", HEAD), ("7 ", HEAD), ("7\n", HEAD), ("abc", HEAD), ("", HEAD),
        ("7", "short"), ("7", "A" * 40), ("7", HEAD + "\n"), ("7", "main"),
    ],
)
def test_malformed_dispatch_inputs_are_refused_before_any_read(monkeypatch, number, head):
    def unreachable(*_args, **_kwargs):
        raise AssertionError("must not reach merge_pr")

    monkeypatch.setattr(merge_lane, "merge_pr", unreachable)
    with pytest.raises(prs.PRError):
        merge_lane.merge_candidate(REPO, number, head)


def test_moved_head_is_refused_before_any_further_read_or_merge(monkeypatch):
    monkeypatch.setattr(
        prs, "get_pr", lambda *_args: SimpleNamespace(head_sha="b" * 40),
    )

    def unreachable(*_args):
        raise AssertionError("no further GitHub call after the head mismatch")

    monkeypatch.setattr(prs, "_gh", unreachable)
    with pytest.raises(prs.PRError, match="not the requested"):
        prs.merge_pr(REPO, 7, prover="lean4", expected_head_sha=HEAD)


def test_refusal_exits_nonzero_without_a_traceback(monkeypatch, capsys):
    def refuse(*_args, **_kwargs):
        raise prs.PRError("not green")

    monkeypatch.setattr(merge_lane, "merge_pr", refuse)
    status = merge_lane.main(["--repo", REPO, "--pr", "7", "--head-sha", HEAD])
    assert status == 1
    assert "merge refused: not green" in capsys.readouterr().err


def test_verification_and_merge_share_one_queued_lane():
    verify = workflow("verify-tnd.yml")["concurrency"]
    merge = workflow("tnd-merge.yml")["concurrency"]
    assert verify["group"] == "tnd-candidate-lane-${{ github.event.pull_request.number }}"
    assert merge["group"] == "tnd-candidate-lane-${{ inputs.pr }}"
    for lane in (verify, merge):
        assert lane["cancel-in-progress"] is False
        assert lane["queue"] == "max"


def test_merge_workflow_is_off_by_default_and_runs_only_maintained_main():
    parsed = workflow("tnd-merge.yml")
    # PyYAML reads the bare `on` key as boolean true.
    assert set(parsed[True]) == {"workflow_dispatch"}
    assert parsed["permissions"] == {"contents": "read"}
    job = parsed["jobs"]["merge"]
    assert "vars.TND_MERGE_LANE_ENABLED == 'true'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert job["timeout-minutes"] > 0
    checkout = job["steps"][0]
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    source = (WORKFLOWS / "tnd-merge.yml").read_text()
    assert "pull_request.head" not in source
    # Inputs reach the shell only through the environment.
    run = next(step["run"] for step in job["steps"] if "merge_lane" in step.get("run", ""))
    assert "inputs." not in run


def test_merge_token_is_scoped_to_the_environment_and_never_the_default():
    job = workflow("tnd-merge.yml")["jobs"]["merge"]
    assert job["environment"] == "tnd-merge"
    step = next(step for step in job["steps"] if "merge_lane" in step.get("run", ""))
    assert step["env"]["GH_TOKEN"] == "${{ secrets.TND_MERGE_TOKEN }}"
    assert 'test -n "$GH_TOKEN"' in step["run"]
