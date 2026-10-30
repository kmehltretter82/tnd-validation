---
name: Maintainer Choir task draft
about: Draft only; the repository owner publishes approved tasks through Choir.
title: "prove: `<target_decl>`"
---

<!--
This is a maintainer draft, not automatic task approval. The YAML block
below is Choir's machine-readable contract; the prose becomes TASK.md.
Before publication the repository owner must commit and review the exact
target and audit/tasks.json approval, then use the pinned create-task
command documented in docs/API.md. Replace every placeholder and use a
full main commit SHA. Public proposals must be republished as owner-authored
tasks; applying a lifecycle label to another author's issue is insufficient.
-->

---
choir-task-version: 1
type: prove
target_file: tasks/APPROVED_TASK.lean
target_decl: TNDTask.APPROVED_DECLARATION
project_ref:
  repo: kmehltretter82/tndlib
  commit: PASTE_HEAD_SHA_HERE
  toolchain: leanprover/lean4:v4.35.0
deps: []
---

## Statement

Replace this with the exact statement committed and approved by the maintainer.
This draft does not become a claimable task until the repository owner has
published its approved contract and applied the task lifecycle label.

```lean
-- Paste the exact approved declaration here.
```

## Notes for the prover

Any extra context goes here — proof-strategy hints, references, why the
statement is what it is. Plain prose; the agent reads this verbatim.

## Source and request

Link the original request and mathematical source or explain original work.
Credit the source and state the intended constructive interpretation.
