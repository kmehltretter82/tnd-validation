# Development source admission prototype

This prototype is **not a certification boundary yet**. The production
`source_binding_validated` flag remains false. It must not be enabled merely
because the examples below pass.

The maintained [semantic elaboration review](SEMANTICS.md) maps every permitted
syntax-kind family to the trusted Lean mechanisms it can reach and records the
mandatory review procedure for a toolchain or policy change.

Run with a trusted Lean 4.35.0 executable:

```sh
python3 audit/admission/admit.py --lean /absolute/path/to/lean --source .
python3 audit/admission/test_admission.py --lean /absolute/path/to/lean
python3 -m unittest discover -s tests/audit -p 'test_admission_limits.py'
```

The parser imports only the trusted distribution's `Init` parser extensions. It
reads candidate files as text and does not import or elaborate their headers or
commands. Its AST-kind list is closed; syntax errors, missing nodes, unknown
constructs, early `exit`/mid-file `import`, modifiers, attributes, extra namespaces,
qualified declaration names, tactics, and metaprogramming commands are rejected.
Only actual EOI at the end of the input completes parsing.

The standalone host parser launcher caps wall-clock time at 90 seconds and combined stdout and
stderr at 1 MiB. On Linux, it sets a hard 60-second CPU limit and 16 GiB virtual
address-space limit; it disables core dumps on all supported hosts. The address
space limit accommodates Lean's virtual reservations and is not an adequate
physical-memory limit. A dedicated cgroup memory limit and filesystem/network
isolation are not provided by this host launcher. macOS runs do not apply Linux-only
CPU/address-space limits and are development evidence only.
The focused limit suite and an initial-corpus admission smoke test passed in
the checksum-verified Lean 4.35.0 Linux ARM64 development image. This is not a
full production-runner or adversarial containment test.

The maintained policy covers all seven library source files and 28 authored
declarations. The root imports must cover every approved source module. Additional
importable files, links, binary contents, and module-name mismatches are rejected.
Files are copied into a fresh staging directory, decoded strictly as UTF-8, and
hashed. `admit_into()` can require equality with the exact Git-blob hash map and
retains the admitted directory for a subsequent read-only build. `verify_exact()`
checks the same file inventory and bytes again. Existing build products and other
repository files are never copied into that directory.

Strings and quotations are excluded, and reflective/effectful or
elaboration-special names including `autoParam`, `optParam`, `outParam`,
`semiOutParam`, `Lean`, `IO`, `String`, and `Char` are excluded separately.
This matters because syntax whitelisting alone does not establish that elaboration
is inert: `autoParam` can evaluate a tactic syntax constant, and syntax data can be
constructed without quotation or string-literal syntax. These restrictions still
need independent semantic review; they are not a proof that every accepted
elaboration path is incapable of side effects.

Task support is being developed for the single maintained `map_exists` task. A
task snapshot uses `Task.lean`, imports only `TNDLib`, declares the exact approved
universes and namespace, and contains only the approved theorem. Candidate proofs
must use the plain-term subset. The challenge's `by sorry` placeholder is allowed
only when its complete bytes match the maintained SHA-256; arbitrary baseline
tactics are not admitted. The library and task sources must be staged together.

## Validation and outstanding work

The 67-case development suite passes on the local Lean 4.35.0 development
assembly. It covers the library and task parser, executable-command and
reflection attempts, exact placeholder and Git-hash checks, changed staged
bytes, and a complete `admit_into()` task run. These tests exercise the
prototype, not the Linux build/export or CI certification path.

The runner now calls `admit_into_container()` for library and task snapshots using hashes
of the Git blobs, builds the staged copy, and checks its source hashes again
after export. For a task it checks that the registry and admission policy agree
on the original path, maps that path to `Task.lean` for compilation, and records
both mappings. Build and export use separate containers; the export container
mounts the build tree read-only. The runner rejects tracked Lean sources outside
`TNDLib`, `tasks`, `tests`, and `audit`, and checks the exact library inventory.
Task checker configuration includes the required empty display-metadata maps.

