# Requests, tasks, and evidence

This interface is pinned to Choir commit `75bc39e40c55542d445653356778c21ada4a66ff`, protocol **9**, with TND's local merge rules. The task-record schema version is **1**; it is separate from the protocol version. Certification is currently disabled and no public pilot has been validated. The examples below describe operations to use after maintainer launch; they do not claim that a task or release already exists.

## Authentication and authority

Contributors authenticate GitHub CLI with their own account:

```sh
gh auth login
gh auth status
gh api user --jq .login
```

Choir invokes that local `gh` session. A contributor needs permission to comment on public issues, create or use their own fork, push their branch there, and open a pull request. They do not need write access to `tndlib`; they must not assign themselves or edit lifecycle labels to claim work. The owner account publishes approved tasks and controls labels, repository rules, and merges. The present intake workflow specifically requires an **owner-authored** task issue, so adding a label to someone else's proposal does not approve it. An organization or bot account would require a reviewed change to that policy.

No shared token belongs in a task, proof, browser, or public index. The Pages frontend reads public static data without credentials. Maintainers use the patched CLI from a trusted `tndlib` checkout for merges, as specified in [the integration notes](../.choir/TND-INTEGRATION.md); an upstream-only `choir` installation lacks TND's merge checks.

## Public operations

Here `N` is an issue number, `P` is a pull-request number, and `SHA` is a full commit ID. All REST paths are relative to `https://api.github.com`. Use the Choir commands below for lease mutations so the pinned arbitration protocol remains authoritative.

| Operation | GitHub interface used | Actor and returned data |
| --- | --- | --- |
| Propose mathematics | `POST /repos/kmehltretter82/tndlib/issues` | Contributor; issue number and URL. A proposal has no executable lifecycle label. |
| Publish an approved task | `choir orch create-task` creates an issue with `choir/task` and `choir/available` | Owner; `{created, number, title}`. Intake validates and adds `choir/type:prove` or removes availability on error. |
| Discover tasks | `GET /repos/kmehltretter82/tndlib/issues?state=open&labels=choir%2Ftask` | Public reader; issue JSON. `choir worker list --json` returns parsed candidate records. |
| Claim or release | `POST /repos/kmehltretter82/tndlib/issues/N/comments` via Choir | Contributor; lease comments determine the holder, not labels or assignees. |
| Heartbeat | `PATCH /repos/kmehltretter82/tndlib/issues/comments/COMMENT_ID` via Choir | Current holder edits their own lease comment. |
| Submit or correct a proof | Push to the contributor's fork and `POST /repos/kmehltretter82/tndlib/pulls` via Choir | Contributor; `{pr_number, pr_url, reused_existing_pr}`. Repeated submission pushes corrections and reuses the open PR for that branch. |
| Inspect checks | `GET /repos/kmehltretter82/tndlib/commits/SHA/check-runs` and `/commits/SHA/status` | Public reader; checks and commit statuses. Exact trusted workflow provenance is also required. |
| Inspect evidence | `/actions/workflows/audit-main.yml/runs`, `/actions/runs/RUN_ID/artifacts`, and `/releases/tags/tnd-audit-evidence` | Public metadata and release assets. A matching successful current attempt and artifact digest are required. |

## Propose a formalization

