# Release procedure

No release is authorized while `.choir/certification.json` has either
validation flag set to `false`, has `resource_limits: null`, or while the audit
admission/checker reports identify themselves as development-only. The current
repository is in exactly that state. This document is a checklist for a future
reviewed release; it is not permission to publish, tag, merge, or enable an
unattended workflow.

## 1. Establish a release candidate

1. Start from a protected `main` commit with no tracked modifications. Record
   its full 40-character SHA; do not build a release from a branch name.
2. Confirm `lean-toolchain`, `lake-manifest.json`, the comparator/exporter
   revisions, container image digest, Choir revision/protocol, admission policy,
   checker inventory, and selected byte/inode budgets match the reviewed
   production manifest. A range-valid value is not automatically a reviewed
   value.
3. Confirm `lake-manifest.json` has no external mathematical packages and run
   the exact-Git downstream check:

   ```sh
   lake build
   lake env lean tests/corpus/Examples.lean
   python3 tests/check_downstream.py
   ```

   The downstream test creates a temporary Git commit, requires its exact SHA
   through Lake's `git`/`rev` fields, builds a consumer, and rejects any
   transitive package. It exercises immutable-pin consumption without claiming
   that a public release already exists.
4. Run the maintained CI matrix and promotion rehearsal on that same candidate.
   Review every acceptance and rejection fixture, not only the final exit code.
5. Review `LICENSE`, `.choir/CHOIR-LICENSE`, attribution/citation fields, and any
   `NOTICE` file. Resolve every adapted-source obligation before publication.
6. Confirm no task placeholder or unfinished task is reachable from
   `TNDLib.lean`, and that every displayed export has a statement, description,
   contributor, citation, and source mapping.

Any candidate change restarts this checklist at its new SHA.

## 2. Obtain production evidence

1. On the supported native-Linux runner, exercise the reviewed production
   parser, build/export quotas, independent checker, comparator, seccomp and
   cleanup/recovery boundary with the selected limits. Development-only markers
   are a hard failure.
2. Require the reserved production evidence profile, both validation booleans,
   exact reviewed resource limits, and the reviewed trusted-input digests. The
   profile transition must be jointly reviewed with the platform validator.
3. Run `audit-main.yml` for the exact candidate SHA. After it completes, list
   every run and rerun for that SHA; the newest attempt must be the successful
   one and no attempt may be pending or ambiguous.
4. Verify the unexpired `tnd-audit-report` artifact metadata and SHA-256 digest,
   the report's `ci.run_id` and `ci.run_attempt`, and the unchanged public
   `audit-SHA-RUN_ID-ARTIFACT_ID.zip` release asset. Independently inspect the
   one-file `audit.json` archive.
5. Rehearse the real branch-protection and serialized merge path, then generate
   the cross-repository index and Pages preview from this evidence. A successful
   local fixture or editable label is not release evidence.

## 3. Tag and publish after explicit review

1. Present the exact SHA, proposed version/tag, production manifest, audit run
   and artifact IDs, selected limits, licenses/attribution, release notes, and
   downstream instructions for final maintainer/user approval.
2. Create a new immutable semantic-version tag such as `v0.1.0` at that exact
   SHA. Never move or reuse a published tag. The release page must state the
   Lean toolchain and full source SHA and link the matching audit evidence.
3. Test a fresh consumer using the public Git URL and the full commit SHA (and,
   separately, the release tag) on the supported toolchain. Confirm Lake resolves
   the tag to the recorded SHA and no transitive dependency appears.
4. Only after that check may documentation call the version a release. Pages may
   display it only when the platform accepts the matching production profile.

A consumer should prefer the immutable full revision even when a friendly tag
is also recorded:

```toml
[[require]]
name = "tndlib"
git = "https://github.com/kmehltretter82/tndlib.git"
rev = "FULL_40_CHARACTER_RELEASE_COMMIT"
```

## 4. Withdrawal and correction

- Do not force-move a tag, rewrite released history, delete audit evidence, or
  replace an asset under the same name. Those actions destroy reproducibility.
- If evidence becomes unavailable or suspect, stop publication, make the site
  show results as unavailable, mark the GitHub release **withdrawn**, and publish
  a security/correctness advisory naming the affected SHA and reason.
- Correct the library on `main`, rerun the complete candidate and evidence
  procedure, and issue a strictly newer tag. Keep the old source and evidence
  available for diagnosis while clearly discouraging reuse.
- GitHub releases are not a package registry with a true yank operation. A
  withdrawal is therefore metadata plus a new corrective release; it is never a
  silent replacement. Downstream users must update their explicit revision.

Record who approved the logical policy, resource manifest, evidence profile,
and publication. Automatic tagging or deployment is out of scope until the
manual procedure has succeeded end to end.
