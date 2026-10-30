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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract closing-issue refs from a PR body")
    parser.add_argument("--body-file", required=True, help="Path to a file containing the PR body")
    args = parser.parse_args(argv)

    body = Path(args.body_file).read_text(encoding="utf-8")
    references = parse_closing_refs(body)
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
