"""Exercise the actual local merge path with GitHub I/O replaced by fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from gate.checks import BRANCH_PROTECTION_CONTEXTS, REQUIRED_PRESENT
from gate.verify import comparator_cli
from gate.verify.tnd_comparator import approved_target, docker_arguments
from gate.verify.tnd_policy import rejected_paths
from gate.verify.tnd_readiness import require_certification
from orchestrator import prs
from orchestrator.tnd_verification import (
    WORKFLOW,
    complete_run_listing,
    require_verified_run,
    run_title,
)

BASE = "a" * 40
HEAD = "b" * 40


@pytest.mark.parametrize("policy", [{}, {"schema_version": 1},
                                  {"schema_version": 1, "source_binding_validated": False},
                                  {"schema_version": 1, "source_binding_validated": 1},
                                  {"schema_version": 1, "source_binding_validated": True,
                                   "resource_boundary_validated": False},
                                  {"schema_version": 1, "source_binding_validated": True,
                                   "resource_boundary_validated": True,
                                   "resource_limits": None}])
def test_unvalidated_source_binding_blocks_certification(policy):
    with pytest.raises(ValueError, match="certification is disabled"):
        require_certification(policy)


def test_readiness_accepts_only_validated_exact_resource_policy():
    quota = {
        "schema_version": 1, "build_bytes": 65536, "build_inodes": 64,
        "export_bytes": 65536, "export_inodes": 64,
    }
    require_certification({
        "schema_version": 1, "source_binding_validated": True,
        "resource_boundary_validated": True, "resource_limits": quota,
    })
    for invalid in ({**quota, "build_bytes": True}, {**quota, "extra": 1}):
        with pytest.raises(ValueError, match="certification is disabled"):
            require_certification({
                "schema_version": 1, "source_binding_validated": True,
                "resource_boundary_validated": True, "resource_limits": invalid,
            })


def test_current_policy_is_explicitly_not_certifiable():
    policy = json.loads(Path(".choir/certification.json").read_text())
    with pytest.raises(ValueError, match="certification is disabled"):
        require_certification(policy)


def successful_run(run_id: int = 1) -> dict:
    return {
        "id": run_id, "event": "pull_request_target", "path": WORKFLOW,
        "head_sha": BASE, "display_title": run_title(7, HEAD, BASE),
        "status": "completed", "conclusion": "success",
        "run_attempt": 1, "created_at": "2026-10-29T09:00:00Z",
        "run_started_at": "2026-10-29T09:00:00Z",
    }


@pytest.fixture
def merge_environment(monkeypatch):
    state = {
        "runs": [successful_run()],
        "protection": {
            "enforce_admins": {"enabled": True},
            "required_status_checks": {
                "strict": True, "contexts": list(BRANCH_PROTECTION_CONTEXTS),
            },
        },
        "pr": prs.PRView(
            number=7, title="Proof", url="https://example.invalid/pr/7", author="worker",
            state="open", body="Closes #2", base_sha=BASE, head_sha=HEAD,
            labels=(), files=("TNDLib/Logic.lean",),
            checks=tuple(prs.CheckResult(n, "COMPLETED", "SUCCESS") for n in REQUIRED_PRESENT),
            linked_issues=(2,), mergeable="MERGEABLE", head_repo="worker/tndlib",
        ),
        "calls": [],
    }

    def gh(*args):
        state["calls"].append(args)
        if args[0] == "api":
            if args[-1].endswith("/protection"):
                return json.dumps(state["protection"])
            return json.dumps([{"total_count": len(state["runs"]), "workflow_runs": state["runs"]}])
        if args[:2] == ("pr", "merge"):
            return ""
        raise AssertionError(f"unexpected GitHub call: {args!r}")

    monkeypatch.setattr(prs, "_gh", gh)
    monkeypatch.setattr(prs, "get_pr", lambda *_: state["pr"])
    return state


def assert_no_merge(state: dict) -> None:
    assert not any(call[:2] == ("pr", "merge") for call in state["calls"])


def test_verified_submission_merges_exact_head(merge_environment):
    prs.merge_pr("owner/tndlib", 7, prover="lean4")
    merge = merge_environment["calls"][-1]
    assert merge[:2] == ("pr", "merge")
    assert merge[-2:] == ("--match-head-commit", HEAD)


@pytest.mark.parametrize("linked", [(), (2, 3)])
@pytest.mark.parametrize("force", [None, "overseer reason"])
def test_merge_requires_exactly_one_linked_task_even_with_override(
    merge_environment, linked, force,
):
    merge_environment["pr"] = replace(
        merge_environment["pr"], linked_issues=linked,
    )
    with pytest.raises(prs.PRError, match="exactly one"):
        prs.merge_pr("owner/tndlib", 7, force=force, prover="lean4")
    assert_no_merge(merge_environment)


@pytest.mark.parametrize(
    "changed",
    [
        {"body": "Closes #3", "linked_issues": (3,)},
        {"body": "Closes #2\nnew text"},
    ],
)
def test_final_candidate_recheck_binds_pr_body_and_linked_issue(
    merge_environment, monkeypatch, changed,
):
    initial = merge_environment["pr"]
    final = replace(initial, **changed)
    reads = iter((initial, final))
    monkeypatch.setattr(prs, "get_pr", lambda *_: next(reads))
    with pytest.raises(prs.PRError, match="candidate changed"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


@pytest.mark.parametrize("change", [
    {"status": "queued", "conclusion": None},
    {"conclusion": "failure"},
    {"event": "pull_request"},
    {"path": ".github/workflows/forged.yml"},
    {"head_sha": "c" * 40},
    {"display_title": run_title(7, "c" * 40, BASE)},
    {"display_title": run_title(7, HEAD, "c" * 40)},
])
def test_bad_evidence_never_merges(merge_environment, change):
    merge_environment["runs"][0].update(change)
    with pytest.raises(prs.PRError, match="TND verification"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


def test_absent_audit_does_not_merge(merge_environment):
    merge_environment["runs"] = []
    with pytest.raises(prs.PRError, match="missing or stale"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


@pytest.mark.parametrize("suffix", ["", "@main", "@refs/heads/main"])
def test_trusted_workflow_path_accepts_supported_main_ref_forms(suffix):
    run = {**successful_run(), "path": WORKFLOW + suffix}
    require_verified_run([run], number=7, head=HEAD, base=BASE)


@pytest.mark.parametrize("path", [
    None,
    WORKFLOW + "@other",
    WORKFLOW + "@main@other",
    WORKFLOW + "@refs/heads/main/other",
    WORKFLOW + "@refs/heads/main ",
    ".github/workflows/other.yml@main",
])
def test_workflow_path_rejects_other_refs_and_malformed_values(path):
    run = {**successful_run(), "path": path}
    with pytest.raises(ValueError, match="missing or stale"):
        require_verified_run([run], number=7, head=HEAD, base=BASE)


def test_absent_status_does_not_merge(merge_environment):
    pr = merge_environment["pr"]
    checks = tuple(c for c in pr.checks if c.name != "tnd-audit")
    merge_environment["pr"] = replace(pr, checks=checks)
    with pytest.raises(prs.PRError, match="missing required checks"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


@pytest.mark.parametrize("status,conclusion", [("QUEUED", ""), ("COMPLETED", "FAILURE")])
def test_pending_or_failed_status_does_not_merge(merge_environment, status, conclusion):
    pr = merge_environment["pr"]
    checks = tuple(replace(c, status=status, conclusion=conclusion) if c.name == "tnd-audit" else c
                   for c in pr.checks)
    merge_environment["pr"] = replace(pr, checks=checks)
    with pytest.raises(prs.PRError, match="blocking checks not green"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


def test_latest_failed_attempt_overrides_old_success():
    failed = {**successful_run(2), "conclusion": "failure"}
    with pytest.raises(ValueError, match="not successful"):
        require_verified_run([failed, successful_run()], number=7, head=HEAD, base=BASE)


def test_rerun_of_older_id_overrides_later_created_run():
    success = {**successful_run(2), "run_started_at": "2026-10-29T11:00:00Z"}
    failed_rerun = {**successful_run(1), "run_attempt": 2,
                    "run_started_at": "2026-10-29T12:00:00Z", "conclusion": "failure"}
    with pytest.raises(ValueError, match="not successful"):
        require_verified_run([success, failed_rerun], number=7, head=HEAD, base=BASE)


def test_newer_failed_rerun_blocks_actual_force_merge(merge_environment):
    merge_environment["runs"] = [
        {**successful_run(2), "run_started_at": "2026-10-29T11:00:00Z"},
        {**successful_run(1), "run_attempt": 2, "run_started_at": "2026-10-29T12:00:00Z",
         "conclusion": "failure"},
    ]
    with pytest.raises(prs.PRError, match="not successful"):
        prs.merge_pr("owner/tndlib", 7, force="explicit reason", prover="lean4")
    assert_no_merge(merge_environment)


@pytest.mark.parametrize("change", [
    {"run_attempt": None}, {"run_attempt": 2, "run_started_at": None},
    {"created_at": None}, {"run_started_at": "2026-02-30T10:00:00Z"},
])
def test_invalid_attempt_timing_fails_closed(change):
    uncertain = {**successful_run(1), **change}
    with pytest.raises(ValueError):
        require_verified_run([successful_run(2), uncertain], number=7, head=HEAD, base=BASE)


def test_same_second_failed_attempt_cannot_be_ordered_behind_success():
    failure = {**successful_run(1), "conclusion": "failure"}
    with pytest.raises(ValueError, match="not successful"):
        require_verified_run([successful_run(2), failure], number=7, head=HEAD, base=BASE)


def test_active_old_run_blocks_even_if_newer_run_succeeded():
    queued = {**successful_run(1), "run_attempt": 2,
              "status": "queued", "conclusion": None}
    newer = {**successful_run(2), "run_started_at": "2026-10-29T11:00:00Z"}
    with pytest.raises(ValueError, match="pending or active"):
        require_verified_run([queued, newer], number=7, head=HEAD, base=BASE)


def test_rerun_created_during_preflight_is_caught_by_final_read(
    merge_environment, monkeypatch,
):
    original_gh = prs._gh
    listing_reads = 0

    def change_after_first_listing(*args):
        nonlocal listing_reads
        result = original_gh(*args)
        if (
            len(args) > 5
            and args[0] == "api"
            and "actions/workflows/verify-tnd.yml/runs" in args[5]
        ):
            listing_reads += 1
            if listing_reads == 1:
                merge_environment["runs"].append({
                    **successful_run(2),
                    "status": "queued",
                    "conclusion": None,
                    "created_at": "2026-10-29T10:00:00Z",
                    "run_started_at": None,
                })
        return result

    monkeypatch.setattr(prs, "_gh", change_after_first_listing)
    with pytest.raises(prs.PRError, match="pending or active"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert listing_reads == 2
    assert_no_merge(merge_environment)


def test_candidate_change_during_preflight_is_caught_before_final_merge(
    merge_environment, monkeypatch,
):
    first = merge_environment["pr"]
    reads = iter([first, replace(first, base_sha="c" * 40)])
    monkeypatch.setattr(prs, "get_pr", lambda *_: next(reads))
    with pytest.raises(prs.PRError, match="candidate changed during preflight"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


def test_paginated_older_rerun_is_considered():
    page1 = [successful_run(n) for n in range(2, 102)]
    failure = {**successful_run(1), "run_attempt": 2,
               "run_started_at": "2026-10-29T12:00:00Z", "conclusion": "failure"}
    runs = complete_run_listing([
        {"total_count": 101, "workflow_runs": page1},
        {"total_count": 101, "workflow_runs": [failure]},
    ])
    with pytest.raises(ValueError, match="not successful"):
        require_verified_run(runs, number=7, head=HEAD, base=BASE)


@pytest.mark.parametrize("pages", [
    [], [{"workflow_runs": []}], [{"total_count": 1000, "workflow_runs": []}],
    [{"total_count": 2, "workflow_runs": [successful_run()]}],
    [{"total_count": 2, "workflow_runs": [successful_run(), successful_run()]}],
    [{"total_count": 1, "workflow_runs": [successful_run()]},
     {"total_count": 2, "workflow_runs": [successful_run(2)]}],
])
def test_incomplete_or_changed_listing_refuses_merge(pages):
    with pytest.raises(ValueError):
        complete_run_listing(pages)


def test_unprotected_admin_merge_refused(merge_environment):
    merge_environment["protection"]["enforce_admins"]["enabled"] = False
    with pytest.raises(prs.PRError, match="administrator enforcement"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert_no_merge(merge_environment)


def test_force_cannot_override_unverified_proof(merge_environment):
    merge_environment["runs"] = []
    with pytest.raises(prs.PRError, match="missing or stale"):
        prs.merge_pr("owner/tndlib", 7, force="an explicit reason", prover="lean4")
    assert_no_merge(merge_environment)


def test_policy_edits_refused_before_any_api_call(merge_environment):
    merge_environment["pr"] = replace(merge_environment["pr"], files=("audit/Check.lean",))
    with pytest.raises(prs.PRError, match="protected paths"):
        prs.merge_pr("owner/tndlib", 7, prover="lean4")
    assert merge_environment["calls"] == []


def test_source_surface():
    assert rejected_paths(["TNDLib.lean", "TNDLib/Logic.lean", "tasks/Example.lean"]) == []
    paths = ["lakefile.toml", "TNDLib/../audit/Check.lean", ".github/workflows/verify-tnd.yml"]
    assert rejected_paths(paths) == sorted(paths)


def test_trusted_workflow_separates_verification_and_write_credentials():
    workflow = yaml.safe_load(Path(".github/workflows/verify-tnd.yml").read_text())
    # PyYAML uses YAML 1.1, under which the Actions key `on` becomes True.
    assert "pull_request_target" in workflow[True]
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "read"}
    jobs = workflow["jobs"]
    assert jobs["report"]["permissions"] == {"statuses": "write"}
    assert not any("uses" in step for step in jobs["report"]["steps"])
    checkout = jobs["verify"]["steps"][0]["with"]
    assert checkout["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert checkout["fetch-depth"] == 1
    assert checkout["fetch-tags"] is False
    assert checkout["persist-credentials"] is False
    audit_step = next(
        step for step in jobs["verify"]["steps"]
        if step.get("name") == "Independently verify isolated proof exports"
    )
    assert '--quota-parent "$RUNNER_TEMP"' in audit_step["run"]


def test_every_workflow_audit_run_uses_trusted_runner_quota_parent():
    invocations: list[tuple[str, str]] = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                command = step.get("run")
                if isinstance(command, str) and "audit/run.py" in command:
                    invocations.append((path.name, command))
                    assert '--quota-parent "$RUNNER_TEMP"' in command, path
    assert {name for name, _ in invocations} == {
        "audit-main.yml",
        "verify-pr.yml",
        "verify-tnd.yml",
        "verify-trust-report.yml",
    }


def test_every_proof_pr_workflow_uses_bounded_filtered_fetch():
    expected = {
        "verify-axiom-honesty.yml",
        "verify-comparator.yml",
        "verify-pr.yml",
        "verify-sorry.yml",
        "verify-statement-equiv.yml",
        "verify-statement-immutability.yml",
        "verify-style.yml",
        "verify-tnd.yml",
        "verify-trust-report.yml",
    }
    actual = set()
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        source = path.read_text()
        workflow = yaml.safe_load(source)
        helper_locations = [
            (job.get("steps", []), index, step)
            for job in workflow.get("jobs", {}).values()
            for index, step in enumerate(job.get("steps", []))
            if isinstance(step.get("run"), str)
            and "gate.verify.tnd_fetch" in step["run"]
        ]
        if not helper_locations:
            continue
        actual.add(path.name)
        assert workflow.get("env", {}).get("GIT_NO_LAZY_FETCH") == "1", path
        assert workflow.get("permissions", {}).get("pull-requests") == "read", path
        assert len(helper_locations) == 1, path
        steps, helper_index, step = helper_locations[0]
        prior_checkouts = [
            candidate
            for candidate in steps[:helper_index]
            if str(candidate.get("uses", "")).startswith("actions/checkout@")
        ]
        assert len(prior_checkouts) == 1, path
        checkout = prior_checkouts[0].get("with", {})
        assert checkout.get("ref") == "${{ github.event.pull_request.base.sha }}", path
        assert checkout.get("fetch-depth") == 1, path
        assert checkout.get("fetch-tags") is False, path
        assert checkout.get("persist-credentials") is False, path
        assert step.get("env", {}).get("GH_TOKEN") == "${{ github.token }}", path
        assert step.get("env", {}).get("REPO") == "${{ github.repository }}", path
        assert all(token in step["run"] for token in (
            '--repo "$REPO"', '--pr "$PR_NUMBER"',
            '--base "$BASE_SHA"', '--head "$HEAD_SHA"',
        )), path
        assert "fetch-depth: 0" not in source, path
        assert "git fetch" not in source, path
    assert actual == expected


def test_comparator_workflow_uses_trusted_runner_quota_parent():
    workflow = yaml.safe_load(Path(".github/workflows/verify-comparator.yml").read_text())
    steps = workflow["jobs"]["comparator"]["steps"]
    command = next(
        step["run"] for step in steps
        if step.get("name") == "Compare the approved task in the isolated container"
    )
    assert '--quota-parent "$RUNNER_TEMP"' in command


def test_reconcile_writer_runs_only_reviewed_main_code_without_git_credentials():
    workflow = yaml.safe_load(Path(".github/workflows/reconcile.yml").read_text())
    assert workflow["permissions"] == {"issues": "write", "contents": "read"}
    job = workflow["jobs"]["reconcile"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    checkout_step = next(
        step for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    checkout = checkout_step["with"]
    assert checkout == {
        "ref": "refs/heads/main",
        "fetch-depth": 1,
        "fetch-tags": False,
        "persist-credentials": False,
    }
    assert job["timeout-minutes"] == 15


def test_issue_close_writer_is_main_only_trusted_and_fail_closed():
    path = Path(".github/workflows/issue-close-on-merge.yml")
    source = path.read_text()
    workflow = yaml.safe_load(source)
    job = workflow["jobs"]["close"]
    assert "\n    branches: [main]\n" in source
    assert job["if"] == (
        "github.event.pull_request.merged == true && "
        "github.event.pull_request.base.ref == 'main'"
    )
    assert job["timeout-minutes"] == 15
    checkout = next(
        step["with"] for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout == {
        "ref": "${{ github.event.pull_request.base.sha }}",
        "fetch-depth": 1,
        "fetch-tags": False,
        "persist-credentials": False,
    }
    commands = "\n".join(
        step["run"] for step in job["steps"] if isinstance(step.get("run"), str)
    )
    assert "gate.state.close_on_merge_cli" in commands
    assert "gate.state.issue_updates" in commands
    assert " complete --pr " in commands
    assert "gh issue" not in commands
    assert "|| true" not in source


def test_issue_intake_writer_quarantines_before_validation_on_trusted_main():
    path = Path(".github/workflows/issue-intake.yml")
    source = path.read_text()
    workflow = yaml.safe_load(source)
    job = workflow["jobs"]["intake"]
    assert job["timeout-minutes"] == 15
    checkout_index = next(
        index for index, step in enumerate(job["steps"])
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    checkout = job["steps"][checkout_index]["with"]
    assert checkout == {
        "ref": "refs/heads/main",
        "fetch-depth": 1,
        "fetch-tags": False,
        "persist-credentials": False,
    }
    names = [step.get("name", "") for step in job["steps"]]
    quarantine_index = names.index("Quarantine before parsing and enforce owner publication")
    validate_index = names.index("Validate issue body")
    assert checkout_index < quarantine_index < validate_index
    commands = "\n".join(
        step["run"] for step in job["steps"] if isinstance(step.get("run"), str)
    )
    for command in (" quarantine ", " comments ", " apply-intake ", "--body-file"):
        assert command in commands
    assert "quarantine --mark-invalid" in commands
    assert "gh issue" not in commands
    assert "|| true" not in source


def _mapping_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _mapping_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _mapping_nodes(child)


def test_every_setup_uv_use_has_the_global_version_and_cache_contract():
    paths = sorted(Path(".github/workflows").glob("*.yml"))
    paths += sorted(Path(".github/actions").glob("**/*.yml"))
    setup_steps = []
    for path in paths:
        document = yaml.safe_load(path.read_text())
        setup_steps.extend(
            (path, node) for node in _mapping_nodes(document)
            if str(node.get("uses", "")).startswith("astral-sh/setup-uv@")
        )
    assert setup_steps
    for path, step in setup_steps:
        assert step.get("with", {}).get("version") == "0.9.6", path
        assert step.get("with", {}).get("enable-cache") is False, path


def test_every_workflow_job_has_an_explicit_positive_timeout():
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        for name, job in workflow["jobs"].items():
            timeout = job.get("timeout-minutes")
            assert isinstance(timeout, int) and not isinstance(timeout, bool), (path, name)
            assert timeout > 0, (path, name)


def test_text_audits_have_bounded_jobs_and_rerun_when_pr_body_changes():
    paths = (
        "verify-axiom-honesty.yml",
        "verify-sorry.yml",
        "verify-statement-equiv.yml",
        "verify-statement-immutability.yml",
        "verify-style.yml",
    )
    for name in paths:
        workflow = yaml.safe_load(Path(".github/workflows", name).read_text())
        assert all(job.get("timeout-minutes") == 15 for job in workflow["jobs"].values())
    for name in (
        "verify-comparator.yml", "verify-tnd.yml",
        "verify-statement-equiv.yml", "verify-sorry.yml",
    ):
        source = Path(".github/workflows", name).read_text()
        assert "types: [opened, synchronize, reopened, edited]" in source


def test_audit_main_checkout_is_explicitly_shallow_and_tagless():
    workflow = yaml.safe_load(Path(".github/workflows/audit-main.yml").read_text())
    job = workflow["jobs"]["audit-main"]
    checkout = next(
        step["with"] for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout == {
        "ref": "${{ github.sha }}",
        "fetch-depth": 1,
        "fetch-tags": False,
        "persist-credentials": False,
    }


def test_maintainer_regression_never_executes_fork_or_manual_branch_code():
    path = Path(".github/workflows/maintainer-ci.yml")
    source = path.read_text()
    workflow = yaml.safe_load(source)
    assert workflow["permissions"] == {"contents": "read"}
    assert "\n  push:\n    branches: [main]\n" in source
    assert "\n  pull_request:\n" in source
    assert "\n  workflow_dispatch:\n" in source
    job = workflow["jobs"]["regression"]
    guard = job["if"]
    assert "github.event_name == 'workflow_dispatch'" in guard
    assert "github.ref == 'refs/heads/main'" in guard
    assert "github.event.pull_request.head.repo.full_name == github.repository" in guard
    assert job["timeout-minutes"] == 45
    checkout_step = next(
        step for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout_step["with"] == {
        "ref": "${{ github.event_name == 'pull_request' && "
               "github.event.pull_request.head.sha || github.sha }}",
        "fetch-depth": 1,
        "fetch-tags": False,
        "persist-credentials": False,
    }
    for step in job["steps"]:
        action = step.get("uses")
        if action:
            revision = action.rsplit("@", 1)[-1]
            assert len(revision) == 40 and set(revision) <= set("0123456789abcdef")
    commands = "\n".join(
        step["run"] for step in job["steps"] if isinstance(step.get("run"), str)
    )
    for required in (
        "audit/install_lean.py",
        "lake build",
        "tests/corpus/Examples.lean",
        "tests/check_downstream.py",
        "audit/admission/test_admission.py",
        "tests/audit/check_fixtures.py",
        "tests/audit/promotion_rehearsal.py",
        "python -m pytest -q",
        "python -m unittest discover",
        "python -m compileall",
        "ruff check",
    ):
        assert required in commands
    assert commands.count("uv run --frozen --extra dev") == 4
    assert "uv run --frozen python" not in commands
    assert "tnd_readiness" not in commands
    assert "docker" not in commands
    assert "upload-artifact" not in source


def test_comparator_task_must_match_committed_approval():
    registry = json.loads(Path("audit/tasks.json").read_text())
    assert approved_target(registry, "tasks/map_exists.lean", "TNDTask.mapExists")
    assert not approved_target(registry, "tasks/map_exists.lean", "TNDTask.weakened")
    assert not approved_target(registry, "tasks/other.lean", "TNDTask.mapExists")


def _example_task_body() -> str:
    text = Path("docs/API.md").read_text()
    return text.split("```yaml\n", 1)[1].split("\n```", 1)[0]


def test_comparator_target_requires_exactly_one_closing_reference(monkeypatch):
    calls = []

    def gh(*args):
        calls.append(args)
        return json.dumps({
            "body": "Closes #2 and fixes #3", "baseRefOid": BASE, "headRefOid": HEAD,
        })

    monkeypatch.setattr(comparator_cli, "_gh", gh)
    reason = comparator_cli._resolve_pr_target("kmehltretter82/tndlib", 7)
    assert isinstance(reason, str) and "exactly one" in reason
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("author", "labels", "state"),
    [
        ("contributor", [{"name": "choir/task"}], "OPEN"),
        ("kmehltretter82", [{"name": "bug"}], "OPEN"),
        ("kmehltretter82", [{"name": "choir/task"}], "CLOSED"),
    ],
)
def test_comparator_target_requires_open_owner_approved_task(
    monkeypatch, author, labels, state,
):
    responses = iter((
        json.dumps({"body": "Closes #2", "baseRefOid": BASE, "headRefOid": HEAD}),
        json.dumps({
            "body": _example_task_body(), "author": {"login": author},
            "labels": labels, "state": state,
        }),
    ))
    monkeypatch.setattr(comparator_cli, "_gh", lambda *_: next(responses))
    reason = comparator_cli._resolve_pr_target("kmehltretter82/tndlib", 7)
    assert isinstance(reason, str) and "owner-approved" in reason


def test_comparator_target_accepts_one_open_owner_approved_task(monkeypatch):
    responses = iter((
        json.dumps({"body": "Closes #2", "baseRefOid": BASE, "headRefOid": HEAD}),
        json.dumps({
            "body": _example_task_body(),
            "author": {"login": "kmehltretter82"},
            "labels": [{"name": "choir/task"}], "state": "OPEN",
        }),
    ))
    monkeypatch.setattr(comparator_cli, "_gh", lambda *_: next(responses))
    target = comparator_cli._resolve_pr_target("kmehltretter82/tndlib", 7)
    assert target == (
        BASE, HEAD, "tasks/map_exists.lean", "TNDTask.mapExists", "Closes #2",
    )


def test_comparator_outer_sandbox_exposes_only_isolated_build_for_writes(tmp_path):
    paths = (tmp_path / name for name in ("source", "build", "tools", "lean", "check"))
    args = docker_arguments(*paths)
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    mounts = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
    writable = [mount for mount in mounts if not mount.endswith(",readonly")]
    assert writable == [f"type=bind,src={tmp_path / 'build'},dst=/work/.lake"]
    assert not any("docker.sock" in arg or "TOKEN" in arg for arg in args)


@pytest.mark.parametrize("mutation", [None, "digest", "head", "expired", "run"])
def test_public_evidence_publisher_validates_original_archive(tmp_path, mutation):
    workflow = yaml.safe_load(Path(".github/workflows/audit-main.yml").read_text())
    publisher = workflow["jobs"]["publish-evidence"]
    assert publisher["permissions"] == {"actions": "read", "contents": "write"}
    assert not any("uses" in step for step in publisher["steps"])
    script = publisher["steps"][0]["run"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    archive = b"immutable archive fixture"
    artifact = {
        "id": 123, "name": "tnd-audit-report", "expired": False,
        "workflow_run": {"id": 456, "head_sha": HEAD},
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
    }
    if mutation == "digest":
        artifact["digest"] = "sha256:" + "0" * 64
    elif mutation == "head":
        artifact["workflow_run"]["head_sha"] = BASE
    elif mutation == "expired":
        artifact["expired"] = True
    elif mutation == "run":
        artifact["workflow_run"]["id"] = 789
    (tmp_path / "metadata.json").write_text(json.dumps(artifact))
    (tmp_path / "evidence.zip").write_bytes(archive)
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, check=False,
        env={**os.environ, "SOURCE_SHA": HEAD, "RUN_ID": "456", "ARTIFACT_ID": "123"},
    )
    assert (result.returncode == 0) == (mutation is None)
    public_asset = tmp_path / f"audit-{HEAD}-456-123.zip"
    assert public_asset.exists() == (mutation is None)
    if mutation is None:
        assert public_asset.read_bytes() == archive


@pytest.mark.parametrize("mutation", [None, "head", "base", "status"])
def test_workflow_attempt_provenance_is_trusted_and_exact(tmp_path, mutation):
    workflow = yaml.safe_load(Path(".github/workflows/audit-main.yml").read_text())
    step = next(step for step in workflow["jobs"]["audit-main"]["steps"]
                if step.get("name") == "Bind report to this trusted workflow attempt")
    script = step["run"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    report = {"status": "verified", "base_sha": HEAD, "head_sha": HEAD,
              "ci": {"run_id": "untrusted-old-value"}}
    if mutation == "head":
        report["head_sha"] = BASE
    elif mutation == "base":
        report["base_sha"] = BASE
    elif mutation == "status":
        report["status"] = "verified-proof-objects"
    output = tmp_path / "audit/output/audit.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(report))
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, check=False,
        env={**os.environ, "AUDIT_HEAD_SHA": HEAD, "AUDIT_RUN_ID": "456",
             "AUDIT_RUN_ATTEMPT": "2", "AUDIT_REPOSITORY": "owner/tndlib", "AUDIT_EVENT": "push"},
    )
    assert (result.returncode == 0) == (mutation is None)
    if mutation is None:
        assert json.loads(output.read_text())["ci"] == {
            "repository": "owner/tndlib", "workflow": ".github/workflows/audit-main.yml",
            "event": "push", "run_id": 456, "run_attempt": 2, "head_sha": HEAD,
        }
