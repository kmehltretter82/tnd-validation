# TND's Choir integration

The overlay comes from Choir commit
`75bc39e40c55542d445653356778c21ada4a66ff`, protocol 9. Automation starts in
`MANUAL`. No repository, task, comment, label, branch protection, or deployment
was changed while staging these files locally.

## Certification is disabled

`.choir/certification.json` deliberately sets `source_binding_validated` to
`false`. Replaying exported proof objects does not yet prove that arbitrary
executable Lean elaboration faithfully represents the published source tree.
The maintained setup action checks this policy before any verification job can
pass. Proof merges and public audit publication remain blocked. Do not enable
the flag merely because mathematical fixtures or infrastructure tests pass.

## How the overlay was generated

The pinned `scripts/upgrade-project.sh` was used in its offline mode with a
seeded `.choir/project.toml` (`prover = "lean4"`, `merge = "manual"`). Its exact
generation prefix, ending before `# --- Idempotency check + commit + push`, was
staged as a temporary script beside the original and run with
`--no-push --force-build-workflow`, without `--repo`. Calls to `uv run python`
in that temporary prefix were replaced with `python3`; its generation helpers
use the standard library. The original script otherwise commits even with
`--no-push`, so it was not run to completion.

This generated the entire upstream package, policy, issue-template, workflow,
and overlay-manifest set, including both per-prover workflow heredocs. The
upstream installer omits `choir_cli/` and `viz/` although its package metadata
requires them; both directories were also copied from the same commit.
`.choir/CHOIR-LICENSE` preserves Choir's Apache-2.0 license. The initial
`overlay.json` records the generated upstream baseline; locally adapted files
are deliberately different from those baseline hashes.

## Local changes and upgrade discipline

`gate/checks.py` makes `tnd-audit` required even when absent. The local
`orchestrator/prs.py` also requires an exact successful trusted workflow run,
rejects protected-path edits, and checks actual administrator-enforced strict
branch protection. `orchestrator/tnd_verification.py` rejects absent, pending,
failed, stale, or wrong-origin evidence. These rules also bind Choir's explicit
override path for the TND verifier.

Run merge commands from this checkout, for example:

```sh
uv run --frozen python -m choir_cli orch --repo kmehltretter82/tndlib --prover lean4 merge 123
```

An independently installed upstream `choir` command does not contain TND's
extra merge rules. The GitHub branch rule must require every context in
`gate.checks.BRANCH_PROTECTION_CONTEXTS`, set `strict: true`, and enable
administrator enforcement. The local merge command refuses if these settings
are absent; their behavior against a base change still needs a live GitHub test.

**Release blocker: rerun-to-merge race.** The local preflight verifies a
complete run listing and uses the latest known attempt by start time, rejecting
missing timing and tied unsuccessful attempts. That snapshot is not atomic
with GitHub's later merge request. A new or rerun audit can be queued, cancelled,
fail, or finish out of order after the preflight while an older `tnd-audit`
commit status is still green: the current reporter posts only after its verify
job. `--match-head-commit` prevents a head change, not a change in the set of
workflow attempts. Strict branch protection evaluates GitHub's required status,
but this implementation has not shown that GitHub binds it to the latest exact
PR/base/attempt in this race. Posting pending at job start alone is insufficient:
the job may be queued or cancelled before posting, or older reporters may post
after newer attempts. Do not enable certified merges until an enforceable design
and actual-GitHub acceptance tests cover these cases, including the administrator
merge identity and an audit starting between preflight and merge.

