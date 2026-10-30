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
    """
    title = run_title(number, head, base)
    matching = [
        run for run in runs
        if run.get("event") == "pull_request_target"
        and trusted_workflow_path(run.get("path"))
        and run.get("head_sha") == base
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
