# Proposed resource boundary for source admission and proof builds

**Experimental host-mount implementation; production-wired but not validated.**
`resource_boundary.py` provides a preliminary lifecycle for private build and
export tmpfs mounts with limits, mount identity/flag checks, and nonrecursive
cleanup. Its tests use a fake host and never perform a real mount. It does not
start or contain the parser or candidate containers, verify Docker's mount
namespace, supervise abrupt host failure, or provide complete CI integration.
`audit/run.py` now routes its production build/export calls through
`bounded_build_export`, which owns one fresh boundary, rechecks both mounts
before every container, confirms removal of each named container, copies the
bounded export, closes the mounts, and only then publishes the checked copy.
The older unbounded `build_export` function is retained only for development
integration harnesses and is no longer called by `verify`. The production route
requires both validation flags, an exact limit policy, and `--quota-parent`;
those are currently absent or false, so it fails before any mount operation.
No numeric production budget is selected. The workflow supplies its trusted
`RUNNER_TEMP` as the prospective parent, but the helper must still validate it
as an existing canonical safe directory. This must not be treated as a validated
security boundary or certification. The standalone helper still requires its caller to confirm every
container has stopped before `close()`; the production wrapper performs that
check for its own containers. Unmounting a tmpfs
discards its contents, including any nonempty build or export files. After a
successful unmount, the helper's `rmdir` removes only the empty underlying
mountpoint; it does not recursively delete the contents while the filesystem is
mounted. The helper checks mount identity before unmounting, even if a container
has changed mount-root permissions or exhausted a quota, and refuses teardown if
the recorded mount has been replaced or contains unexpected nested mounts.
An abnormal privileged mount or unmount helper exit, interruption, or timeout quarantines
the entire private path and prevents automatic unmount or removal: killing a
process group does not establish that every privileged descendant has stopped,
and a late helper could otherwise mount at a removed or reused pathname. A
separate supervisor must establish helper termination and safely reconcile any
mounts. `resource_recovery.py` is that step; see "Recovery" below. Even a
successful helper exit does not prove that a detached descendant has stopped, so
recovery rechecks before touching anything. The helper itself checks that path ancestors are owned by
root or the invoking user and not writable by unrelated users (except trusted
sticky directories), but pathname checks are not atomic with privileged mount
operations and do not protect against same-UID or privileged actors. Native
Linux testing and a reviewed race-resistant setup remain required.

`resource_stages.py` owns one-shot quota stages for a build/export sequence or
Choir comparator run, checks both mount identities immediately before each
container launch and again after comparator exit, and requires confirmed removal
of each named container before closing the mounts. If container absence cannot
be confirmed, it leaves the mounts in place for independent recovery. The
production comparator now injects its Docker argument factory into this helper,
avoiding a module import cycle, and classifies output only after successful
unmount. Its entry point requires the same false-by-default validation flags,
exact limits, and trusted quota parent as the audit runner. Tests mock all mount
and Docker operations; native Linux enforcement remains untested. The separate
development CLI (`python3 -m audit.resource_stages --help`) requires an existing
canonical scratch parent, explicit byte and inode limits, and local source/tool
paths. The helper validates the parent and ancestors; the
CLI creates a build/export output only after successful container and mount
cleanup, and refuses to overwrite an existing output. Comparator output is
emitted only after cleanup. This is a stage experiment: it does not perform Git
source admission or certify proofs. It does
not establish that the daemon sees the same mount namespace, handle host crashes,
or supervise privileged helper descendants. A successful mock test is not
evidence of filesystem quota enforcement. Do not use it for certification.
Production certification remains disabled. Neither bounded production route has
been exercised on native Linux; the explicit development-only builder and
comparator helpers still permit unbounded writable bind mounts for focused tests.
The development parser container has limits, but its enforcement has not been
validated on the target Linux runner. A successful proof-object check does not
establish that untrusted elaboration is harmless.

## Goal and scope

