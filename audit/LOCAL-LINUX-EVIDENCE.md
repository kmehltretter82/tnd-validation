# Local native-Linux evidence, 2026-10-30

**Development evidence only.** This came from an expendable QEMU virtual machine,
not the intended GitHub-hosted `ubuntu-24.04` x86-64 runner. It selects no budget,
changes no certification flag, and must not be cited as production validation.
Everything below must be repeated on the target runner.

Environment: Ubuntu 24.04.5, Linux 6.8.0-147-generic, aarch64, 3 vCPU, 3 GiB RAM, no
swap, Docker 29.1.3 with overlayfs, cgroup v2, and its built-in seccomp profile.
Lean 4.35.0 came from `audit/install_lean.py`.

## Observed

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

- Anything about x86-64 or the hosted runner, its mount namespace, kernel, or sudo.
- `RUNNER_TEMP` passing the parent-chain check; a group-writable parent is refused.
- Real Actions behavior: cancellation, the `if: always()` step, and the merge lane.
- Filtered-fetch or server over-delivery.
- `audit/run.py verify` end to end. Its guard correctly refuses while the flags are
  false, and it must not be bypassed to obtain this result.
- Host memory under simultaneous tmpfs use. tmpfs may swap, and this VM had none.
- Build-stage CPU: the build profile has `--cpus` but no CPU-time ulimit. `command()`
  in `audit/run.py` sets a 900 s wall-clock limit per stage and the named container
  is then force-removed, but that path was read in the code, not observed firing.
  The spin test ran on the parser only.
- A helper that hides its arguments. The recovery scan cannot see one.

One container probe in the harness returned no output on a single earlier run, in a
version that did not capture Docker's error. It has not recurred in six later passes
through that stage, and its cause is unknown.
