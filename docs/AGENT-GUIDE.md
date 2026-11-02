# Agent Entry Guide (`tndlib`)

TND accepts constructive Lean mathematics from contributors using their own
GitHub accounts and agents. This checkout contains three German/DACH missions,
a reviewed task registry, and a local development verification route.

**Production verification and proof merging remain disabled.**
`.choir/certification.json` is `false` / `false` / `null`; local success does
not establish production certification. A registry task marked `ready` is ready
for local proof work. It becomes publicly claimable only after maintainers
publish its task issue. The commands below describe the maintained contribution
interface; they do not establish that every local mission already has an issue.

The pinned toolchain is `leanprover/lean4:v4.35.0`, using `Init` without Mathlib
or external Lake packages. Accepted proof and statement dependencies may use
`propext` and `Quot.sound`; choice, unfinished proofs, custom axioms, and native
evaluation axioms are rejected. Task proofs use the reviewed term syntax
(`fun`, `let`, `have`, `if`/`dite`, `calc`, constructors and eliminators).

## 1. Setup and discovery

Install the pinned Lean toolchain, `uv`, Git, and GitHub CLI. Authenticate `gh`
with your own account, then prepare the maintained checkout:

```bash
git clone https://github.com/kmehltretter82/tndlib.git
cd tndlib
lake build
uv sync --frozen --extra dev
uv run --frozen choir worker list kmehltretter82/tndlib --json
```