These connections have driver unit tests, including a real Git snapshot with an
extra root module. A development Git-commit harness accepted a library proof and
a registered task and rejected unimported-module and artifact-overwrite attacks
using image-embedded Linux Lean for parser, build, export, and checking. This did
not exercise the guarded production `verify()` path or host-mounted toolchain.
The security of accepted elaboration constructs, the
reachability of modules in the allowed auxiliary trees, artifact provenance
between stages, the trusted toolchain, and container cleanup still need independent
review and adversarial validation. Independent kernel replay, axiom/type closure,
statement identity, and generated-export inventory checks remain mandatory after
source admission. Keep certification disabled until these requirements are met.

### Docker parser isolation

`sandbox.py` is integrated into the still-disabled runner. It stages checked
source bytes and maintained parser policy,
then runs `Main.lean` in a named, non-root container with a read-only root and
read-only source, parser, policy, and Lean mounts. The container has no network,
Docker socket, credentials, or writable host mounts. It limits CPU, CPU time,
memory and swap, processes, and temporary storage; disables core dumps and
daemon-side log storage; and uses the existing bounded parser launcher for wall
time and combined output. The container must be confirmed absent before a
successful parser result can be returned. The staged bytes are hashed again
afterward.

`python3 -m unittest discover -s tests/audit -p 'test_parser_sandbox.py'`
exercises the argument, cleanup, timeout, error, and byte-recheck contracts.
A local ARM64 Linux Docker smoke used the official Lean release embedded in the
development image: it accepted the corpus, rejected the `#eval` overwrite
attempt, and failed closed under forced output flood, timeout, and low-memory
conditions; the exact named container was absent afterward in each case. The
actual production host-mounted Linux Lean distribution has not been tested with
the integrated runner. Nor does parser isolation prove the semantic safety of accepted
Lean syntax, close the disk-quota and GitHub merge-order blockers, or authorize
changing the production certification flag.

The known source-binding counterexamples are an unimported extra library module
and a root `#eval` that replaces a compiled `.olean` with clean baseline bytes.
The development Git-commit harness rejects their admission mechanisms, but a
complete hostile-source regression through the guarded production Linux runner
is still required.

### Portable Git integration harness

`tests/audit/linux_git_integration.py` creates temporary local Git commits and
exercises the maintained admission, build, export, independent checker, and
registered-task stages. It checks one constructive library change and one task
proof, then verifies that an unimported module and an artifact-overwrite command
are rejected. The temporary commits are deleted with the test workspace. The
harness requires the project readiness flag to be `false`; it never calls the
guarded `verify()` entry point or issues a certificate.

On an unprivileged Linux host with a trusted Lean 4.35.0 installation, built
Linux checker/exporter binaries, a Docker-visible working directory, and Docker's
built-in default seccomp profile, run from the repository root:

```sh
python3 tests/audit/linux_git_integration.py \
  --lean-root /absolute/path/to/lean-4.35.0 \
  --checker /absolute/path/to/tnd-check \
  --exporter /absolute/path/to/tnd-export \
  --work-dir /absolute/path/to/docker-visible-workspace
```

The optional `--image` must match the runner's exact maintained digest pin.
For development on a non-Linux host, an explicit
`--embedded-image sha256:IMAGE_ID` instead uses Lean inside that locally present,
immutable image and runs the Linux checker in a container. In this mode omit
`--lean-root`, supply compatible Linux checker/exporter binaries, and ensure the
selected image contains the trusted Lean 4.35.0 distribution. Embedded mode
changes the toolchain mount arrangement and is not production-path validation.
Neither mode relaxes or mocks the daemon's default-seccomp requirement. The
local Docker Desktop daemon currently reports `profile=unconfined`, so the
current gate rejects a run before creating fixtures; this is an expected failure,
not a passing test or certification result.
