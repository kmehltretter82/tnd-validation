"""Refuse certification until source and resource boundaries are validated."""

from __future__ import annotations

import json
from pathlib import Path


def require_certification(policy: dict) -> None:
    quota = policy.get("resource_limits")
    expected = {
        "schema_version",
        "build_bytes",
        "build_inodes",
        "export_bytes",
        "export_inodes",
    }
    valid_quota = isinstance(quota, dict) and set(quota) == expected
    if valid_quota:
        values = [
            quota["build_bytes"],
            quota["build_inodes"],
            quota["export_bytes"],
            quota["export_inodes"],
        ]
        valid_quota = (
            isinstance(quota["schema_version"], int)
            and not isinstance(quota["schema_version"], bool)
            and quota["schema_version"] == 1
            and all(isinstance(value, int) and not isinstance(value, bool) for value in values)
            and all(4096 <= value <= 4 * 1024**3 for value in values[::2])
            and all(16 <= value <= 1_000_000 for value in values[1::2])
        )
    if (
        not isinstance(policy.get("schema_version"), int)
        or isinstance(policy.get("schema_version"), bool)
        or policy.get("schema_version") != 1
        or policy.get("source_binding_validated") is not True
        or policy.get("resource_boundary_validated") is not True
        or not valid_quota
    ):
        raise ValueError(
            "TND certification is disabled: " + str(policy.get("reason", "unvalidated policy"))
        )


if __name__ == "__main__":
    require_certification(json.loads(Path(".choir/certification.json").read_text()))
