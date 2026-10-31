# Proposed production resource limits

**Accepted by the maintainer on 2026-10-31; not yet in force.** `.choir/certification.json` still has no limits and both flags are false. Setting them is the certification decision; see `docs/EVIDENCE.md`
in `und`.

| Limit | Proposed | Peak measured on the hosted runner | Headroom |
| --- | --- | --- | --- |
| Build bytes | 1 GiB | 1.01 MiB (comparator) | about 1,000 times |
| Build inodes | 100,000 | 159 (comparator) | about 600 times |
| Export bytes | 256 MiB | 1.65 MiB | about 150 times |
| Export inodes | 4,096 | 2 | about 2,000 times |

These are the values that passed live on the hosted runner in the test repository: the
audit, the comparator, a real merge, and `audit-main`. Both quotas together are at most
1.25 GiB of tmpfs on a 16 GiB runner.

They are deliberately far above today's use, because the library should grow without a
limit change, and low enough that a hostile build cannot exhaust the runner. A single
export file is separately capped at 128 MiB, so the export quota does not widen that.

## What this rests on, and does not

- Peaks were sampled every 0.1 s on the real `ubuntu-24.04` x86-64 runner, across the
  library, all six starter tasks, and the comparator's workspace.
- Both quotas full with a container killed at its 2 GiB memory limit left the runner with
  over 12 GiB available and no swap in use, and teardown returned that memory.
- The corpus has 28 exports, so this says little about a much larger library. The limits
  are in one reviewed file and can be raised by a maintainer change.