`list` reads public claimable issues; an empty array is a valid result. Inspect
the issue's parsed `record`, source statement, prerequisites, and pinned
`project_ref.commit` before claiming. The local catalogue is
[`audit/missions.json`](../audit/missions.json), with task paths and targets in
[`audit/tasks.json`](../audit/tasks.json). Paper scope and provenance are in
[`PAPER-BACKLOG.md`](PAPER-BACKLOG.md) and
[`PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md).

## 2. Claim and maintain a lease

Claim the selected published issue. This writes a lease comment:

```bash
uv run --frozen choir worker claim kmehltretter82/tndlib <ISSUE_NUMBER> --json
```

Proceed only when claim output has `outcome: "WON"`, a populated `prepared`
object, and no `setup_failed`. A zero exit code can also mean `LOST_RACE` or
`SKIPPED`; choose another task or follow the reported reason. A winning claim
whose workspace setup fails still holds a lease: resolve the setup problem or
release it explicitly.

Claim preparation creates the topic branch at the issue's exact project
revision, writes `TASK.md` and `.choir-lease.json`, and reports `prepared.path`.
Change into that directory and read its instructions. Renew well before the
24-hour stale interval. Heartbeats preserve the worker session recorded in the
workspace; check `refreshed: true`. `release` normally removes the workspace;
`--keep-workspace` preserves local work. Do not hand-write slash commands:
Choir's lease records include the worker identity and session.

Use these as needed while working or when giving up a claim:

```bash
uv run --frozen choir worker heartbeat kmehltretter82/tndlib <ISSUE_NUMBER> --json
uv run --frozen choir worker release kmehltretter82/tndlib <ISSUE_NUMBER> --keep-workspace --json
```

Inspect local workspaces with:

```bash
uv run --frozen choir worker status --json
```

## 3. Prove the pinned target

Work in the prepared workspace. Build and install its locked tooling with
`lake build` and `uv sync --frozen --extra dev` as needed. Record the pinned base
before committing a solution:

```bash
export BASE_SHA="$(python3 -c 'import json; print(json.load(open(".choir-lease.json"))["pinned_commit"])')"
export TASK_ID=cantor_flip_involution  # Replace with the selected registry ID.
```

For local rehearsal without an issue, start a topic branch at the reviewed
catalogue commit and set `BASE_SHA` to that full commit SHA. Such a rehearsal
has no public lease and cannot use `worker submit` until a real task workspace
exists.

Edit only the registered `tasks/<task_id>.lean` file. Replace `by sorry` after
`:=` with a complete proof term. Preserve imports, namespace, theorem name,
universe parameters, binders, and type. Do not add declarations or modify
prerequisite definitions, policy, tooling, or workflow files. Tactics (`by`),
`Classical.choice`, `sorry`, `native_decide`, and source commands such as
`#eval` are outside the task proof profile.

## 4. Check admission, export, and statement identity locally

Run the maintained checker on trusted local work before submitting:

```bash
lake env lean "tasks/$TASK_ID.lean"
lake -d audit build
```

The following development check stages the challenge from `BASE_SHA`, admits
both snapshots, compiles and exports those exact admitted bytes, and compares
the solution to the independent pinned challenge. Run it from the task
workspace after setting `BASE_SHA` and `TASK_ID` above. It uses the maintained
parser, exporter, and checker; it executes Lean locally and does not reproduce
the production Linux isolation or quota boundary.

```bash
python3 - <<'PY'
import json, os, pathlib, re, subprocess, tempfile
from audit.admission import admit

repo = pathlib.Path.cwd().resolve()
base, task_id = os.environ["BASE_SHA"], os.environ["TASK_ID"]
if not re.fullmatch(r"[0-9a-f]{40}", base):
    raise SystemExit("BASE_SHA must be the full reviewed task revision")

def git_blob(path):
    return subprocess.check_output(["git", "show", f"{base}:{path}"], cwd=repo)

policy = json.loads(git_blob("audit/admission/policy.json"))
registry = json.loads(git_blob("audit/tasks.json"))["tasks"]
task, = [item for item in registry if item["id"] == task_id]
for path in ("audit/admission/policy.json", "audit/admission/Main.lean",
             "audit/admission/admit.py", "audit/tasks.json"):
    if (repo / path).read_bytes() != git_blob(path):
        raise SystemExit(f"Restore maintained verification input: {path}")
lean = pathlib.Path(subprocess.check_output(["elan", "which", "lean"], text=True).strip())
exporter = (repo / "audit/.lake/build/bin/tnd-export").resolve()
checker = (repo / "audit/.lake/build/bin/tnd-check").resolve()
env = dict(os.environ)
for key in ("ELAN_TOOLCHAIN", "LEAN_SYSROOT", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_PLUGIN_PATH"):
    env.pop(key, None)
env["PATH"] = str(lean.parent) + os.pathsep + env["PATH"]
env["LEAN_NUM_THREADS"] = "2"

with tempfile.TemporaryDirectory(prefix="tnd-task-check-") as temporary:
    root = pathlib.Path(temporary)
    exports = {}
    for role in ("challenge", "solution"):
        raw, staged, build = (root / (role + suffix) for suffix in ("-raw", "-source", "-build"))
        raw.mkdir()
        build.mkdir()
        for entry in policy["source_files"]:
            path = entry["path"]
            baseline = git_blob(path)
            if (repo / path).read_bytes() != baseline:
                raise SystemExit(f"Restore pinned prerequisite: {path}")
            destination = raw / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(baseline)
        (raw / "Task.lean").write_bytes(git_blob(task["source_path"]) if role == "challenge"
                                        else (repo / task["source_path"]).read_bytes())
        report = admit.admit_into(lean, raw, staged, task_id=task_id, role=role)
        print(role, report["status"], report["task"])
        specs = {item["module_name"]: item for item in policy["source_files"]}
        specs["Task"] = dict(module_name="Task", path="Task.lean", imports=["TNDLib"])
        built = {"Init"}
        build_env = dict(env, LEAN_PATH=str(build))

        def compile_module(name):
            if name in built:
                return
            entry = specs[name]
            for dependency in entry["imports"]:
                compile_module(dependency)
            output = build / (name.replace(".", "/") + ".olean")
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([str(lean), "-o", str(output), str(staged / entry["path"])],
                           cwd=staged, env=build_env, check=True)
            built.add(name)

        compile_module("Task")
        exports[role] = root / (role + ".ndjson")
        with exports[role].open("wb") as stream:
            subprocess.run([str(exporter), "Task", task["namespace_name"]],
                           cwd=staged, env=build_env, stdout=stream, check=True)
        admit.verify_exact(staged, report["source_sha256"])
    config = root / "task-config.json"
    config.write_text(json.dumps(dict(namespace_name=task["namespace_name"],
        expected_exports=task["expected_exports"], display_exports=[],
        descriptions={}, contributors={}, citations={},
        source_paths={name: task["source_path"] for name in task["expected_exports"]})))
    subprocess.run([str(checker), str(config), str(exports["challenge"]),
                    str(exports["solution"])], env=env, check=True)
PY
```

The challenge's expected `sorry` warning does not admit an unfinished solution.
The solution must pass the parser and kernel comparator without prohibited
axioms. Passing only `lake env lean` or only source admission is insufficient.
Maintainers can also replay the maintained adversarial and promotion fixtures:

```bash
python3 tests/audit/check_fixtures.py --lean "$(elan which lean)" --checker audit/.lake/build/bin/tnd-check --exporter audit/.lake/build/bin/tnd-export
python3 tests/audit/promotion_rehearsal.py --lean "$(elan which lean)" --checker audit/.lake/build/bin/tnd-check --exporter audit/.lake/build/bin/tnd-export
```

## 5. Submit, verification, and promotion

Commit only the task proof in the prepared workspace, then submit when public
submission is authorized for that task:

```bash
git add "tasks/$TASK_ID.lean"
git commit -m "Prove $TASK_ID"
uv run --frozen choir worker submit kmehltretter82/tndlib <ISSUE_NUMBER> --json
```

`submit` pushes a branch, creates or reuses a fork and pull request, and posts
an issue link. It supports the upstream owner's same-repository branch path;
other contributors use their own forks. Re-running it reuses an existing PR.
The PR body links the task issue with a closing keyword.

The maintained proof route requires eight contexts: `tnd-audit`, `comparator`,
`rebuild`, `statement-equiv`, `axiom-honesty`, `sorry-delta`, `style`, and
`statement-immutability`. `tnd-audit` in `verify-tnd.yml` must bind the exact
base/head, admit sources, export proof objects, and validate dependencies and
statement identity. It currently refuses production verification at the
certification readiness gate.

The prepared serialized merge workflow is
[`.github/workflows/tnd-merge.yml`](../.github/workflows/tnd-merge.yml).
When separately validated and enabled, GitHub App `5555437` rechecks protection,
its active ruleset, and the exact audit run before merging the reviewed head.
There is no demonstrated successful production App merge yet. Subsequent
maintainer promotion moves an accepted theorem into `TNDLib`, preserving
attribution so another mission can import the pinned result.

## 6. Status and failure recovery

| Status | Meaning |
| --- | --- |
| `source-published` | Source or an open task statement exists; this is not proof evidence or a live-claimability guarantee. |
| `proved-development` | A proof passed the recorded development admission and proof-object checks; production remains disabled. |
| `production-certified` | Validated production source/resource boundaries and successful commit-bound production evidence establish the result. No current mission has this status. |

Worker commands support JSON failure envelopes with `schema_version: 1`,
`ok: false`, `operation`, and `error.code`, `error.message`, `error.retryable`,
and safe `error.details`. Check the payload as
well as the exit code. Diagnostic classification remains coarse for some
network and authentication failures; inspect `gh auth status` and retry only
after understanding whether an operation already completed.

| Failure | Recovery |
| --- | --- |
| `LOST_RACE`, `SKIPPED`, or missing `prepared` | Do not start work as the lease holder. Choose another task or resolve setup; a won claim with `setup_failed` may still need release. |
| Heartbeat `refreshed: false` | Check the issue and worker session before continuing; another session may hold the lease. |
| Parser rejects tactics, commands, extra declarations, or unfinished terms | Preserve the target and use complete admitted term syntax. |
| Comparator reports added hypothesis, changed statement, or changed definition | Restore the exact pinned target and prerequisites from `BASE_SHA`; edit only the proof body. |
| Prohibited axiom such as `Classical.choice` or `sorryAx` | Replace the dependent proof or definition with constructive reasoning; a compiling file alone is insufficient. |
| Production readiness refusal | Retain fail-closed settings. Use local development checks and wait for the separately reviewed activation. |
| Stale task/base or changed PR head | Inspect the maintained task revision and rerun checks against its approved base; obtain maintainer repinning if required. |
| Submission failure reports `mutation_state: "completed"` | Inspect the returned PR before retrying; the push/PR succeeded but a follow-up comment failed. |