Use the [request form](https://github.com/kmehltretter82/tndlib/issues/new?template=request.yml), or put the proposed statement, hypotheses, mathematical source/citation, explanation, and constructive considerations in `request.md`, then run:

```sh
gh issue create --repo kmehltretter82/tndlib \
  --title 'Request: your result' --body-file request.md
```

GitHub silently drops labels set on a new issue by anyone without push access, and the public index lists only `tnd/proposal` issues. So a request made this way does not appear on the site until a maintainer adds that label; the form applies it for you. This publishes a proposal, not a task. Lean syntax is optional. A maintainer reviews the source and intended meaning, commits the exact Lean statement outside certified imports, and approves its inventory before publishing a separate task. Reference the proposal from the task prose. Neither a request title nor an editable label establishes a theorem statement or constructive verification.

## Task schema and maintainer approval

The canonical implementation is [TaskRecord](../gate/state/task_record.py), [intake](../gate/state/intake.py), and [serialization](../orchestrator/tasks/serialize.py). A task issue starts with this YAML front matter, followed by human-readable context:

```yaml
---
choir-task-version: 1
type: prove
target_file: tasks/map_exists.lean
target_decl: TNDTask.mapExists
project_ref:
  repo: kmehltretter82/tndlib
  commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  toolchain: leanprover/lean4:v4.35.0
deps: []
---
```

The example SHA is a placeholder. Before publication, replace it with the full reviewed main commit containing the target and its entry in `audit/tasks.json`. Copy the approved statement into the prose, explain the task, cite its mathematical source, and link the originating proposal.

| Field | Pinned schema and TND use |
| --- | --- |
| `choir-task-version` | Required integer `1`. Unknown versions and extra fields are rejected. |
| `type` | Choir accepts `prove`, `golf`, or `index`; the TND pilot publishes `prove` tasks. |
| `target_file` | Required repository-relative path without `..` or backslashes; Lean intake requires `.lean`. TND additionally requires an approved task-registry path. |
| `target_decl` | Required dot-separated Lean identifier; must exactly match the approved task export and name a theorem, because the comparator compares statements. |
| `project_ref` | Required `repo`, `commit`, `toolchain`; no extra fields. Choir accepts abbreviated hashes of at least seven hex characters, but TND publishes full 40-character hashes and Lean `4.35.0`. |
| `deps` | Required list of positive issue numbers; use `[]` when empty. Open dependencies produce client advisories, not a hard claim gate. |
| `blueprint_ref` | Optional string naming a planning node; omit when unused. |

A closed dependency issue is not a library import. Maintainers must wait for needed results to be promoted and available at the task's pinned commit before publishing a dependent task. Do not repin a task under an active claim; coordinate with its holder and publish a fresh approved contract when needed.

A draft issue body can be validated locally without posting it:

```sh
uv run --frozen python -m gate.state.intake_cli \
  --body-file task.md --repo kmehltretter82/tndlib --prover lean4 > intake.json
```

Read `status` in `intake.json`; the command also exits zero for a structured validation rejection. This checks the Choir schema only, not owner authorization, source existence, mathematical correctness, or registry approval.

After the target, inventory, source citation and exact statement are reviewed and present on main, the owner publishes from that trusted checkout. Repository lifecycle labels must already be provisioned. This example uses the sample task and makes a public issue:

```sh
TND_BASE_SHA=$(git rev-parse HEAD)
uv run --frozen python -m choir_cli orch --repo kmehltretter82/tndlib --prover lean4 \
  create-task --title 'Prove TNDTask.mapExists' --type prove \
  --target-file tasks/map_exists.lean --target-decl TNDTask.mapExists \
  --commit "$TND_BASE_SHA" --toolchain leanprover/lean4:v4.35.0 \
  --prose 'Prove the exact committed TNDTask.mapExists statement. Read tasks/map_exists.lean and the approved request for its explanation and source.'
```

`create-task` validates/serializes the Choir record and immediately creates a claimable issue; it is not a dry run and does not itself check TND's inventory or certify the mathematics. The owner must complete those checks first. Keep the public request and maintainer task separate.

## Discover, claim, heartbeat, release, and submit

Install the pinned contributor client as described in [CONTRIBUTING.md](../CONTRIBUTING.md). Explicit `--json` is useful for both agents and shell scripts:

```sh
choir worker list kmehltretter82/tndlib --json
choir worker claim kmehltretter82/tndlib N --json
choir worker heartbeat kmehltretter82/tndlib N --json
choir worker release kmehltretter82/tndlib N --keep-workspace --json
choir worker submit kmehltretter82/tndlib N --json
```

These are separate operations, not a sequence to run blindly: submit a completed claim, or release unfinished work. Release normally removes the local workspace and branch; `--keep-workspace` preserves them. Use `heartbeat --session SESSION` only with the session returned by your own successful claim when working outside its workspace. Claims become stale after 24 hours without a fresh heartbeat under this pinned client.

`worker list` is a convenience view capped at 200 candidate issues. Read the complete task snapshot and lease comments with pagination when needed:

```sh
gh api --paginate 'repos/kmehltretter82/tndlib/issues?state=open&labels=choir%2Ftask&per_page=100'
gh api --paginate 'repos/kmehltretter82/tndlib/issues/N/comments?per_page=100'
```

The lease wire format is a `choir-lease` fenced block with `login`, `action` (`claim`, `heartbeat`, `release`), protocol `9`, and a worker `session`. The authoritative login and timestamps come from GitHub's comment metadata. [The arbiter](../gate/state/lease_arbiter.py) resolves competing live claims; do not create an alternative lease protocol or infer ownership from the issue label. Keep the returned session and `.choir-lease.json` with the workspace.

## JSON outcomes and failure handling

The [worker CLI](../client/cli.py) serializes the following responses. `reason`, `setup_failed`, and `refused` are diagnostic text, not stable enumerated reason codes.
The returned `record` uses Python-model field names (`choir_task_version`), while the issue's YAML uses the wire alias `choir-task-version`; do not paste the JSON object as issue front matter without the canonical serializer.

| Command | JSON contract | Required handling |
| --- | --- | --- |
| `list` | Array of `{number, title, labels, priority, difficulty, record}` | `record: null` means malformed task data, not an approved target. |
| `claim` | `{outcome, reason, winner, session, prepared}` | `outcome` is `WON`, `LOST_RACE`, `SKIPPED`, or `ERROR`; every structured outcome exits zero. |
| Winning claim | `prepared: {path, record, branch, advisories}` | Start only when `outcome == "WON"` and `prepared` is non-null. A win can instead include `setup_failed` and `workspace`; the lease may still be held. |
| `heartbeat` | `{refreshed, repo, issue, session}` | `refreshed: false` exits zero in JSON mode but is not a successful refresh. Null session means the client could not identify the workspace session. |
| `release` | `{comment_posted, workspace_removed}` | Confirm the release comment was posted; labels may lag. |
| `submit` | `{pr_number, pr_url, reused_existing_pr}` | Submission creates or updates review work, not acceptance. |
| Maintainer `merge` | `{merged, number, refused}` on a gate refusal | `merged: false` is a structured refusal even with exit zero. Never treat command completion as a passed audit. |

`LOST_RACE` means another worker/session owns the lease; choose another task. `SKIPPED` covers such conditions as closed/invalid/unavailable issues or protocol mismatch. `ERROR` describes a failed claim operation, possibly after a comment was posted. Inspect the lease before retrying. On `setup_failed`, retain the session, repair setup or release the claim; do not start another session assuming the lease was undone. These operation outcomes are successful production of a structured answer and therefore exit zero even when the operation itself did not achieve the requested state.

### Stable worker error envelope

When one of the five public worker commands cannot produce its operation
payload, `--json` writes exactly one versioned error object to stdout and exits
nonzero:

```json
{
  "schema_version": 1,
  "ok": false,
  "operation": "claim",
  "error": {
    "code": "transport_error",
    "message": "The remote service could not be reached reliably.",
    "retryable": false,
    "details": {"mutation_state": "unknown"}
  }
}
```

The closed version-1 `code` set is:

| Code | Meaning and retry rule |
| --- | --- |
| `invalid_arguments` | The command was not invoked correctly. Fix the invocation; do not retry it unchanged. |
| `authentication_required` | The GitHub CLI reliably reported missing authentication. Authenticate, then make a new decision. |
| `authorization_denied` | GitHub reliably returned HTTP 403. Do not retry without changing authority or access. |
| `transport_error` | A timeout or reliably transient HTTP status occurred. `retryable` is true only for read-only `list`; mutation commands remain false because their write may have landed before the response was lost. |
| `remote_protocol_error` | A successful remote call returned malformed/non-JSON or schema-invalid data, or a non-transient HTTP response. Do not infer an operation result. |
| `workspace_error` | A positively identified local workspace, metadata, or Git operation failed. Repair local state before retrying. |
| `internal_error` | The cause could not be classified safely, including an ambiguous generic `gh` failure. Do not guess from `message`. |

`operation` is `list`, `claim`, `heartbeat`, `release`, or `submit`. A failure
while selecting/parsing an unknown worker subcommand uses `worker`. The
human-oriented `message` may change and is deliberately redacted; automation
must branch only on the other fields. `details.mutation_state` is
`not_applicable` for a read, `not_started` for rejected mutation-command
arguments, and `unknown` when a mutation command reached its implementation
but did not return operation data. A release whose lease comment was posted
before local cleanup failed instead reports `mutation_state: "completed"`,
`comment_posted: true`, and `workspace_removed: false`. A submit whose push/PR
completed before its final issue comment failed reports
`mutation_state: "completed"` plus the known `pr_number`, `pr_url`, and
`reused_existing_pr` values. These are still nonzero envelopes because the
complete workflow did not finish, but callers must not repeat the remote
mutation as though it never happened.

Successful payloads are intentionally unchanged and are not wrapped in
`{ok:true}`. In particular, `ClaimOutcome.ERROR`, a won claim with
`setup_failed`, and `heartbeat` with `refreshed:false` remain operation data,
not transport envelopes. The latter heartbeat result is advisory by design
and can include a best-effort GitHub failure; inspect the lease before acting.

The client classifies authentication/authorization only from GitHub CLI exit
4 or a numeric HTTP status, never from changeable English stderr. Unknown
future exceptions therefore fail closed as `internal_error`. A killed process,
broken stdout pipe, or invalid/missing JSON still lies outside any in-process
contract; treat it as an unknown failure and never retry a mutation blindly.
The audit driver's free-text rejection `reason` has the same limitation and
must not be presented as a stable code.

The [intake CLI](../gate/state/intake_cli.py) emits `{status, comment, should_post_comment, add_labels, remove_labels}` and, on error, `errors: [{code, field, message, hint}]`. Its stable codes are:

- `no_frontmatter`, `unterminated_frontmatter`, `invalid_yaml`: fix the issue-body framing or YAML.
- `missing_field`, `unknown_field`, `type_mismatch`, `invalid_value`: fix the named schema field.
- `unknown_version`: use supported task schema `1`.
- `repo_mismatch`: pin this repository rather than a different project.
- `target_file_extension`: use the selected prover's `.lean` target.

The owner-author rejection occurs before this parser in the workflow and is reported in the workflow log; it does not produce the parser's JSON envelope. An arbitrary contributor request cannot be repaired into an approved task merely by changing its YAML.

## Verification and promotion

Inspect the current pull request without assuming that submission succeeded:

```sh
gh pr checks P --repo kmehltretter82/tndlib --json name,state,bucket,link
gh pr view P --repo kmehltretter82/tndlib --json headRefOid,baseRefOid,url
```

A missing, pending, failed, stale, or wrong-origin required audit blocks acceptance. A contributor log or matching status name alone is insufficient. The maintained merge path checks the trusted workflow, exact head and base, required checks, and administrator-enforced repository rules. The certification-disabled flag currently blocks production verification regardless of local fixture success.

The [audit driver](../audit/run.py) produces `schema_version`, `status`, `base_sha`, `head_sha`, pins, source hashes, and proof/axiom details. Rejection has `status: "rejected"` and a diagnostic `reason`; optional checker output is diagnostic only. `status: "verified-proof-objects"` is developmental proof-object evidence and never source certification. Approved task proofs appear under `tasks` and do not certify library exports. Missing or unreadable reports mean no certification.

A maintainer separately promotes an accepted proof into `TNDLib`, updates its approved export inventory and display metadata, and obtains a fresh full-library audit of the resulting main commit. When production gates are validated, trusted `audit-main.yml` runs publish `tnd-audit-report` with `audit.json`. The public release asset `audit-SHA-RUN_ID-ARTIFACT_ID.zip` under `tnd-audit-evidence` is the unchanged artifact archive. The platform requires the latest exact-source workflow attempt to succeed, matching report `ci` metadata including `run_attempt`, an unexpired artifact, and an identical GitHub artifact SHA-256 digest. Old successes cannot mask a newer failed or pending audit. Tasks carry a separate snapshot timestamp.

## Reuse

After a verified `tndlib` release exists, use its exact commit as a Lake dependency and `import TNDLib` or the needed modules. Pin Lean to that release's toolchain. The future immutable Git form and publication/withdrawal checklist are recorded in [the release procedure](RELEASING.md). No release currently satisfies it. Task completion alone is not a verified library release.
