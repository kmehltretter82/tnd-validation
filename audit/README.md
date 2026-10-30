# Constructive proof verification

**Production certification is disabled.**
`.choir/certification.json` records both `source_binding_validated: false` and
`resource_boundary_validated: false`, with no selected resource limits. The
trusted workflow, merge readiness gate, and `run.py` refuse certification unless
both flags are exactly true and an exact bounded-filesystem policy is present.
Current checks establish properties of exported proof objects; they do not yet
establish that arbitrary contributor source was faithfully represented or safely
contained on the target host. Both flags must remain false until independent
review and hostile-source tests establish those boundaries.

The trusted audit tools are a separate Lake project. They are development tools;
downstream users of `tndlib` do not import Comparator or lean4export.

`Check.lean` reads NDJSON proof objects, compares approved theorem statements and
their complete definition dependencies using pinned Comparator code, computes
axiom dependencies from raw types and bodies, and independently replays the
solution environment through Lean's kernel. It never loads candidate `.olean`
files, runs candidate elaboration code, or trusts `#print axioms` output. The
only permitted axioms are `propext` and `Quot.sound`; their declarations are also
compared with the trusted reference. Definitions are immutable: this version
does not accept comparator definition holes.

`ExportPublic.lean` enumerates every non-internal declaration under `TNDLib`,
including generated matcher declarations, and exports their dependencies. The
maintainer-owned `exports.json` fixes the exact inventory, source-file mapping,
and displayed subset. It also supplies the explanation, contributor attribution,
and source/provenance citation shown for each displayed result. These metadata
keys must exactly match the displayed inventory and may not be blank. They are
maintainer-reviewed descriptions, not a mathematical claim established by the
kernel; a promotion or adaptation must update them with accurate provenance.
The report records the inventory's SHA-256 digest. Both reference and solution
inventories must match it.
Generated helpers are audited but are omitted from the public result list.
Changes that introduce or remove public declarations need explicit inventory
review; a proof submission cannot approve its own inventory or definitions.

The guarantee concerns the approved named proof objects and their checked
statements. Arbitrary Lean metaprogramming cannot provide trusted evidence of
every other declaration it might create, omit from an export, or otherwise
hide. The former build/export design allowed contributor elaboration to replace a
writable `.olean` with an innocent object; root-only export could also miss a
module not imported by `TNDLib.lean`. Admission rejects the demonstrated
mechanisms and the runner now separates build and export, but syntax restrictions
alone do not prove accepted elaboration has no effects. The exact relationship
between all publishable source, compiled artifacts, and exported proof objects
still requires a complete hostile-source Linux test and independent semantic
review. Local reports are development evidence, not certificates. Human review
also remains necessary for intended mathematical meaning and APIs.

