"""TND's trusted admission rules for proof submissions.

Run this module from the maintained base checkout, before building any submitted
Lean code. Contributions may change Lean sources only; build, policy, workflow,
and verifier changes belong to a separate maintainer change.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable

_SHA = re.compile(r"[0-9a-f]{40}\Z")


def rejected_paths(paths: Iterable[str]) -> list[str]:
    """List paths outside the proof-only contribution surface."""
    return sorted(
        path for path in paths
        if not (
            path == "TNDLib.lean"
            or (path.startswith(("TNDLib/", "tasks/")) and path.endswith(".lean"))
        )
        or any(part in {"", ".", ".."} for part in path.split("/"))
    )


def inspect_tree(base: str, head: str) -> None:
    """Inspect Git objects as data; never import or execute submission code."""
    if not _SHA.fullmatch(base) or not _SHA.fullmatch(head):
        raise ValueError("base and head must be full lowercase Git commit hashes")
    paths = subprocess.check_output(
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
         "--name-only", "-z", base, head, "--"],
    ).decode().split("\0")
    paths = [path for path in paths if path]
    refused = rejected_paths(paths)
    if refused:
        raise ValueError(f"proof submissions cannot change protected paths: {refused!r}")
    for path in paths:
        entry = subprocess.check_output(["git", "ls-tree", "-z", head, "--", path])
        if entry and not entry.startswith(b"100644 blob "):
            raise ValueError(f"submitted Lean source must be a regular non-executable file: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    inspect_tree(args.base, args.head)


if __name__ == "__main__":
    main()
