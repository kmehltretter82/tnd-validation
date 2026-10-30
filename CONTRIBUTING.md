# Contributing to tndlib

This guide describes the planned pilot workflow. Certification is disabled while the source-verification boundary is being validated; no public end-to-end contribution has been accepted. Do not assume an open request is ready until the repository owner publishes a separate approved Choir task.

## Before you start

- Install [Lean with elan](https://lean-lang.org/install/), Git, Python, `uv`, and the [GitHub CLI](https://cli.github.com/); authenticate `gh` with your own GitHub account.
- Build the library with `lake build`. The repository's `lean-toolchain` selects Lean `v4.35.0`; the mathematical library does not depend on Mathlib.
- Understand the [proposed logical policy](README.md#constructive-policy). A compiling proof can still depend on a prohibited axiom or change the intended statement.
- You may work directly or use your own proving agent. Review and understand your contribution, including its assumptions and dependencies.

To propose work, use the [request form](https://github.com/kmehltretter82/tndlib/issues/new?template=request.yml). Include the statement, mathematical source, explanation, and constructive considerations. Requests do not grant a lease or authorize changes to the library. The [API guide](docs/API.md) explains approval and the exact task schema.

## Join and claim a task

Choir's current [contributor manual](https://github.com/Weber-GeoML/Choir/blob/75bc39e40c55542d445653356778c21ada4a66ff/docs/agents/CONTRIBUTOR.md) explains the full client workflow. Use the project-compatible pinned Choir revision:

```sh
git clone https://github.com/Weber-GeoML/Choir.git
git -C Choir checkout 75bc39e40c55542d445653356778c21ada4a66ff
sh Choir/scripts/join.sh kmehltretter82/tndlib
```

After setup reports `READY`, inspect available tasks and claim one by issue number:

```sh
choir worker list kmehltretter82/tndlib --json
choir worker claim kmehltretter82/tndlib ISSUE_NUMBER --json
```

Replace `ISSUE_NUMBER` with the chosen number. A usable claim requires both `outcome: "WON"` and a non-null `prepared` object; change directory to `prepared.path`, inspect its `record` and `advisories`, and read `TASK.md` and `CHOIR.md`. `WON` with `setup_failed` means you may hold the lease even though workspace preparation failed. Repair setup or release the claim before abandoning it. JSON outcomes, including `LOST_RACE`, `SKIPPED`, and `ERROR`, can exit zero; inspect the payload. `LOST_RACE` means another worker or session holds the claim.

A label is only a snapshot of the lease. Preserve the claim's `session` and local `.choir-lease.json`; they distinguish concurrent agents using the same account. Open dependency issues produce advisories, not claim blockers. If needed results are absent from the pinned commit, ask the maintainer to update the approved task before starting. Do not run `choir update` blindly: it follows upstream rather than retaining this project's reviewed pin.

## Prove and submit

Replace the placeholder in the approved target declaration with a proof. Keep the statement and existing definitions unchanged. Work only in the task's permitted files; do not change the verifier, policy, dependencies, workflows, or toolchain. Do not add assumptions or invoke classical choice indirectly. The unproved task file is separate from the certified library.

The staged pilot's maintained fetch preflight accepts at most eight changed
proof-source files and 2,000 changed lines. Renames are rejected. Each present
source blob must be at most 256 KiB and all candidate source blobs together at
most 1 MiB. These are host-risk limits, not mathematical style targets; an
ordinary task proof should normally change just its one registered file.

The current admission prototype is deliberately **term-only**. Replace the
task's `by sorry` placeholder with a plain `:=` term (or permitted equation
clauses), for example a `fun`, constructor, application, or `match` expression.
Every tactic-mode `by` block is rejected today, including blocks using `exact`,
`simp`, `omega`, or `decide`, even when the resulting proof would be
constructive. Custom syntax, attributes, local `where` declarations, and other
forms outside the reviewed subset are also rejected. This restriction is a
source-boundary limitation, not a claim that tactics are inherently classical.
See [the admission contract](audit/admission/README.md) and its
[semantic review](audit/admission/SEMANTICS.md) before investing in a proof.

Run the build and task commands in your prepared workspace. For a Lean task file, a typical local check is:

```sh
lake build
lake env lean tasks/TARGET_FILE.lean
```

These commands provide useful diagnostics; the maintained-base independent verifier determines whether the proof and its dependencies meet the policy.

Before submission, reproduce the maintained admission decision with a trusted
Lean 4.35 executable. The admission CLI expects the task to be staged as
`Task.lean` beside an exact library snapshot:

```sh
TND_ADMISSION_DIR=$(mktemp -d)
cp -R TNDLib TNDLib.lean "$TND_ADMISSION_DIR/"
cp tasks/TARGET_FILE.lean "$TND_ADMISSION_DIR/Task.lean"
python3 audit/admission/admit.py --lean "$(elan which lean)" \
  --source "$TND_ADMISSION_DIR" --task map_exists --role solution
```

For the pilot, `map_exists` is the only maintained task ID ([unapproved drafts](docs/STARTER-QUEUE.md) are not yet tasks). A successful report
has `status: "admitted-source-syntax"`; a nonzero exit with
`status: "rejected"` means the source shape is outside the current subset. Its
free-text `reason` is diagnostic and not yet a stable automation code. Delete
the temporary directory after inspecting it. Passing this development parser
does not certify the proof; the isolated build and independent checker still
decide statement and dependency validity.

Once both local checks succeed, commit your proof in the prepared branch and
submit it:

```sh
git add tasks/TARGET_FILE.lean
git commit -m 'Prove the approved task'
choir worker submit kmehltretter82/tndlib ISSUE_NUMBER --json
```

Submission creates or uses your fork, pushes the branch, and opens or reuses a PR linked with `Closes #ISSUE_NUMBER`. It does not grant acceptance. To fix a rejected proof, commit the correction in the same workspace and run `submit` again; the existing open PR is reused.

For long-running work, refresh before the pinned client's 24-hour stale-lease window expires:

```sh
choir worker heartbeat kmehltretter82/tndlib ISSUE_NUMBER --json
```

Confirm `refreshed: true`. If you cannot finish, release while retaining your work:

```sh
choir worker release kmehltretter82/tndlib ISSUE_NUMBER --keep-workspace --json
```

Without `--keep-workspace`, release removes the local workspace and task branch. Confirm `comment_posted: true`; the issue label may update later. See the [JSON response and failure contract](docs/API.md#json-outcomes-and-failure-handling) before automating these commands. For these public worker operations, a nonzero `--json` result is the version-1 `{schema_version, ok, operation, error}` envelope. Branch on its closed `error.code`, not its diagnostic message. Only a read-only `list` transport failure is marked retryable; inspect remote state before repeating any mutation whose `details.mutation_state` is `unknown`.

## What the checks mean

- **Missing or pending check:** no acceptance has happened. A first-time contributor's GitHub Actions run can be held for maintainer approval; wait for a maintainer to investigate.
- **Statement or definition mismatch:** restore the approved statement and definitions. Raise a task defect if the statement is wrong.
- **Prohibited dependency:** remove the direct or indirect dependency, including `Classical.choice`, `sorryAx`, custom axioms, or native-evaluation axioms.
- **Verifier unavailable or infrastructure failure:** retain the PR and ask a maintainer to investigate. A missing audit does not become a passing audit.

Maintainers review each submission. An accepted task proof is not yet a certified library release: a maintainer separately promotes it into `TNDLib`, and the exact resulting library commit must pass the full audit before it is published as a result.

See [Requests, tasks, and evidence](docs/API.md) for public GitHub API and check-inspection examples.
