# Draft task: transport an existential witness

This is a local pilot fixture, not a published or claimable GitHub issue. A maintainer must validate the task workflow and publish the task through Choir before inviting contributions.

- **Target file:** `tasks/map_exists.lean`
- **Target declaration:** `TNDTask.mapExists`
- **Prerequisites:** the pinned `tndlib` baseline and familiarity with existential introduction/elimination.
- **Goal:** given a witness `x` satisfying `p (f x)`, provide a witness in the codomain satisfying `p`.
- **Acceptance:** replace the placeholder with a proof of the exact approved statement, with no additional hypotheses, unfinished obligations, or disallowed axiom dependencies. Preserve the target statement and definitions. The task proof must pass the maintained-base independent checker and review.
- **Promotion:** an accepted task proof remains separate from certified exports. A maintainer may propose its inclusion in `TNDLib`; the resulting exact library commit must pass the full audit before appearing as a published result.

The local solution fixture at `tests/tasks/MapExistsSolution.lean` helps test the pipeline. It is not itself a published contribution.
