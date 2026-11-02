"""Bind TND merges to the trusted workflow, its PR head, and its base.

A green status name alone is not evidence: a PR-controlled workflow could emit
the same name. TND uses a base-controlled pull_request_target workflow and an
isolated reporter. The workflow run's immutable event, path, SHA, and generated
title bind its success to the exact contribution being merged.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from gate.checks import BRANCH_PROTECTION_CONTEXTS

WORKFLOW = ".github/workflows/verify-tnd.yml"
STATUS = "tnd-audit"
MAX_FILTERED_RUNS = 999


def complete_run_listing(pages: Any) -> list[Mapping[str, Any]]:
    """Reject truncated, inconsistent or duplicated filtered API results.

    GitHub caps filtered run searches at 1,000 results. An old run can be
    rerun recently, so an incomplete listing cannot establish the newest
    attempt, even if the visible page contains a success.
    """
    if not isinstance(pages, list) or not pages:
        raise ValueError("invalid TND workflow run listing")
    runs: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    total = None
    for index, page in enumerate(pages):
        if not isinstance(page, Mapping):
            raise ValueError("invalid TND workflow run page")
        count, batch = page.get("total_count"), page.get("workflow_runs")
        if (isinstance(count, bool) or not isinstance(count, int)
                or not 0 <= count <= MAX_FILTERED_RUNS
                or not isinstance(batch, list) or len(batch) > 100):
            raise ValueError("TND workflow run listing is invalid or exceeds the query limit")
        if total is None:
            total = count
        elif count != total:
            raise ValueError("TND workflow run listing changed during pagination")
        if index < len(pages) - 1 and len(batch) != 100:
            raise ValueError("TND workflow run listing contains an incomplete page")
        for run in batch:
            if not isinstance(run, Mapping):
                raise ValueError("invalid TND workflow run")
            run_id = run.get("id")
            if (isinstance(run_id, bool) or not isinstance(run_id, int)
                    or run_id < 1 or run_id in seen):
                raise ValueError("TND workflow run listing contains duplicate or invalid IDs")
            seen.add(run_id)
            runs.append(run)
    if len(runs) != total:
        raise ValueError("TND workflow run listing is incomplete")
    return runs


def attempt_start(run: Mapping[str, Any]) -> datetime:
    """Order latest attempts by start time, not run ID or completion time."""
    attempt = run.get("run_attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("TND run has invalid attempt metadata")

    def timestamp(value: Any) -> datetime:
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
        ):
            raise ValueError("TND run has missing or invalid timing metadata")
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)

    created = timestamp(run.get("created_at"))
    started = run.get("run_started_at")
    if (started is None and attempt == 1
            and run.get("status") in {"queued", "requested", "waiting", "pending"}):
        started = created
    else:
        started = timestamp(started)
    if started < created:
        raise ValueError("TND run started before its creation")
    return started


def require_merge_protection(protection: Mapping[str, Any]) -> None:
    """Require GitHub to close the race when the base moves after preflight."""
    status_checks = protection.get("required_status_checks") or {}
    contexts = set(status_checks.get("contexts") or [])
    contexts.update(check["context"] for check in status_checks.get("checks") or [])
    if (
        status_checks.get("strict") is not True
        or (protection.get("enforce_admins") or {}).get("enabled") is not True
        or not set(BRANCH_PROTECTION_CONTEXTS).issubset(contexts)
    ):
        raise ValueError(
            "TND requires strict branch protection, administrator enforcement, "
            "and every Choir/TND required context before merging"
        )


def _targets_main_branch(ruleset: Mapping[str, Any]) -> bool:
    if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch":
        return False
    conditions = ruleset.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, Mapping) else None
    include = ref_name.get("include") if isinstance(ref_name, Mapping) else None
    exclude = ref_name.get("exclude") if isinstance(ref_name, Mapping) else None
    if not isinstance(include, list) or not isinstance(exclude, list) or exclude:
        return False
    return bool({"~DEFAULT_BRANCH", "refs/heads/main"} & set(include))


def require_app_only_merge_ruleset(
    rulesets: Any,
    *,
    app_id: int,
    require_unredacted_actors: bool = False,
    expected_ruleset_id: int | None = None,
) -> dict[str, Any]:
    """Require an active main-branch ruleset restricting updates to the merge App.

    Trust model:
    1. Owner-side configuration audit (``require_unredacted_actors=True``) runs with
       repository administration visibility and requires the unredacted
       ``bypass_actors`` list to contain ``Integration`` ``app_id`` (``always``) as
       the sole bypass actor.
    2. Runtime merge preflight runs under the short-lived GitHub App installation
       token minted by ``orchestrator/merge_lane.py`` with ``Administration: read``
       (keeping ruleset administration out of the runtime merge credential). When
       GitHub redacts ``bypass_actors`` on a read-only ruleset read, GitHub still
       evaluates ``current_user_can_bypass`` for the caller; runtime preflight
       accepts the ruleset only when it is an active ``main``-branch ``update``
       ruleset and ``current_user_can_bypass == "always"`` for the authenticated
       Merge App token.
    """
    if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id < 1:
        raise ValueError("TND merge App ID must be a positive integer")
    if expected_ruleset_id is not None and (
        isinstance(expected_ruleset_id, bool)
        or not isinstance(expected_ruleset_id, int)
        or expected_ruleset_id < 1
    ):
        raise ValueError("expected TND ruleset ID must be a positive integer")
    if not isinstance(rulesets, list) or not rulesets:
        raise ValueError("TND requires an active main-branch ruleset restricting direct merges")
    for ruleset in rulesets:
        if not isinstance(ruleset, Mapping) or not _targets_main_branch(ruleset):
            continue
        ruleset_id = ruleset.get("id")
        if expected_ruleset_id is not None and (
            isinstance(ruleset_id, bool) or ruleset_id != expected_ruleset_id
        ):
            continue
        rules = ruleset.get("rules")
        if not isinstance(rules, list):
            continue
        rule_types = {
            rule.get("type") for rule in rules if isinstance(rule, Mapping)
        }
        if "update" not in rule_types:
            continue
        bypass = ruleset.get("bypass_actors")
        if isinstance(bypass, list) and bypass:
            if len(bypass) == 1 and isinstance(bypass[0], Mapping):
                actor = bypass[0]
                if (
                    actor.get("actor_type") == "Integration"
                    and not isinstance(actor.get("actor_id"), bool)
                    and actor.get("actor_id") == app_id
                    and actor.get("bypass_mode") == "always"
                ):
                    return {
                        "ruleset_id": ruleset_id,
                        "name": ruleset.get("name"),
                        "verification_mode": "unredacted_bypass_actors",
                    }
            continue
        if (
            not require_unredacted_actors
            and (bypass is None or bypass == [])
            and ruleset.get("current_user_can_bypass") == "always"
        ):
            return {
                "ruleset_id": ruleset_id,
                "name": ruleset.get("name"),
                "verification_mode": "app_token_self_bypass",
            }
    raise ValueError(
        "TND requires an active main-branch update ruleset whose only bypass actor "
        f"is GitHub App {app_id}"
    )


def run_title(number: int, head: str, base: str) -> str:
    return f"TND PR {number} head:{head} base:{base}"


def trusted_workflow_path(path: Any) -> bool:
    """Accept GitHub's documented optional main-ref suffix, never another path/ref.

    The merge caller separately requires a main-branch base and binds the run
    to its exact base SHA and generated PR title.
    """
    return isinstance(path, str) and path in {
        WORKFLOW,
        f"{WORKFLOW}@main",
        f"{WORKFLOW}@refs/heads/main",
    }


def require_verified_run(
    runs: Sequence[Mapping[str, Any]], *, number: int, head: str, base: str,
) -> None:
    """Fail closed for absent, stale, pending, failed, or untrusted evidence.

    Among runs for this exact pair use the newest run, so an older green run
    cannot conceal a newer queued or failed attempt. GitHub reruns update the
    same run's status; no artifact from the untrusted build is interpreted here.

    GitHub's REST API reports a `pull_request_target` run's `head_sha` as the PR
    head, observed live on 2026-10-31, though the run executes the base's workflow.
    The event and path establish that origin; the generated title binds the base.
    """
    title = run_title(number, head, base)
    matching = [
        run for run in runs
        if run.get("event") == "pull_request_target"
        and trusted_workflow_path(run.get("path"))
        and run.get("head_sha") == head
        and run.get("display_title") == title
    ]
    if not matching:
        raise ValueError("TND verification is missing or stale for the current PR head and base")
    ordered = [(attempt_start(run), run) for run in matching]
    # A rerun can be queued before its actual start timestamp is available or
    # while a later-created run has already succeeded. Any active attempt can
    # still supersede that result, so do not infer safety from its timestamp.
    if any(run.get("status") != "completed" for run in matching):
        raise ValueError("TND verification has a pending or active attempt")
    latest_start = max(start for start, _ in ordered)
    latest = [run for start, run in ordered if start == latest_start]
    # Seconds-resolution ties cannot establish that an unsuccessful run is
    # older than a success. Treat every tied attempt as authoritative.
    for newest in latest:
        if newest.get("status") == "completed" and newest.get("conclusion") == "success":
            continue
        raise ValueError(
            f"TND verification run {newest['id']} is not successful: "
            f"{newest.get('status')}/{newest.get('conclusion')}"
        )
