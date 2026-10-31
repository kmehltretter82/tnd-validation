# Native-Linux evidence, 2026-10-30

**Development evidence only.** It selects no budget, changes no certification flag,
and must not be cited as production validation. Most of this came from an expendable
QEMU virtual machine; "Hosted runner" below records the repeat on the target runner.

Environment: Ubuntu 24.04.5, Linux 6.8.0-147-generic, aarch64, 3 vCPU, 3 GiB RAM, no
swap, Docker 29.1.3 with overlayfs, cgroup v2, and its built-in seccomp profile.
Lean 4.35.0 came from `audit/install_lean.py`.

## Hosted runner

One `workflow_dispatch` run on GitHub's `ubuntu-24.04` in the separate test repository
`kmehltretter82/tnd-validation` (commit `85744f0`, run `41133552468`), with the same
three harnesses: Linux 7.0.0-1017-azure, x86-64, 4 vCPU, 16 GiB RAM, **3 GiB swap**,
Docker 28.0.4, overlay2, cgroup v2, built-in seccomp, `sudo` available.

- The x86-64 Lean archive installed through the verifier.
- `RUNNER_TEMP` (mode 755, owned by `runner`) passed the parent-chain check.
- Every boundary, tamper, recovery, and container-limit check held, all 15 hostile
  sources were rejected, and all 4 Git cases passed. The recovery step found nothing
  left to reconcile.
- Parses took 2.5 to 7.9 s against the 90 s timeout.
- The clean library build took 1.1 s and 0.47 GiB; the checker and exporter took
  10.9 s and 1.6 GiB.
- `maintainer-regression` passed its whole matrix, and `audit-main` stopped at the
  certification guard with every later step skipped. Both ran on that commit.

Four `hosted-validation` runs have now passed, the last on commit `83a2db7`, after the
recovery fix.

Failure behavior on the same runner, holding real mounts and a container attached as
production attaches them (commit `83a2db7`):

- A real run cancellation first left recovery refusing, with mounts and container in
  place. The owner had outlived its cancelled step as an orphan, and an attached client
  would have blocked recovery too. After the fix, two cancellations and one `SIGKILL`
  of the owner each recovered completely, including the orphaned owner.
- Killing `Runner.Worker` ended the job as a failure. No later step ran and no report
  was uploaded, so that case rests on VM disposal, as designed.

Filtered acquisition ran live in `verify-tnd` through GitHub's real API and Git server.
A valid proof PR passed it. Five hostile PRs were refused at that step, before any
toolchain or candidate code ran: a 300 KB blob (absent from the filtered fetch), 12
files, 2,500 changed lines, a protected-path edit, and a symlink at the task path. The
symlink's reason names an inconsistent listing rather than the file type, so that
message is not a precise diagnosis.

With placeholder test-only certification flags in that repository, `audit/run.py verify`
ran end to end on a real proof PR for the first time and `tnd-audit`, `rebuild`, and
`trust-report` went green. This found two defects mocked tests had hidden. `lake build`
of the pinned tools failed under `GIT_NO_LAZY_FETCH=1`, in both the shared setup and the
comparator workflow; lazy fetch is now allowed for those two trusted build steps only.
The generated comparator workspace also could not import a task outside the published
library. The fix passes a real local Lake build but has **not yet run on the hosted
comparator**, so no run has yet had all eight required checks green.

The swap matters for budgets: tmpfs may swap, so a quota mount's bytes are not all
held in RAM here, unlike on the VM.

## Observed on the VM

Reproduce these with `tests/audit/linux_boundary_smoke.py`,
`tests/audit/linux_container_limits.py`, and `tests/audit/linux_git_integration.py`.

