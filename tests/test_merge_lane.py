"""The serialized merge lane adds no authority and stays off until validated."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from gate.checks import BRANCH_PROTECTION_CONTEXTS, REQUIRED_PRESENT
from orchestrator import config_audit, github_app, governance, merge_lane, prs
from orchestrator.tnd_verification import require_app_only_merge_ruleset

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
    assert "GH_TOKEN" not in step["env"]
    assert step["env"]["TND_MERGE_APP_ID"] == "${{ secrets.TND_MERGE_APP_ID }}"
    assert step["env"]["TND_MERGE_APP_PRIVATE_KEY"] == "${{ secrets.TND_MERGE_APP_PRIVATE_KEY }}"
    assert step["env"]["TND_MERGE_ACTOR"] == "${{ github.actor }}"
    assert 'test -n "$TND_MERGE_APP_ID"' in step["run"]
    assert 'test -n "$TND_MERGE_APP_PRIVATE_KEY"' in step["run"]


def test_merge_candidate_mints_app_token_when_app_credentials_are_set(monkeypatch):
    calls = []
    monkeypatch.setenv("TND_MERGE_APP_ID", "12345")
    monkeypatch.setenv("TND_MERGE_APP_PRIVATE_KEY", "fake-pem")
    monkeypatch.setenv("TND_MERGE_ACTOR", "kmehltretter82")
    monkeypatch.setattr(
        merge_lane,
        "mint_installation_token",
        lambda repo, app_id, key: f"ghs_{repo}_{app_id}",
    )
    monkeypatch.setattr(
        merge_lane, "merge_pr", lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    assert merge_lane.main(["--repo", REPO, "--pr", "7", "--head-sha", HEAD]) == 0
    assert calls == [
        (
            (REPO, 7),
            {
                "prover": "lean4",
                "expected_head_sha": HEAD,
                "actor": "kmehltretter82",
                "app_id": 12345,
            },
        )
    ]


def test_app_only_merge_ruleset_requires_active_main_update_rule_and_sole_app_bypass():
    valid = [
        {
            "id": 42,
            "name": "tnd-merge-lane-only",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "rules": [{"type": "update"}],
            "bypass_actors": [
                {"actor_type": "Integration", "actor_id": 12345, "bypass_mode": "always"}
            ],
        }
    ]
    require_app_only_merge_ruleset(valid, app_id=12345)
    for invalid in (
        [],
        [{**valid[0], "enforcement": "evaluate"}],
        [{**valid[0], "rules": [{"type": "deletion"}]}],
        [
            {
                **valid[0],
                "conditions": {
                    "ref_name": {"include": ["~ALL"], "exclude": ["refs/heads/main"]}
                },
            }
        ],
        [{**valid[0], "bypass_actors": []}],
        [
            {
                **valid[0],
                "bypass_actors": [
                    {
                        "actor_type": "RepositoryRole",
                        "actor_id": 5,
                        "bypass_mode": "always",
                    }
                ],
            }
        ],
        [
            {
                **valid[0],
                "bypass_actors": [
                    {
                        "actor_type": "Integration",
                        "actor_id": 99999,
                        "bypass_mode": "always",
                    }
                ],
            }
        ],
    ):
        with pytest.raises(ValueError, match="ruleset"):
            require_app_only_merge_ruleset(invalid, app_id=12345)


def test_governance_policy_and_review_authorization():
    policy = governance.validate_governance(
        {
            "schema_version": 1,
            "superadmin": "kmehltretter82",
            "admins": ["alice-admin"],
            "reviewers": ["bob-reviewer"],
        }
    )
    assert policy.is_superadmin("kmehltretter82")
    assert policy.is_maintainer("alice-admin")
    assert not policy.is_superadmin("alice-admin")
    assert policy.is_reviewer("bob-reviewer")
    assert not policy.is_maintainer("bob-reviewer")

    # Proof PR requires reviewer approval or reviewer dispatch.
    with pytest.raises(ValueError, match="authorized TND reviewer"):
        governance.require_review_authorization(
            pr_author="contributor",
            actor="outsider",
            reviews=[],
            head_sha=HEAD,
            is_maintainer_pr=False,
            files=["tasks/map_exists.lean"],
            repo="kmehltretter82/tndlib",
            governance=policy,
        )
    governance.require_review_authorization(
        pr_author="contributor",
        actor="bob-reviewer",
        reviews=[],
        head_sha=HEAD,
        is_maintainer_pr=False,
        files=["tasks/map_exists.lean"],
        repo="kmehltretter82/tndlib",
        governance=policy,
    )

    # Superadmin-only paths (.choir/governance.json, .choir/certification.json)
    # cannot be merged by an ordinary admin without superadmin approval on HEAD.
    with pytest.raises(ValueError, match="superadmin approval"):
        governance.require_review_authorization(
            pr_author="alice-admin",
            actor="alice-admin",
            reviews=[],
            head_sha=HEAD,
            is_maintainer_pr=True,
            files=[".choir/governance.json"],
            repo="kmehltretter82/tndlib",
            governance=policy,
        )
    governance.require_review_authorization(
        pr_author="alice-admin",
        actor="alice-admin",
        reviews=[
            {"user": {"login": "kmehltretter82"}, "state": "APPROVED", "commit_id": HEAD}
        ],
        head_sha=HEAD,
        is_maintainer_pr=True,
        files=[".choir/governance.json"],
        repo="kmehltretter82/tndlib",
        governance=policy,
    )


def test_maintainer_pr_merges_through_lane_when_regression_and_audit_are_green(monkeypatch):
    checks = tuple(
        prs.CheckResult(name, "COMPLETED", "SUCCESS")
        for name in (*REQUIRED_PRESENT, "regression")
    )
    pr = prs.PRView(
        number=12,
        title="Promote map_exists",
        url="https://example.invalid/pr/12",
        author="kmehltretter82",
        state="open",
        body="Promote map_exists\n\ntnd-pr-mode: maintainer\n",
        base_sha="b" * 40,
        head_sha=HEAD,
        labels=(),
        files=("TNDLib.lean", "TNDLib/Existential.lean", "audit/exports.json"),
        checks=checks,
        linked_issues=(),
        mergeable="MERGEABLE",
        head_repo="kmehltretter82/tndlib",
    )
    run = {
        "id": 1,
        "event": "pull_request_target",
        "path": ".github/workflows/verify-tnd.yml",
        "head_sha": HEAD,
        "display_title": f"TND PR 12 head:{HEAD} base:{'b' * 40}",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "created_at": "2026-10-31T09:00:00Z",
        "run_started_at": "2026-10-31T09:00:00Z",
    }
    protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "strict": True,
            "contexts": list(BRANCH_PROTECTION_CONTEXTS),
        },
    }
    ruleset = {
        "id": 42,
        "name": "tnd-merge-lane-only",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "update"}],
        "bypass_actors": [
            {"actor_type": "Integration", "actor_id": 12345, "bypass_mode": "always"}
        ],
    }
    calls = []

    def gh(*args):
        calls.append(args)
        if args[0] == "api":
            endpoint = args[-1]
            if endpoint.endswith("/protection"):
                return __import__("json").dumps(protection)
            if endpoint.endswith("/rulesets"):
                return __import__("json").dumps(
                    [{"id": 42, "enforcement": "active", "target": "branch"}]
                )
            if endpoint.endswith("/rulesets/42"):
                return __import__("json").dumps(ruleset)
            if "/reviews" in args:
                return "[[]]"
            for arg in args:
                if "/reviews" in str(arg):
                    return "[[]]"
            return __import__("json").dumps([{"total_count": 1, "workflow_runs": [run]}])
        if args[:2] == ("pr", "merge"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(prs, "_gh", gh)
    monkeypatch.setattr(prs, "get_pr", lambda *_: pr)
    prs.merge_pr(
        "kmehltretter82/tndlib",
        12,
        prover="lean4",
        expected_head_sha=HEAD,
        actor="kmehltretter82",
        app_id=12345,
    )
    assert calls[-1][:2] == ("pr", "merge")
    assert "--delete-branch" in calls[-1]

    # Without green maintainer-regression, a maintainer PR is refused.
    pr_without_reg = replace(
        pr,
        checks=tuple(c for c in checks if c.name != "regression"),
    )
    monkeypatch.setattr(prs, "get_pr", lambda *_: pr_without_reg)
    with pytest.raises(prs.PRError, match="maintainer-regression"):
        prs.merge_pr(
            "kmehltretter82/tndlib",
            12,
            prover="lean4",
            expected_head_sha=HEAD,
            actor="kmehltretter82",
            app_id=12345,
        )


def test_github_app_token_minting_validates_single_repo_installation(monkeypatch):
    monkeypatch.setattr(github_app, "build_app_jwt", lambda app_id, key: "jwt-token")
    responses = {
        ("GET", "https://api.github.com/repos/kmehltretter82/tndlib/installation"): {
            "id": 99,
            "app_id": 12345,
        },
        ("POST", "https://api.github.com/app/installations/99/access_tokens"): {
            "token": "ghs_minted_token",
        },
    }
    monkeypatch.setattr(
        github_app,
        "_api_json",
        lambda method, url, token, payload=None: responses[(method, url)],
    )
    assert (
        github_app.mint_installation_token("kmehltretter82/tndlib", "12345", "pem")
        == "ghs_minted_token"
    )


def test_app_token_redacted_bypass_actors_succeeds_only_with_self_always_bypass():
    base_ruleset = {
        "id": 26325579,
        "name": "tnd-merge-lane-only",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}],
        "current_user_can_bypass": "always",
    }
    for redacted in (
        base_ruleset,
        {**base_ruleset, "bypass_actors": None},
        {**base_ruleset, "bypass_actors": []},
    ):
        matched = require_app_only_merge_ruleset([redacted], app_id=5555437)
        assert matched == {
            "ruleset_id": 26325579,
            "name": "tnd-merge-lane-only",
            "verification_mode": "app_token_self_bypass",
        }
    for non_bypass in ("never", "pull_requests_only", None):
        with pytest.raises(ValueError, match="only bypass actor is GitHub App 5555437"):
            require_app_only_merge_ruleset(
                [{**base_ruleset, "current_user_can_bypass": non_bypass}],
                app_id=5555437,
            )


def test_owner_config_audit_requires_unredacted_exclusive_app_bypass_and_no_owner_bypass(
    monkeypatch,
):
    protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "strict": True,
            "contexts": list(BRANCH_PROTECTION_CONTEXTS),
        },
    }
    ruleset = {
        "id": 26325579,
        "name": "tnd-merge-lane-only",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "update"}],
        "bypass_actors": [
            {"actor_type": "Integration", "actor_id": 5555437, "bypass_mode": "always"}
        ],
        "current_user_can_bypass": "never",
    }

    def gh(*args):
        endpoint = args[-1]
        if endpoint.endswith("/protection"):
            return __import__("json").dumps(protection)
        if endpoint.endswith("/rulesets"):
            return __import__("json").dumps([{"id": 26325579}])
        if endpoint.endswith("/rulesets/26325579"):
            return __import__("json").dumps(ruleset)
        raise AssertionError(args)

    monkeypatch.setattr(config_audit, "_gh", gh)
    report = config_audit.audit_merge_config(
        "kmehltretter82/tnd-validation",
        app_id=5555437,
        expected_ruleset_id=26325579,
    )
    assert report["status"] == "verified-merge-config"
    assert report["verification_mode"] == "unredacted_bypass_actors"
    assert report["owner_can_bypass"] == "never"

    # Redacted bypass_actors must be rejected by the owner configuration audit.
    ruleset_redacted = {
        k: v for k, v in ruleset.items() if k != "bypass_actors"
    }
    ruleset_redacted["current_user_can_bypass"] = "always"
    ruleset.clear()
    ruleset.update(ruleset_redacted)
    with pytest.raises(prs.PRError, match="only bypass actor"):
        config_audit.audit_merge_config("kmehltretter82/tnd-validation", app_id=5555437)

    # Owner with bypass permission must be rejected.
    ruleset["bypass_actors"] = [
        {"actor_type": "Integration", "actor_id": 5555437, "bypass_mode": "always"}
    ]
    ruleset["current_user_can_bypass"] = "always"
    with pytest.raises(prs.PRError, match="owner/caller must not have ruleset bypass"):
        config_audit.audit_merge_config("kmehltretter82/tnd-validation", app_id=5555437)