GitHub documents that the merge API's `sha` checks the PR head and that required
checks must pass for the latest commit; neither statement establishes atomic
binding to the newest workflow attempt. See [merge API](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request)
and [required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

The local merge command now performs the complete workflow-run and branch-
protection preflight twice. Immediately before its `--match-head-commit` merge
request it also fetches the PR again, requires the same open head/base/source
snapshot, and rechecks ordinary required checks. This catches a rerun, base
movement, protection change, or status change during the first preflight. It
does **not** make the operation atomic: an attempt can still be created after
the second run listing and before GitHub processes the merge request. These
extra reads are fail-closed hardening, not grounds to enable certification.

### Candidate serialized merge lane for the personal repository

The best design found that does not assume an organization merge queue is to
put verification attempts and the merge operation under one GitHub Actions
concurrency lease per PR. GitHub now documents `queue: max` for concurrency
groups, allowing queued runs instead of replacing an older pending run. The
maintained `verify-tnd` workflow and a separate maintainer-dispatched merge
workflow would use the exact same group, `cancel-in-progress: false`, and
`queue: max`. The merge workflow would contain no candidate checkout or code;
after acquiring the group it would fetch the PR and complete run listing,
repeat the existing protection/status checks, and issue a direct merge with the
expected head `sha` and without bypassing repository rules. See GitHub's
[concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
and the [conditional merge endpoint](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request).

This gives a prospective linearization rule: an audit ahead of the merge lease
must finish and be observed; an audit entering the group after the merge lease
cannot execute before the merge. If a queued attempt is already visible when
the merge job performs its listing, the existing active-attempt rule rejects
the merge. Re-runs are still relevant because GitHub permits repository writers
to re-run a workflow and retains the original event SHA and privileges; see
[re-running workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

The lane is now authored but **disabled**: `verify-tnd.yml` holds
`tnd-candidate-lane-<PR>`, and `tnd-merge.yml` runs
`orchestrator/merge_lane.py` under the same group only when the repository
variable `TND_MERGE_LANE_ENABLED` is `true`. It takes no override input and binds
the request to an exact head. No automated test has observed GitHub's scheduling;
the local merge command remains the only exercised path.

It requires a `tnd-merge` environment holding a `TND_MERGE_TOKEN` secret. The
default `GITHUB_TOKEN` is not usable: GitHub creates no downstream runs from its
events, so merging with it would silently skip `issue-close-on-merge` and
`audit-main`, and it cannot read branch protection. The token must obey the
same strict administrator-enforced rules as everyone else. Its exact identity
is a reviewed decision that has not been made.

On `kmehltretter82/tnd-validation` (not a release) these have been observed live:
strict administrator-enforced protection with all eight contexts rejected the owner's
direct push (`GH006`); `create-task`, intake, `worker list`, `claim`, a competing claim
(`LOST_RACE`), `heartbeat`, `release`, reclaim, and `submit` worked; a weakened statement
failed `statement-equiv` and `statement-immutability` and passed again once corrected;
and the certification guard kept `tnd-audit` red and GitHub's merge state `BLOCKED`.
Three rapid pushes to one PR queued in the shared lane, one running and one pending with
none cancelled, and a rerun completed as attempt 2 of its run. That covers only the
`verify-tnd` side, because `tnd-merge` has not run, and it does not show the lane's
capacity limit. The user ran `gh pr merge` on PR #2, with and without `--admin`, and
GitHub refused both: "the base branch policy prohibits the merge" and "3 of 8 required
status checks are failing". The project's own merge command has not been run there, and
no successful merge has been observed. With all eight checks green and GitHub reporting
`CLEAN`, `tnd-merge` refused a wrong head by name, then refused the right head as stale:
GitHub reports a `pull_request_target` run's `head_sha` as the PR head, while the
preflight queried the base. With the preflight using the PR head, `tnd-merge` merged PR
#2 at its exact reviewed head using `TND_MERGE_TOKEN`, and the merge triggered
`issue-close-on-merge` (task closed as `choir/done`) and `audit-main` (evidence published
to a release). The variable below was set for that test and has been removed again. The
lane's race boundaries, cancellation, and queue saturation remain untested.

Before setting the variable, a test repository must show that initial runs and
all full/partial reruns acquire the same cross-workflow group, that `queue: max`
never drops an attempt within the supported load, that the merge token obeys
strict administrator-enforced rules, that its merge does trigger the post-merge
workflows, and that an attempt dispatched at each boundary before/during/after
final preflight is either observed or ordered after the merge. Cancellation, a
full queue, delayed run-list visibility, base movement, and direct UI/API merge
behavior also need acceptance tests. Until that evidence exists, the race remains
a release blocker and the current twice-read local path is the only staged
hardening.

All stock required check names remain. Text audits execute the maintained
base's gate code and read submission Git objects as data. Rebuild and trust
report use the isolated audit driver. The stock comparator retains Choir's
workspace construction and Lean comparator; `tnd_comparator.py` wraps its whole
execution in an additional unprivileged, network-free Docker container with
read-only tools and source. Its production entry point requires the same exact
disabled-by-default resource policy as the audit runner, places the writable
build tree on fresh byte-and-inode-limited storage under the trusted
`RUNNER_TEMP`, confirms container cleanup and unmount, and only then classifies
the comparator output. The unbounded `run_container` helper is development-only.
The wrapper requires the linked target to match the base's approved task
registry and rejects unsupported or missing comparator targets instead of
returning green. Native Linux quota enforcement remains a required live test.

Do not run an upstream upgrade directly over this repository: its `rsync
--delete` would remove TND's extra gate modules, and it would replace adapted
workflows and merge enforcement. Generate a new baseline separately, review
the changes against the pinned source, reapply TND's adaptations, and rerun the
boundary tests before adopting another Choir revision.

## Tasks and promotion

Public requests are proposals. The request template never applies
`choir/available`. Owner-authored approved tasks identify a source path and
declaration committed in `audit/tasks.json`; intake refuses another author's
issue as a directly executable task. The sample is `tasks/map_exists.lean` and
`TNDTask.mapExists`. Its intentional placeholder is outside certified imports.

A proof contributor fills that task's proof. The verifier checks changed
registered tasks independently of the published library and records provisional
task evidence. The stock comparator checks the same target against its approved
base statement. A successfully checked task is still outside the library.
Promotion is a separate maintainer change: move the reviewed result into
`TNDLib/`, update `TNDLib.lean` and `audit/exports.json`, and require a fresh
full-library audit of the resulting main commit. A task's completed GitHub state
alone never grants a published constructive badge.

## Workflow and publication boundary

`verify-tnd.yml` uses `pull_request_target`, checks out only the exact base SHA
at depth one with tags disabled, and gives the verifier read permission. Every
proof-verification workflow uses the same shallow-base rule before invoking the
maintained filtered-fetch helper against exact GitHub PR/base/head metadata. It
accepts at most eight proof-surface files, 2,000 changed lines, 256 KiB per
present source blob and 1 MiB in aggregate; fetches the exact head SHA shallowly
with the corresponding Git object filter; and leaves lazy object fetching
disabled. The resulting Git diff and ordinary-blob identities must match the
API listing before later gates or comparator workspace construction. This
bounds candidate Lean bytes under the documented GitHub filtering assumption
but is not a filesystem quota or native-runner validation.

The candidate runs only in the audit driver's network-free container. A fresh
reporter job with no checkout or artifacts
posts `tnd-audit` on the PR head; it alone has `statuses: write`. The local merge
preflight additionally verifies workflow event, path, exact base, and the
generated PR/head/base run title, so an identically named untrusted status is
insufficient.

`audit-main.yml` audits `base = head = github.sha` on main pushes, manual runs
on main, and the first day of each month. Successful evidence is uploaded as
`tnd-audit-report` containing `audit.json`, retained for 90 days. Before upload,
the trusted workflow adds a `ci` object identifying the repository, workflow
path, event, run ID, run attempt, and exact head SHA. A fresh
publisher job validates the original archive's digest and originating run and
head, then uploads the unchanged ZIP as
`audit-HEAD_SHA-RUN_ID-ARTIFACT_ID.zip` to release `tnd-audit-evidence`. It never
unpacks an artifact or runs mathematical source. Only that job has
`contents: write`. Monthly re-audits renew evidence before artifact metadata
expires. Expired or missing evidence must make the public site unavailable for
certification, even if an old release asset remains downloadable.

## Verification performed locally

The local CLI reports `MANUAL` and loads successfully. The repository-wide
Python suite exercises the actual merge function with mocked GitHub responses,
required-check presence, pending/failure/staleness, protected paths, workflow
origins, task matching, container boundaries, public-archive validation, and the
disabled certification policy. The vendored lifecycle and comparator/workspace
suites cover task creation and serialization, intake, competing claims,
heartbeat, release, submission, completion, stale-lease reconciliation, and
workspace construction. Run the current suite with `uv run --frozen --extra dev
python -m pytest -q`; modified Python must also pass Ruff. Hard-coded historical
test counts are intentionally omitted because the boundary suite is still being
expanded.

`maintainer-ci.yml` records the same broad development regression matrix for
reviewed implementation changes and the resulting `main` tree. Because it
checks out and executes the candidate revision, its pull-request job is limited
to same-repository branches; fork heads are never executed. Manual dispatch is
main-only, permissions are read-only, and checkout credentials are not
persisted. The workflow is explicitly non-certifying: it uploads no proof
evidence and does not substitute for native-Linux boundary validation or any
required proof-submission check.

These tests do not establish remote GitHub lifecycle behavior, native-Linux
container/quota execution, comparator parity on a live submission, production
admission/checker isolation, or source certification. No live task, PR, merge,
branch-protection update, release-evidence handoff, or Pages deployment was
performed by this integration work. Source binding, reviewed numeric resource
limits, daemon-visible quota and recovery behavior, production checker markers,
the serialized merge lane, and the live cross-repository evidence path must all
be resolved before those checks can yield a certified release.
