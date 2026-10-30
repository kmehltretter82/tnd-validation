"""Merge one reviewed candidate from inside the serialized verification lane.

`tnd-merge.yml` runs this while holding the same concurrency group as
`verify-tnd.yml`, so no audit attempt can start between the final preflight and
the merge request. Every check stays in `merge_pr`; this entry point only binds
the request to an exact head. It deliberately exposes no override: `force` is
for the overseer's local command, and a dispatch input is not an attributable
human decision.
"""

from __future__ import annotations

import argparse
import re
import sys

from orchestrator.prs import PRError, merge_pr

SHA = re.compile(r"[0-9a-f]{40}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,9}\Z")
PROVER = "lean4"


def merge_candidate(repo: str, number: str, head_sha: str) -> None:
    if NUMBER.fullmatch(number) is None:
        raise PRError("merge lane PR number is not a positive integer")
    if SHA.fullmatch(head_sha) is None:
        raise PRError("merge lane head is not a full commit SHA")
    merge_pr(repo, int(number), prover=PROVER, expected_head_sha=head_sha)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)
    try:
        merge_candidate(args.repo, args.pr, args.head_sha)
    except PRError as error:
        print(f"merge refused: {error}", file=sys.stderr)
        return 1
    print(f"merged #{args.pr} at {args.head_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