| Area | Result |
| --- | --- |
| Lean archive | Official `linux_aarch64` archive installed and self-identified in 98 s (3.1 GiB unpacked). One flipped byte in the real archive was refused before extraction, leaving nothing behind. |
| Quota on the host | 8 MiB / 256-inode tmpfs: byte, inode, and sparse-then-dirty writes stopped with `ENOSPC` at the limit. Execution was refused. The export mount's limit is separate. |
| Quota in a container | The daemon saw the host mount. A non-root, capability-free, network-free container with a read-only root hit the same byte and inode limits, could not execute from the mount, could not write through a read-only stage mount, and had no Docker socket. |
| Tampering | Nested and stacked mounts and mode changes were refused. Teardown still succeeded after a candidate-style `chmod 000` of a mount root and with files present. |
| `SIGKILL` | Two mounts and a running container survived the owner's death. Recovery refused a live owner, a surviving process naming the root, and a nested mount; then removed the container and left no mount or path, without affecting a live neighbouring boundary. Three consecutive passes. |
| Lean through quota stages | `lake build` and export succeeded through `audit.resource_stages`. With the build bytes, build inodes, or export bytes set too low, the run failed with no output and no residue. |
| Container limits | Under the exact parser and build arguments: a memory bomb was killed at the limit, a fork bomb stopped at 128 processes, `/tmp` capped at 32 MiB (parser) and 256 MiB (build), `/dev/shm` at 64 MiB, and a CPU spin in the parser was killed at 60 s. No routes or interfaces, no capabilities, seccomp filtering, `no_new_privs`, read-only root and toolchain, no Docker socket, `mount` refused, and `/tmp` is noexec. An output flood was refused at once. No container remained. |
| Hostile Lean source | All 15 cases rejected. Deep nesting that fits the size limit reached the parser and hit its depth guard. `#eval`, tactics, macros, and a mid-file `import` were refused by syntax kind. Invalid UTF-8 and oversized files never reached it. Each parse took 5 to 30 s here against a 90 s timeout, so a slower runner needs checking. |
| Git to admission, build, and export | `linux_git_integration.py` passed all 4 cases with a host-mounted toolchain, including rejecting an unimported module and an artifact overwrite. This drives the runner's stages, not `verify()`. |
| Test matrix | 408 pytest and 125 audit unittests with no skips, with `TND_LEAN_ROOT` set as in CI; 67 admission and all proof-object fixtures; 38-declaration promotion rehearsal; exact-Git downstream build. |

## Measured cost

One clean build on this VM, not a budget:

| Stage | Wall time | Peak RSS | Output |
| --- | --- | --- | --- |
| Library `lake build` | 2.5 s | 0.48 GiB | 0.24 MiB, 63 inodes |
| Checker and exporter `lake build` | 22 s | 1.6 GiB | 395 MiB, 429 inodes |
| Build and export through quota stages | 3.4 s | not measured | build about 0.4 MiB and 63 inodes; export 1.7 MiB and 2 inodes |

Quota peaks were sampled every 0.2 s, so they may understate a brief maximum. They
describe today's small corpus and say little about an adversarial or larger build.

## Not established

- Recovery inside the real `verify-tnd` workflow rather than a dedicated test workflow.
- The merge lane.
- Host memory under simultaneous tmpfs use, now on a runner that has swap.
- A server that over-delivers objects despite the filter. GitHub did not, and this
  cannot be forced there; `tests/test_tnd_fetch.py` covers only a local Git server.
- `verify` under real limits. The hosted run used placeholder limits in a test
  repository, and reports remain `development_only`, which the platform rejects.
- Build-stage CPU: the build profile has `--cpus` but no CPU-time ulimit. `command()`
  in `audit/run.py` sets a 900 s wall-clock limit per stage and the named container
  is then force-removed, but that path was read in the code, not observed firing.
  The spin test ran on the parser only.
- A helper that hides its arguments. The recovery scan cannot see one.

One container probe in the harness returned no output on a single earlier run, in a
version that did not capture Docker's error. It has not recurred in six later passes
through that stage, and its cause is unknown.