Bound untrusted parsing, compilation, and export in the supported Linux CI
environment. The design assumes a fresh GitHub-hosted Ubuntu virtual machine
with a local Linux Docker daemon; it does not assert equivalent behavior on a
self-hosted runner, a remote daemon, nested Docker, or macOS Docker Desktop.
The current GitHub documentation states that its Linux VMs offer passwordless
`sudo`, while `ubuntu-slim` cannot mount filesystems or run Docker-in-Docker.
The workflow must use a supported VM and verify its actual facilities rather
than infer them from the label. [GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

All privileged setup and teardown runs in maintained trusted workflow code on
the host. Candidate source and Lean code must never receive host root, sudo,
the Docker socket, a network, or credentials. This resource boundary is an
additional control: it does not prove parser semantics, source-to-export
identity, kernel correctness, statement identity, or merge enforcement.

## Candidate design

1. A trusted wrapper creates a private, randomly named directory outside the
   checkout with mode `0700`, owned by the runner. It records its identity and
   creates empty build and export mountpoints without following symlinks. The
   wrapper mounts separate host tmpfs filesystems using `sudo -n`, each with
   explicit nonzero `size` and `nr_inodes`, plus `nodev,nosuid,noexec`.
   Mount root ownership is set to the unprivileged runner UID/GID and mode
   `0700`. Only the wrapper can choose paths, limits, mount options, or mount
   operations; they must not come from candidate files, issue text, PR
   metadata, or workflow inputs controlled by a contributor.
2. The ordinary unprivileged driver receives those exact directories from the
   trusted wrapper. Before each stage it must verify, without following links,
   the parent and owner, exact mountpoints and mount IDs in its mount namespace,
   filesystem type, mount flags, actual capacity and inode limits. It must also
   reject unexpected nested mounts and a Docker daemon that cannot see the same
   host mounts. Missing, unsupported, inconsistent, oversized, or uninspectable
   limits cause rejection; a user-supplied path or `statvfs` alone is not proof
   that it is a dedicated mount.
3. A separate unprivileged, network-free parser container receives candidate
   text and maintained parser/policy and Lean files as read-only mounts. It has
   no writable host bind mounts. Cap its memory and total memory-plus-swap,
   CPU, process count, elapsed time, temporary storage, `/dev/shm`, and combined
   stdout/stderr; accept only the expected JSON and successful exit. Apply the
   existing source inventory and Git-blob hash checks and retain the staged
   exact bytes for later compilation. Named-container cleanup must run after
   success, failure, timeout, and output overflow. Its failure is a rejection.
4. The build container receives the admitted source and trusted toolchain
   read-only and the dedicated build mount read-write. After its confirmed
   termination, the export container receives that same build mount read-only,
   its own bounded output mount read-write, and the trusted exporter read-only.
   Both remain non-root with all capabilities dropped, no-new-privileges, no
   network, and no Docker socket or credentials. Reject cleanup failure, and
   check source hashes and output-file type/size after both stages. The export
   filesystem's total limit must not be confused with the existing per-file
   output limit.
5. Once all candidate containers are confirmed stopped, the trusted wrapper
   unmounts in reverse order, verifies the recorded mount IDs are detached, and
   removes only its verified private directory. An unmount, daemon, or cleanup
   failure is not a successful verification. Never use lazy unmount as evidence
   that resources were reclaimed.

The actual size and inode budgets are **not selected yet**. Measure the pinned
Lean version, corpus, accepted task, generated helpers, exporter, and checker on
the supported runner; set reviewed limits with headroom. A quota overflow must
produce a rejection. Kernel tmpfs `size` limits allocated bytes and `nr_inodes`
limits inodes, and tmpfs may use swap unless disabled; `noswap` availability is
kernel-dependent and must be checked. Account for all simultaneous tmpfs mounts,
container limits, page cache, Docker overhead, and the host's memory and swap.
[Linux tmpfs documentation](https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html).

As an alternative, trusted setup can preallocate bounded loop-backed filesystem
images for build and output, then mount and bind them with the same permissions
and read-only stage separation. This uses disk rather than holding the build in
tmpfs but adds filesystem formatting, loop-device ownership, mount verification,
free-space reservation, and teardown complexity. A sparse image is not a host disk
reservation. Either approach requires an implementation review and the tests
below; Docker writable-layer storage limits do not bound writable host bind
mounts. [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/),
[Docker storage-driver limits](https://docs.docker.com/reference/cli/dockerd/).

## Interrupted jobs and host trust

`finally`, `atexit`, and shell traps do not run after all host failures or
`SIGKILL`. Add an independent trusted `if: always()` cleanup step and a
supervisor/watchdog that tracks the exact mounts, containers, and lease, with
tested cleanup on cancellation and interrupted processes. A hosted VM's
disposal is the final recovery layer after hard runner loss, not a successful
audit result. A self-hosted runner needs persistent stale-lease recovery,
reconciliation on restart, and protection against cleaning a live job; it is
unsupported until independently designed and tested. Never sweep unrelated
mounts, Docker resources, or directories.

## Recovery

Before its first mount, the boundary atomically writes `<root>.lease` beside the
private root, naming that root's identity, the owner's PID and kernel start time,
and each container before it starts. Leases live outside the mounts, so candidate
containers cannot reach them. An `if: always()` step in every quota-using workflow
runs `python3 -m audit.resource_recovery --parent "$RUNNER_TEMP" --terminate-owner`,
standard library only, and a job whose recovery refuses fails.

It handles only leased resources, in this order, and refuses (retaining everything
for host disposal) on any mismatch: the lease is a private regular file naming a
direct child of the parent with the recorded identity; the owner has exited within a
bounded wait or, with `--terminate-owner`, was killed by its exact PID and start time;
every named container is removed; no process argument names the root after a bounded
wait; the containers are confirmed absent again; each mountpoint holds at most one tmpfs with the required flags and nothing
nested. Only then does it unmount, confirm detachment, and remove the empty paths.

The process scan is evidence, not proof. It sees every process's arguments only
without `hidepid`, and a descendant that rewrites its arguments or a helper that
started and stopped between scans is not distinguished. The argument holds because
only the dead owner can launch a helper for that root. Host disposal remains the
final layer. Only a hosted runner's single-job VM may use `--terminate-owner`.
`tests/audit/linux_boundary_smoke.py` exercises this with real mounts, and a real run
cancellation first exposed the need for the owner handling and this ordering.

## Acceptance tests before enabling certification

- On the actual pinned Linux CI environment, record runner kernel, Docker and
  cgroup versions, filesystem/mount metadata, UID/GID, measured peak memory,
  inode counts, build/output usage, and the reviewed limits. Build the library
  and an approved task, export in the separate read-only stage, independently
  replay and inspect statements/axioms; verify exact Git source hashes.
- Demonstrate that candidate attempts to exceed build and export byte limits
  and inode limits fail without exhausting host disk or memory. Exercise sparse
  files, many small or zero-length files, directory creation, and large output.
  Verify intended limits also apply with the selected Docker daemon and mount
  namespace. Test `/tmp` and `/dev/shm` separately.
- Exercise parser input causing excessive nesting, malformed syntax, CPU use,
  memory use, output, and process creation. Confirm bounded termination, no
  candidate-controlled execution on the host, and no success after timeout,
  kill, OOM, malformed output, or cleanup failure.
- Verify the export container cannot write to build artifacts, admitted source,
  trusted parser, checker, or Lean toolchain and cannot access the network,
  Docker socket, or credentials. Re-run the known `.olean` replacement and
  unimported-module attacks through the full Git-to-audit path.
- Test bad or replaced quota paths, mount IDs, symlinks, extra nested mounts,
  incorrect owner/mode, unmounted or oversized filesystems, unsupported mount
  options, read-only mount failure, and mismatched source hashes. All must fail
  before a candidate can write outside its allocated scratch space.
- Exercise normal completion, build/export error, quota exhaustion, output
  overflow, timeout, container/client failure, cancellation, supervisor crash,
  and runner termination. Confirm no certificate is emitted and only the exact
  task-owned resources are cleaned. Validate recovery independently of in-process
  cleanup and verify no live neighboring task is affected.
- Independently review the allowed Lean syntax/elaboration semantics and test
  the actual GitHub merge identity, protected branch, trusted CI workflow, and
  cross-repository evidence pipeline. Resource containment alone does not close
  the separate preflight-to-merge rerun race documented in
  [TND's Choir integration](../.choir/TND-INTEGRATION.md).
