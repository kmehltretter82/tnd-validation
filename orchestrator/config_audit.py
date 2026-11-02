"""Owner-side audit of TND repository branch protection and merge-lane rulesets.

Runtime merge preflight (`orchestrator/prs.py` inside `orchestrator/merge_lane.py`)
executes with a short-lived GitHub App installation token whose repository
administration permission is intentionally read-only (`Administration: read`).
GitHub omits `bypass_actors` on ruleset queries made by non-admin tokens while
still returning `current_user_can_bypass: "always"` for the Merge App token.

This owner-side audit complements runtime preflight: run by the repository owner
before enabling merges (and during periodic governance audits), it queries the
same endpoints with owner credentials, refuses redacted `bypass_actors` lists,
verifies that GitHub App 5555437 is the sole bypass actor (`always`), verifies
that the owner's own `current_user_can_bypass` is `"never"`, and checks strict
administrator-enforced branch protection on `main`.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from gate.checks import BRANCH_PROTECTION_CONTEXTS
from orchestrator.prs import PRError, _gh
from orchestrator.tnd_verification import (
    require_app_only_merge_ruleset,
    require_merge_protection,
)

DEFAULT_MERGE_APP_ID = 5555437


def audit_merge_config(
    repo: str,
    *,
    app_id: int = DEFAULT_MERGE_APP_ID,
    expected_ruleset_id: int | None = None,
) -> dict[str, Any]:
    """Verify full unredacted branch-protection and ruleset configuration on ``repo``."""
    try:
        protection = json.loads(_gh("api", f"repos/{repo}/branches/main/protection"))
        summaries = json.loads(_gh("api", f"repos/{repo}/rulesets"))
        if not isinstance(summaries, list):
            raise ValueError("invalid GitHub ruleset listing")
        rulesets = []
        for item in summaries:
            if not isinstance(item, dict):
                raise ValueError("invalid GitHub ruleset summary")
            ruleset_id = item.get("id")
            if isinstance(ruleset_id, bool) or not isinstance(ruleset_id, int) or ruleset_id < 1:
                raise ValueError("invalid GitHub ruleset ID")
            detail = json.loads(_gh("api", f"repos/{repo}/rulesets/{ruleset_id}"))
            if not isinstance(detail, dict):
                raise ValueError("invalid GitHub ruleset detail")
            rulesets.append(detail)
        require_merge_protection(protection)
        matched = require_app_only_merge_ruleset(
            rulesets,
            app_id=app_id,
            require_unredacted_actors=True,
            expected_ruleset_id=expected_ruleset_id,
        )
        matched_detail = next(
            r for r in rulesets if r.get("id") == matched["ruleset_id"]
        )
        if matched_detail.get("current_user_can_bypass") != "never":
            raise ValueError(
                "owner/caller must not have ruleset bypass permission "
                f"(found current_user_can_bypass={matched_detail.get('current_user_can_bypass')!r})"
            )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PRError(f"TND merge configuration audit failed: {exc}") from exc

    status_checks = protection.get("required_status_checks") or {}
    contexts = sorted(
        set(status_checks.get("contexts") or [])
        | {check["context"] for check in status_checks.get("checks") or []}
    )
    return {
        "status": "verified-merge-config",
        "repo": repo,
        "merge_app_id": app_id,
        "ruleset_id": matched["ruleset_id"],
        "ruleset_name": matched["ruleset_name"] if "ruleset_name" in matched else matched["name"],
        "verification_mode": matched["verification_mode"],
        "owner_can_bypass": matched_detail.get("current_user_can_bypass"),
        "enforce_admins": True,
        "strict_status_checks": True,
        "required_contexts": contexts,
        "expected_contexts": list(BRANCH_PROTECTION_CONTEXTS),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name of the GitHub repository")
    parser.add_argument(
        "--app-id",
        type=int,
        default=DEFAULT_MERGE_APP_ID,
        help=f"GitHub App ID for the merge lane (default: {DEFAULT_MERGE_APP_ID})",
    )
    parser.add_argument(
        "--ruleset-id",
        type=int,
        default=None,
        help="Optional expected ruleset ID to pin",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = audit_merge_config(
            args.repo,
            app_id=args.app_id,
            expected_ruleset_id=args.ruleset_id,
        )
    except PRError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
