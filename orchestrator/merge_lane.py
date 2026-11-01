"""Merge one reviewed candidate from inside the serialized verification lane.

`tnd-merge.yml` runs this while holding the same concurrency group as
`verify-tnd.yml`, so no audit attempt can start between the final preflight and
the merge request. Every check stays in `merge_pr`; this entry point binds the
request to an exact head and, when GitHub App credentials are provided by the
`tnd-merge` environment, mints a short-lived repository-scoped installation
token in memory. It deliberately exposes no override: `force` is for the
overseer's local command, and a dispatch input is not an attributable human
decision.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from orchestrator.github_app import APP_ID, GitHubAppError, mint_installation_token
from orchestrator.prs import PRError, merge_pr

SHA = re.compile(r"[0-9a-f]{40}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,9}\Z")
PROVER = "lean4"


def merge_candidate(
    repo: str,
    number: str,
    head_sha: str,
    *,
    actor: str | None = None,
    app_id: str | None = None,
    private_key_pem: str | None = None,
) -> None:
    if NUMBER.fullmatch(number) is None:
        raise PRError("merge lane PR number is not a positive integer")
    if SHA.fullmatch(head_sha) is None:
        raise PRError("merge lane head is not a full commit SHA")
    kwargs: dict[str, object] = {
        "prover": PROVER,
        "expected_head_sha": head_sha,
    }
    if actor is not None:
        if not actor.strip():
            raise PRError("merge lane actor must not be blank")
        kwargs["actor"] = actor.strip()
    if app_id is not None or private_key_pem is not None:
        if not app_id or APP_ID.fullmatch(app_id) is None or not private_key_pem:
            raise PRError("merge lane requires both TND_MERGE_APP_ID and TND_MERGE_APP_PRIVATE_KEY")
        try:
            token = mint_installation_token(repo, app_id, private_key_pem)
        except GitHubAppError as error:
            raise PRError(f"GitHub App authentication failed: {error}") from error
        os.environ["GH_TOKEN"] = token
        kwargs["app_id"] = int(app_id)
    merge_pr(repo, int(number), **kwargs)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)
    actor = os.environ.get("TND_MERGE_ACTOR")
    app_id = os.environ.get("TND_MERGE_APP_ID")
    private_key = os.environ.get("TND_MERGE_APP_PRIVATE_KEY")
    try:
        merge_candidate(
            args.repo,
            args.pr,
            args.head_sha,
            actor=actor,
            app_id=app_id,
            private_key_pem=private_key,
        )
    except PRError as error:
        print(f"merge refused: {error}", file=sys.stderr)
        return 1
    print(f"merged #{args.pr} at {args.head_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
