"""CLI for `issue-close-on-merge` workflow.

Reads a PR body from `--body-file` and prints its one closing issue number.
Zero or multiple unique references are rejected before the workflow mutates
any issue; the lifecycle helper separately validates that issue as an
owner-approved Choir task.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gate.state.close_on_merge import parse_closing_refs
from orchestrator.governance import has_maintainer_marker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract closing-issue refs from a PR body")
    parser.add_argument("--body-file", required=True, help="Path to a file containing the PR body")
    parser.add_argument(
        "--maintainer-ok",
        action="store_true",
        help="Allow a maintainer PR body with tnd-pr-mode: maintainer and zero closing refs",
    )
    args = parser.parse_args(argv)

    body = Path(args.body_file).read_text(encoding="utf-8")
    references = parse_closing_refs(body)
    if args.maintainer_ok and has_maintainer_marker(body):
        if references:
            print(
                "error: a maintainer PR must not contain closing-issue references; "
                f"found {len(references)}",
                file=sys.stderr,
            )
            return 1
        print("maintainer")
        return 0
    if len(references) != 1:
        print(
            "error: a merged Choir PR must contain exactly one unique "
            f"closing-issue reference; found {len(references)}",
            file=sys.stderr,
        )
        return 1
    print(references[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