The merge gate has a separate release blocker: a new or rerun verification
can start after the local preflight and before GitHub merges, while an older
`tnd-audit` commit status remains green. Head-SHA pinning and strict branch
protection have not been shown to bind the merge atomically to the latest
exact workflow attempt. A pending status posted by a job alone does not cover
queued/cancelled starts or out-of-order reporter completions. See
[TND's Choir integration](../.choir/TND-INTEGRATION.md) for the required live
acceptance tests; certification and proof merges remain disabled.

Build the tools from the trusted base checkout:

```sh
cd audit
lake build
```

The production runner requires Linux, Docker, an unprivileged account and the
exact Lean 4.35.0 installation. Preload the digest-pinned image in `run.py`, then
run from a clean base checkout with both Git commits locally available:

```sh
python3 audit/run.py --repo . --base BASE_SHA --head HEAD_SHA \
  --quota-parent /canonical/trusted/scratch \
  --output audit/output/audit.json
```

Before any proof workflow fetches its candidate commit, the maintained
`gate.verify.tnd_fetch` helper checks that GitHub's current PR number, open
state, main base, base SHA and head SHA match the trusted event. The preceding
trusted checkout acquires only that exact base SHA at depth one, with tags
disabled; it does not fetch all branch history before admission. The helper
accepts at most eight proof-surface files and 2,000 changed lines, then fetches
the exact head SHA with `--depth=1`, no tags or submodules, and
`blob:limit=262145`. Automatic lazy object fetching remains disabled for every
later workflow step. The fetched tree must exactly match the API file list;
every non-removed source must be an ordinary `100644` blob already present
locally, at most 256 KiB, and all candidate source blobs together are limited
to 1 MiB. A local Git-server test covers the filter boundary byte-for-byte.

This is pre-admission **risk reduction, not a filesystem quota**. It relies on
the Git server honoring protocol-v2 object filtering (an explicit unsupported-
filter warning is fatal), and commit/tree negotiation plus the Git object store
still use ordinary host storage. It cannot bound a malicious server that sends
objects contrary to the filter before Git rejects them. Native GitHub-runner
tests must measure the pack/object footprint and failure behavior. The same
limits give the comparator a concrete bound on candidate-controlled Lean bytes
before it materializes its ordinary temporary workspace; trusted base files are
separate. Certification remains disabled until the actual fetch, workspace,
build quota and cleanup chain are validated together.

The runner checks each commit's published Lake configuration, manifest, and
Lean pin against a maintained exact-byte policy. Alternate Lake configuration,
tracked build artifacts, and unapproved Lean module roots are rejected. A
deliberate package change requires a reviewed policy update; the synthetic
sandbox package must not silently differ from the published package.

The runner extracts regular tracked source blobs from each Git commit, rejects
unapproved Lean source roots, and admits a fresh staged copy against their exact
hashes using the maintained policy. It supplies its own dependency-free Lake
configuration and rechecks source hashes after export. Each reference and
solution build runs in its own network-disabled container with read-only source
and toolchain and a writable build directory. After that container has stopped,
an export container reads the build directory read-only and writes only its
output. The containers have no capabilities, credentials, or Docker socket and
have limited memory, processes, and CPU. The checker now runs in a separate
developmental container with read-only inputs and no writable host mounts.
Time, console output, and export-file size are bounded. After each stage, the
runner attempts to remove the named container and requires a successful Docker
query showing it is absent before continuing. Cleanup behavior and the full
chain still require validation on a clean Linux installation. A Linux ARM64
development smoke test exercised the separate stages and replayed the library
export against itself using the official Lean sysroot embedded in its test image.
It did not exercise the production host-mounted toolchain, Git admission, or a
changed submission, so it is not an end-to-end verification of a commit.

A separate development harness exercised actual temporary Git commits through
`admitted_snapshot`, isolated Linux build/export, independent checker replay,
and `verify_tasks`. It accepted a constructive library change and a registered
task proof, and rejected an extra unimported library module and an artifact
overwrite command. Admission, build, export, and checking all ran using Lean
embedded in the development Linux image. The harness did not call
the guarded production `verify()` function, use the production host-mounted
Linux toolchain, or establish the safety of every admitted Lean construct.
The portable [Git integration harness](../tests/audit/linux_git_integration.py)
and its prerequisites are documented in the [admission guide](admission/README.md).
It preserves the daemon's built-in seccomp gate; the current local daemon reports
`profile=unconfined`, so a rerun of that harness correctly refuses to proceed.

On the development Mac, a full nested Linux `verify()` test is not yet
available. The test image has neither the Docker CLI nor `elan`; its `/opt/lean`
is inside the container and is not a host path the Docker daemon can bind into
the build containers. The mounted Docker socket was visible as `root:root` mode
`0755`, but an unprivileged Linux user received `EACCES` when connecting. A
faithful test needs a Linux Docker client and toolchain manager, a host-visible
Lean installation and matching temporary paths, and a safe non-root socket
configuration. Most importantly, the real production guard currently refuses
`verify()` before these stages. Do not change or bypass that guard to claim a
certification result from a development test.

The local Docker Desktop daemon reported an unconfined seccomp profile during
this development test. Its results therefore do not validate the security of
Docker's default seccomp profile or establish the isolation settings of the
eventual GitHub-hosted runner.

Before each parser, build, export, and comparator container starts, the driver
requires the exact maintained Ubuntu image digest, queries Docker's security
options, and accepts only one unambiguous
`name=seccomp,profile=builtin` entry. This matches the built-in profile shown in
[Docker's system-info documentation](https://docs.docker.com/reference/cli/docker/system/info/).
Missing, malformed, unconfined, custom, duplicate, or unrecognized profile
reports fail closed. The daemon must be trusted: this metadata is not kernel
attestation, does not pin the profile contents, and can change between the
query and container creation. Validate actual enforcement on the target Linux
runner before enabling certification. Containers also disable image pulls and
daemon logging, bound shared memory, and set the swap limit equal to the memory
limit. These controls do not impose a quota on writable bind mounts.

The 128 MiB export-file limit alone is checked **after** a container exits and
does not bound disk writes. The production `verify` path now refuses its older
unbounded builder and routes build/export through fresh byte-and-inode-limited
tmpfs mounts, with identity checks before every launch, confirmed named-container
removal, teardown before publishing the checked copy, and an explicit trusted
`--quota-parent`. This route remains disabled: its mounts, Docker-daemon
visibility, limits, failure recovery, and supervisor behavior have only mock
coverage, not target-Linux validation. The production Choir comparator now uses
the same validated policy and quota-owned build storage and waits for cleanup and
unmount before classifying its output; its validation flag is likewise false.
The development Git harness and explicit development-only comparator helper still
use unbounded writable bind mounts. Before enabling certification, validate all
boundaries and oversized build/export attempts without consuming the runner's
remaining host space.

`checker_sandbox.py` is integrated into the still-disabled runner for both
library and task proof-object checks. This boundary remains **development-only**:
it requires the Docker built-in seccomp profile, runs the maintained checker in a
named unprivileged container, mounts its configuration, two exports, binary,
and toolchain read-only, and gives it no network, Docker socket, or writable
host mounts. It caps memory and swap at 3 GiB, CPU, processes, temporary
storage, wall time and output, and requires confirmed container removal before
using the result. Its return value explicitly says `development_only`. Tests in
`tests/audit/test_checker_sandbox.py` exercise this contract with mocks; they do
not establish actual daemon seccomp enforcement, resource limits, or kernel
replay against hostile inputs. A full Linux end-to-end test, including large,
malformed, and expansion-heavy exports, and independent review are required
before enabling certification. The Git harness was adapted to the new checker
boundary but has not been rerun with it.

Source admission invokes the trusted Lean parser in a separate named Docker
container with read-only source, policy, parser, and toolchain; no network or
writable host mounts; and CPU, memory/swap, process, time and output limits.
The runner confirms container removal before using the parser result. A local
development smoke exercised rejection, output flooding, timeout, and low-memory
failure; the production host-mounted Linux toolchain and complete guarded path
still need validation. The syntax-depth check runs after parsing and is not a
substitute for process limits. The partially implemented and guarded
[resource-boundary design](RESOURCE-BOUNDARY-DESIGN.md) specifies a candidate
Linux containment approach and the tests required before certification.

Reports bind the base and head commits, source-file hashes, proof-export hashes,
toolchain, verifier dependencies, binary hashes, axiom results and statements.
Any eventual verified report also records the bounded-filesystem implementation
and exact byte/inode policy used for its build and export mounts.
The intended production status is `verified`, but the current mandatory
certification guard prevents it from being issued.
macOS verification stops without issuing that status. Running the checker
directly can validate proof objects for development, but it does not establish
that their source was built in the production isolation boundary.

## Open tasks and promotion

`tasks.json` is a maintainer-approved registry. The current admission policy
supports the registered `map_exists` task only. A task file imports `TNDLib` and
declares its approved statement in `TNDTask`; it is excluded from library
imports and may initially contain `sorry`. A proof PR fills that file. Changed
task files are independently checked against the base statement in a separate
temporary module. Unregistered task edits fail. Results appear under `tasks`
with status `verified-task-proof`, not in the certified library result list.

A maintainer promotes an accepted task by adding its proof under `TNDLib`,
updating the approved export inventory and source mapping, and running the full
library audit. Task completion by itself does not publish a library declaration.
Only tasks whose dependencies are already certified can pass the task proof
audit; imported `sorry` remains prohibited.

`tests/audit/promotion_rehearsal.py` exercises that lifecycle without changing
the published corpus. It creates three temporary local Git commits (challenge,
accepted task, and promotion), admits the exact constructive solution, checks it
against the approved challenge, relocates it into a temporary
`TNDLib.Existential` module, updates copies of the source policy, export inventory,
source mapping, and display metadata, then clones and fully exports/checks the
exact promoted commit. The script requires certification to remain disabled and
emits only `development-only-task-to-promotion-rehearsal` evidence. It never uses
the production runner, Docker, sudo, GitHub, or the real library as an edit target.

```sh
python3 tests/audit/promotion_rehearsal.py \
  --lean /absolute/path/to/lean-4.35.0 \
  --checker audit/.lake/build/bin/tnd-check \
  --exporter audit/.lake/build/bin/tnd-export
```

## Verification tests

```sh
uv run --frozen --extra dev python -m pytest -q tests/audit
python3 audit/admission/test_admission.py --lean "$(elan which lean)"
python3 tests/audit/check_fixtures.py \
  --lean "$(elan which lean)" \
  --checker audit/.lake/build/bin/tnd-check \
  --exporter audit/.lake/build/bin/tnd-export
```

Fixtures test constructive acceptance, direct/indirect choice, imported sorry,
custom axioms, native evaluation, changed statements/definitions, added
hypotheses, unexpected exports, choice in a statement, and a forged proof
object rejected by independent kernel replay. These handwritten fixtures run
locally without the production sandbox and must never be replaced with
untrusted contributor input.

The checker reuses Apache-2.0 Comparator/lean4export code at the revisions in
`lake-manifest.json`. The copied primitive list and kernel replay procedure in
`Check.lean` retain attribution to Lean FRO and Henrik Böving.
