# Proposed production resource limits

**Proposal for review, not a selection.** `.choir/certification.json` still has no limits
and both flags are false. Setting them is the certification decision; see `docs/EVIDENCE.md`
in `und`.

| Limit | Proposed | Measured use | Headroom |
| --- | --- | --- | --- |
| Build bytes | 1 GiB | about 0.4 MiB | about 2,500 times |
| Build inodes | 100,000 | 63 | about 1,500 times |
| Export bytes | 256 MiB | 1.7 MiB | about 150 times |
| Export inodes | 4,096 | 2 | about 2,000 times |

These are the values that passed live on the hosted runner in the test repository: the
audit, the comparator, a real merge, and `audit-main`. Both quotas together are at most
1.25 GiB of tmpfs on a 16 GiB runner.

They are deliberately far above today's use, because the library should grow without a
limit change, and low enough that a hostile build cannot exhaust the runner. A single
export file is separately capped at 128 MiB, so the export quota does not widen that.

## What this rests on, and does not

- Build use was sampled every 0.2 s for the library through the stages, on the ARM64 VM.
- Use has not been measured on the hosted runner, for the comparator's own workspace, or
  for a task build, so those need sampling before these numbers are final.
- The corpus has 28 exports, so this says little about a much larger library.
- tmpfs may swap and the hosted runner has 3 GiB of swap. Simultaneous exhaustion of both
  quotas with a container at its 2 GiB memory limit has not been tested.
