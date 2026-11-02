"""Keep validation-only certification flags out of the production development tree.

This guard preserves the currently approved *uncertified* production profile.
Passing it does not authorize a release. A future certification decision must
review and replace this guard along with the policy and production evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

POLICY = ".choir/certification.json"
FIELDS = {
    "schema_version", "source_binding_validated", "resource_boundary_validated",
    "resource_limits", "reason",
}
REVISION = re.compile(r"[0-9a-f]{40}\Z")


def _unique_object(items: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("certification policy contains duplicate fields")
        result[key] = value
    return result


def require_development_profile(policy: object) -> None:
    """Reject any activation of the production tree's unreviewed certification."""
    if (
        not isinstance(policy, dict)
        or set(policy) != FIELDS
        or type(policy["schema_version"]) is not int
        or policy["schema_version"] != 1
        or policy["source_binding_validated"] is not False
        or policy["resource_boundary_validated"] is not False
        or policy["resource_limits"] is not None
        or not isinstance(policy["reason"], str)
        or not policy["reason"].strip()
    ):
        raise ValueError(
            "production development policy differs from its approved uncertified profile; "
            "validation flags/limits require a separate certification review"
        )


def check_repository(repo: Path, revision: str | None = None) -> None:
    """Inspect working-tree policy or the exact policy blob at a full Git SHA."""
    if revision is None:
        raw = (repo / POLICY).read_bytes()
    else:
        if REVISION.fullmatch(revision) is None:
            raise ValueError("revision must be a full lowercase Git commit SHA")
        raw = subprocess.run(
            ["git", "-C", str(repo), "show", f"{revision}:{POLICY}"],
            capture_output=True, check=True, timeout=15,
        ).stdout
    policy = json.loads(raw, object_pairs_hook=_unique_object)
    require_development_profile(policy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--revision", help="full candidate Git commit SHA")
    args = parser.parse_args(argv)
    try:
        check_repository(args.repo, args.revision)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"production profile refused: {error}\n")
    print("Production development profile preserved: uncertified, with no active limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
