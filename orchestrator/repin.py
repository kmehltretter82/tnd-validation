"""Keep unclaimed tasks pinned to the tree their workers will clone.

A task's `project_ref.commit` is the tree its worker checks out. A merge
that touches the task's `target_file` moves that text, so the pin names a
tree the branch no longer has and the next worker starts from stale
source. The merge that caused the drift is also the event that can repair
it: it knows which files it touched, so no history has to be walked to
find the affected tasks. `issue-close-on-merge` runs this.

Only tasks still labelled `choir/available` are repinned, and that label is
what the merge can see. A claim is a comment (`gate/state/lease_arbiter.py`)
and the label follows it only at the orchestrator's next lease sync, so a
task claimed within that window is still repinned. Nothing reads
`project_ref.commit` after the clone — no check compares a PR's base against
it — so the cost is an issue that displays a commit its holder did not build
on, not a submission that fails. The window closes on its own.

Claimed tasks are otherwise left alone on purpose. Every check runs on
`refs/pull/N/merge`, so a PR from a stale base is either a conflict the
worker resolves or a clean merge the gate verifies against current main. A
current pin saves a worker from starting on text that moved; it is not what
makes the verdict sound.

The batch attempts every eligible task and reports all known per-task
failures. Its CLI exits nonzero when that report is nonempty, so the
post-merge Actions run is visibly incomplete and can be retried. The
triggering merge is first required to be on the current `main` history, then
affected tasks are pinned to the current `main` head rather than blindly to
the event's merge SHA. Each existing task pin must itself be an ancestor of
that head, and the issue body is re-read before editing. Thus rerunning an
older merge after a newer one cannot deliberately move a task backwards. The
workflow also serializes these maintenance runs. Retrying the same merge is
idempotent: tasks already pinned to the resolved head are skipped, while only
failures still need a write.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from orchestrator.tasks.api import (
    LABEL_AVAILABLE,
    MaintainerError,
    list_choir_tasks,
    set_task_pin,
)

SHA = re.compile(r"[0-9a-f]{40}\Z")


def _gh_json(endpoint: str) -> Any:
    """Read one trusted GitHub API object with a bounded `gh` invocation."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        value = json.loads(result.stdout)
    except FileNotFoundError as error:
        raise MaintainerError("`gh` CLI not found in PATH") from error
    except subprocess.TimeoutExpired as error:
        raise MaintainerError("GitHub ancestry query timed out") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        raise MaintainerError(f"GitHub ancestry query failed — {detail}") from error
    except json.JSONDecodeError as error:
        raise MaintainerError("GitHub ancestry query returned invalid JSON") from error
    if not isinstance(value, dict):
        raise MaintainerError("GitHub ancestry query returned a non-object")
    return value


def _sha(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise MaintainerError(f"{context} is not a full commit SHA")
    return value


def current_main_head(repo: str) -> str:
    """Resolve the exact current `main` head from GitHub."""
    value = _gh_json(f"repos/{repo}/git/ref/heads/main")
    obj = value.get("object")
    if not isinstance(obj, dict):
        raise MaintainerError("GitHub main ref is missing its commit object")
    return _sha(obj.get("sha"), context="GitHub main head")


def commit_is_ancestor(repo: str, ancestor: str, descendant: str) -> bool:
    """Return whether two exact GitHub commits form a forward-only move."""
    ancestor = _sha(ancestor, context="ancestor")
    descendant = _sha(descendant, context="descendant")
    if ancestor == descendant:
        return True
    value = _gh_json(f"repos/{repo}/compare/{ancestor}...{descendant}")
    base = value.get("base_commit")
    merge_base = value.get("merge_base_commit")
    if not isinstance(base, dict) or not isinstance(merge_base, dict):
        raise MaintainerError("GitHub comparison omitted commit identities")
    returned_base = _sha(base.get("sha"), context="comparison base")
    returned_merge_base = _sha(
        merge_base.get("sha"), context="comparison merge base"
    )
    status = value.get("status")
    if status not in {"ahead", "behind", "diverged", "identical"}:
        raise MaintainerError("GitHub comparison returned an invalid status")
    return (
        status == "ahead"
        and returned_base == ancestor
        and returned_merge_base == ancestor
    )


def repin_available(repo: str, commit: str, changed: Iterable[str]) -> dict[str, Any]:
    """Repin open unclaimed tasks whose target file is in `changed`.

    `commit` is the triggering merge commit. It must still be reachable from
    current `main`; the current head is the actual pin target. Returns the
    tasks moved, and any whose issue body could not be rewritten; a single
    task-specific GitHub failure does not abandon the rest.
    """
    event_commit = _sha(commit, context="triggering merge commit")
    target = current_main_head(repo)
    if not commit_is_ancestor(repo, event_commit, target):
        raise MaintainerError(
            "triggering merge commit is not on the current main history"
        )
    touched = set(changed)
    repinned: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for handle in list_choir_tasks(repo, state="open", label=LABEL_AVAILABLE):
        record = handle.record
        if record is None or record.target_file not in touched:
            continue
        if record.project_ref.commit == target:
            continue

        entry = {
            "issue": handle.number,
            "target_file": record.target_file,
            "from": record.project_ref.commit,
            "to": target,
        }
        try:
            if not commit_is_ancestor(repo, record.project_ref.commit, target):
                raise MaintainerError(
                    "current task pin is not an ancestor of current main; "
                    "refusing a non-forward repin"
                )
            set_task_pin(
                repo,
                handle.number,
                target,
                expected_commit=record.project_ref.commit,
            )
        except (MaintainerError, ValueError) as e:
            failed.append({**entry, "reason": str(e)})
            continue
        repinned.append(entry)

    return {
        "event_commit": event_commit,
        "commit": target,
        "repinned": repinned,
        "failed": failed,
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point for the workflow step.

    The merge is already complete, but an incomplete maintenance pass must
    still make the workflow red. The JSON retains every attempted outcome;
    exit 1 means at least one eligible issue could not be repinned.
    """
    p = argparse.ArgumentParser(description="Repin unclaimed tasks after a merge")
    p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--commit", required=True, help="the tree to pin to")
    p.add_argument("--files-file", required=True,
                   help="file of repo-relative paths the merge touched, one per line")
    a = p.parse_args(argv)

    changed = [
        line.strip()
        for line in Path(a.files_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = repin_available(a.repo, a.commit, changed)
    print(json.dumps(result, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
