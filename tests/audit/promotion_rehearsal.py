#!/usr/bin/env python3
"""Local-only rehearsal of task acceptance and maintainer promotion.

This script operates on trusted repository fixtures, creates a temporary Git
repository, and emits development evidence only. It never calls the production
runner, Docker, sudo, GitHub, or a readiness override.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PROMOTED_MODULE = "TNDLib.Existential"
PROMOTED_PATH = "TNDLib/Existential.lean"
PROMOTED_NAMESPACE = "TNDLib.Existential"
PROMOTED_DECLARATION = "TNDLib.Existential.mapExists"
DESCRIPTION = "Transports an explicit existential witness through a function."
CONTRIBUTOR = "TND task-to-promotion rehearsal"
CITATION = "Promoted from the approved map_exists task fixture"
MAX_TOOL_OUTPUT = 128 * 1024 * 1024


def _command(
    args: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if len(result.stdout) + len(result.stderr) > MAX_TOOL_OUTPUT:
        raise ValueError("trusted rehearsal tool output exceeded 128 MiB")
    if result.returncode:
        raise ValueError(
            f"trusted rehearsal command failed: {args!r}\n"
            + (result.stdout + result.stderr)[-8000:].decode("utf-8", errors="replace")
        )
    return result


def _git(repo: Path, *args: str) -> bytes:
    return _command(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args], cwd=repo
    ).stdout


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_development_only(repo: Path) -> None:
    policy = json.loads((repo / ".choir/certification.json").read_text())
    if (
        not isinstance(policy.get("schema_version"), int)
        or isinstance(policy.get("schema_version"), bool)
        or policy.get("schema_version") != 1
        or policy.get("source_binding_validated") is not False
        or policy.get("resource_boundary_validated") is not False
        or policy.get("resource_limits") is not None
    ):
        raise ValueError("promotion rehearsal requires every certification boundary disabled")


def copy_baseline(project: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError("temporary repository destination must not exist")
    destination.mkdir()
    for directory in ("TNDLib", "tasks"):
        shutil.copytree(project / directory, destination / directory)
    (destination / ".choir").mkdir()
    # The rehearsal needs only the public readiness policy. Never copy local
    # orchestrator state or credentials into its temporary Git history.
    shutil.copy2(
        project / ".choir/certification.json",
        destination / ".choir/certification.json",
    )
    for name in ("TNDLib.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
        shutil.copy2(project / name, destination / name)
    (destination / "audit/admission").mkdir(parents=True)
    for name in ("exports.json", "tasks.json"):
        shutil.copy2(project / "audit" / name, destination / "audit" / name)
    shutil.copy2(
        project / "audit/admission/policy.json",
        destination / "audit/admission/policy.json",
    )
    require_development_only(destination)


def commit(repo: Path, message: str) -> str:
    _git(repo, "add", "--all")
    _command(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=TND rehearsal",
            "-c",
            "user.email=rehearsal@example.invalid",
            "-C",
            str(repo),
            "commit",
            "--quiet",
            "-m",
            message,
        ],
        cwd=repo,
    )
    if _git(repo, "status", "--porcelain"):
        raise ValueError("temporary Git commit is not clean")
    revision = _git(repo, "rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("temporary Git commit did not produce a full SHA")
    return revision


def initialize_repository(repo: Path) -> str:
    _command(["git", "init", "--quiet", str(repo)], cwd=repo.parent)
    return commit(repo, "trusted task challenge baseline")


def accept_solution(repo: Path, trusted_solution: bytes) -> str:
    task = repo / "tasks/map_exists.lean"
    if task.read_bytes() == trusted_solution:
        raise ValueError("challenge unexpectedly already contains the solution")
    task.write_bytes(trusted_solution)
    revision = commit(repo, "accept constructive map_exists task proof")
    changed = _git(repo, "diff", "--name-only", "HEAD^", "HEAD").decode().splitlines()
    if changed != ["tasks/map_exists.lean"]:
        raise ValueError("accepted-task commit changed files outside the approved task")
    return revision


def promoted_source(solution: bytes, trusted_solution: bytes) -> bytes:
    """Relocate the exact maintained solution into its library namespace."""
    if solution != trusted_solution:
        raise ValueError("accepted task bytes differ from the trusted constructive solution")
    text = solution.decode("utf-8", errors="strict")
    replacements = (
        ("import TNDLib\n", "import Init\n"),
        ("namespace TNDTask\n", f"namespace {PROMOTED_NAMESPACE}\n"),
        ("end TNDTask\n", f"end {PROMOTED_NAMESPACE}\n"),
    )
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError("task solution does not have the expected promotable structure")
        text = text.replace(old, new, 1)
    if "TNDTask" in text or "sorry" in text or "Classical" in text:
        raise ValueError(
            "promoted proof contains an unexpected task, placeholder, or classical name"
        )
    return text.encode()


def promote(repo: Path, trusted_solution: bytes) -> str:
    require_development_only(repo)
    task_solution = (repo / "tasks/map_exists.lean").read_bytes()
    source = promoted_source(task_solution, trusted_solution)
    promoted = repo / PROMOTED_PATH
    if promoted.exists():
        raise ValueError("promotion module already exists")
    promoted.write_bytes(source)

    root_path = repo / "TNDLib.lean"
    root = root_path.read_text()
    if f"import {PROMOTED_MODULE}\n" in root:
        raise ValueError("promotion module is already imported")
    marker = "\n/-! The initial standalone constructive TNDLib corpus. -/"
    if root.count(marker) != 1:
        raise ValueError("library root does not have the expected import boundary")
    root_path.write_text(root.replace(marker, f"\nimport {PROMOTED_MODULE}" + marker, 1))

    policy_path = repo / "audit/admission/policy.json"
    policy = json.loads(policy_path.read_text())
    root_spec = next(entry for entry in policy["source_files"] if entry["path"] == "TNDLib.lean")
    if PROMOTED_MODULE in root_spec["imports"]:
        raise ValueError("promotion module already exists in admission policy")
    root_spec["imports"].append(PROMOTED_MODULE)
    policy["source_files"].append(
        {
            "path": PROMOTED_PATH,
            "module_name": PROMOTED_MODULE,
            "namespace_name": PROMOTED_NAMESPACE,
            "imports": ["Init"],
            "declarations": [PROMOTED_DECLARATION],
            "universes": ["u", "v"],
        }
    )
    _write_json(policy_path, policy)

    exports_path = repo / "audit/exports.json"
    exports = json.loads(exports_path.read_text())
    if PROMOTED_DECLARATION in exports["expected_exports"]:
        raise ValueError("promoted declaration is already exported")
    exports["expected_exports"].append(PROMOTED_DECLARATION)
    exports["expected_exports"].sort()
    exports["source_paths"][PROMOTED_DECLARATION] = PROMOTED_PATH
    exports["display_exports"].append(PROMOTED_DECLARATION)
    exports["display_exports"].sort()
    exports["descriptions"][PROMOTED_DECLARATION] = DESCRIPTION
    exports["contributors"][PROMOTED_DECLARATION] = CONTRIBUTOR
    exports["citations"][PROMOTED_DECLARATION] = CITATION
    for field in ("source_paths", "descriptions", "contributors", "citations"):
        exports[field] = dict(sorted(exports[field].items()))
    _write_json(exports_path, exports)

    validate_promoted_tree(repo)
    revision = commit(repo, "promote map_exists into temporary TNDLib corpus")
    changed = set(_git(repo, "diff", "--name-only", "HEAD^", "HEAD").decode().splitlines())
    expected = {
        "TNDLib.lean",
        PROMOTED_PATH,
        "audit/admission/policy.json",
        "audit/exports.json",
    }
    if changed != expected:
        raise ValueError(f"promotion commit changed unexpected files: {sorted(changed ^ expected)}")
    return revision


def validate_promoted_tree(repo: Path) -> None:
    require_development_only(repo)
    policy = json.loads((repo / "audit/admission/policy.json").read_text())
    specs = policy["source_files"]
    paths = [entry["path"] for entry in specs]
    actual = {"TNDLib.lean"} | {
        path.relative_to(repo).as_posix() for path in (repo / "TNDLib").rglob("*.lean")
    }
    if len(paths) != len(set(paths)) or set(paths) != actual:
        raise ValueError("promoted admission policy does not exactly cover library sources")
    root_spec = next(entry for entry in specs if entry["path"] == "TNDLib.lean")
    imports = [
        line.removeprefix("import ")
        for line in (repo / "TNDLib.lean").read_text().splitlines()
        if line.startswith("import ")
    ]
    if imports != root_spec["imports"]:
        raise ValueError("promoted root imports differ from admission policy")
    promoted_specs = [entry for entry in specs if entry["path"] == PROMOTED_PATH]
    if len(promoted_specs) != 1 or promoted_specs[0] != {
        "path": PROMOTED_PATH,
        "module_name": PROMOTED_MODULE,
        "namespace_name": PROMOTED_NAMESPACE,
        "imports": ["Init"],
        "declarations": [PROMOTED_DECLARATION],
        "universes": ["u", "v"],
    }:
        raise ValueError("promoted source policy differs from the maintained rehearsal contract")

    exports = json.loads((repo / "audit/exports.json").read_text())
    expected = exports["expected_exports"]
    displayed = exports["display_exports"]
    if expected != sorted(set(expected)) or displayed != sorted(set(displayed)):
        raise ValueError("promoted export inventories must be unique and sorted")
    if set(exports["source_paths"]) != set(expected):
        raise ValueError("promoted source mappings do not cover the exact export inventory")
    for name, source_path in exports["source_paths"].items():
        if source_path not in actual or name not in expected:
            raise ValueError("promoted export maps to an unapproved source")
    for field in ("descriptions", "contributors", "citations"):
        if set(exports[field]) != set(displayed) or any(
            not isinstance(value, str) or not value.strip() for value in exports[field].values()
        ):
            raise ValueError("promoted display metadata is missing or blank")
    if (
        PROMOTED_DECLARATION not in expected
        or PROMOTED_DECLARATION not in displayed
        or exports["source_paths"].get(PROMOTED_DECLARATION) != PROMOTED_PATH
        or exports["descriptions"].get(PROMOTED_DECLARATION) != DESCRIPTION
        or exports["contributors"].get(PROMOTED_DECLARATION) != CONTRIBUTOR
        or exports["citations"].get(PROMOTED_DECLARATION) != CITATION
    ):
        raise ValueError("promoted declaration lacks its exact inventory or metadata policy")


def _tool_env(lean: Path, search: list[Path] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    poisoned = ("ELAN_TOOLCHAIN", "LEAN_SYSROOT", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_PLUGIN_PATH")
    for name in poisoned:
        env.pop(name, None)
    env["PATH"] = str(lean.parent) + os.pathsep + "/usr/bin:/bin"
    env["LEAN_NUM_THREADS"] = "2"
    if search:
        env["LEAN_PATH"] = os.pathsep.join(str(path) for path in search)
    return env


def _parser_check(
    lean: Path, parser: Path, source: Path, specs: list[dict], workspace: Path
) -> dict:
    config = workspace / (source.name + "-parser-policy.json")
    _write_json(config, {"source_files": specs})
    result = _command(
        [str(lean), "--run", str(parser), str(config), str(source)],
        cwd=parser.parent,
        env=_tool_env(lean),
    )
    report = json.loads(result.stdout)
    if report != {
        "status": "admitted-source-syntax",
        "scope": "approved-library-source-only",
        "development_only": True,
    }:
        raise ValueError(f"unexpected admission result: {report!r}")
    return report


def admit_task_solution(
    project: Path, repo: Path, lean: Path, workspace: Path, challenge: bytes
) -> dict:
    policy = json.loads((repo / "audit/admission/policy.json").read_text())
    task, = [entry for entry in policy["task_files"] if entry["id"] == "map_exists"]
    if hashlib.sha256(challenge).hexdigest() != task["challenge_sha256"]:
        raise ValueError("task challenge differs from its approved exact-byte hash")
    stage = workspace / "admitted-task-solution"
    stage.mkdir()
    for entry in policy["source_files"]:
        target = stage / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / entry["path"], target)
    solution = _git(repo, "show", "HEAD:tasks/map_exists.lean")
    (stage / "Task.lean").write_bytes(solution)
    report = _parser_check(
        lean,
        project / "audit/admission/Main.lean",
        stage,
        [*policy["source_files"], task],
        workspace,
    )
    if _git(repo, "show", "HEAD:tasks/map_exists.lean") != (stage / "Task.lean").read_bytes():
        raise ValueError("admitted solution bytes differ from the accepted Git blob")
    return report


def admit_promoted_library(project: Path, repo: Path, lean: Path, workspace: Path) -> dict:
    validate_promoted_tree(repo)
    policy = json.loads((repo / "audit/admission/policy.json").read_text())
    return _parser_check(
        lean,
        project / "audit/admission/Main.lean",
        repo,
        policy["source_files"],
        workspace,
    )


def compile_library(lean: Path, repo: Path, workspace: Path) -> Path:
    policy = json.loads((repo / "audit/admission/policy.json").read_text())
    workspace.mkdir(parents=True, exist_ok=False)
    build = workspace / "library-build"
    build.mkdir()
    env = _tool_env(lean, [build])
    root = next(entry for entry in policy["source_files"] if entry["path"] == "TNDLib.lean")
    for entry in [item for item in policy["source_files"] if item is not root]:
        output = build / (entry["module_name"].replace(".", "/") + ".olean")
        output.parent.mkdir(parents=True, exist_ok=True)
        _command([str(lean), "-o", str(output), str(repo / entry["path"])], cwd=repo, env=env)
    output = build / "TNDLib.olean"
    _command([str(lean), "-o", str(output), str(repo / "TNDLib.lean")], cwd=repo, env=env)
    if _git(repo, "status", "--porcelain"):
        raise ValueError("compiling the temporary commit changed its tracked tree")
    return build


def export_module(
    lean: Path,
    exporter: Path,
    module: str,
    namespace: str,
    search: list[Path],
    output: Path,
) -> Path:
    result = _command(
        [str(exporter), module, namespace], cwd=output.parent, env=_tool_env(lean, search)
    )
    if not 0 < len(result.stdout) <= MAX_TOOL_OUTPUT:
        raise ValueError("proof export is empty or oversized")
    output.write_bytes(result.stdout)
    return output


def export_task(
    lean: Path, exporter: Path, library_build: Path, source: bytes, workspace: Path
) -> Path:
    workspace.mkdir(parents=True, exist_ok=False)
    task_source = workspace / "Task.lean"
    task_source.write_bytes(source)
    task_build = workspace / "build"
    task_build.mkdir()
    env = _tool_env(lean, [task_build, library_build])
    _command(
        [str(lean), "-o", str(task_build / "Task.olean"), str(task_source)],
        cwd=workspace,
        env=env,
    )
    return export_module(
        lean,
        exporter,
        "Task",
        "TNDTask",
        [task_build, library_build],
        workspace / "export.ndjson",
    )


def check_exports(
    lean: Path,
    checker: Path,
    config: dict,
    challenge: Path,
    solution: Path,
    workspace: Path,
) -> dict:
    workspace.mkdir(parents=True, exist_ok=False)
    config_path = workspace / "checker-config.json"
    _write_json(config_path, config)
    result = _command(
        [str(checker), str(config_path), str(challenge), str(solution)],
        cwd=workspace,
        env=_tool_env(lean),
    )
    report = json.loads(result.stdout)
    if report.get("status") != "verified-proof-objects" or report.get("toolchain") != "4.35.0":
        raise ValueError(f"proof-object checker did not verify the rehearsal: {report!r}")
    return report


def clone_exact_commit(repo: Path, destination: Path, revision: str) -> Path:
    _command(
        ["git", "-c", "core.hooksPath=/dev/null", "clone", "--quiet", "--no-hardlinks",
         str(repo), str(destination)],
        cwd=repo.parent,
    )
    if _git(destination, "rev-parse", "HEAD").decode().strip() != revision:
        raise ValueError("exact promoted commit clone resolved to a different revision")
    if _git(destination, "status", "--porcelain"):
        raise ValueError("exact promoted commit clone is not clean")
    return destination


def rehearse(project: Path, lean: Path, checker: Path, exporter: Path, workspace: Path) -> dict:
    project = project.resolve(strict=True)
    lean, checker, exporter = (path.resolve(strict=True) for path in (lean, checker, exporter))
    require_development_only(project)
    version = _command([str(lean), "--version"], cwd=project, env=_tool_env(lean)).stdout.decode()
    if not re.search(r"\bversion 4\.35\.0(?:,|\s|\))", version):
        raise ValueError("promotion rehearsal requires the pinned Lean 4.35.0 toolchain")
    original_paths = [
        project / "TNDLib.lean",
        project / "audit/exports.json",
        project / "audit/admission/policy.json",
        project / "tasks/map_exists.lean",
        project / ".choir/certification.json",
        *(project / "TNDLib").rglob("*.lean"),
    ]
    original_hashes = {path: _sha256(path) for path in original_paths}
    challenge = (project / "tasks/map_exists.lean").read_bytes()
    trusted_solution = (project / "tests/tasks/MapExistsSolution.lean").read_bytes()

    repo = workspace / "temporary-tndlib"
    copy_baseline(project, repo)
    baseline = initialize_repository(repo)
    accepted = accept_solution(repo, trusted_solution)
    task_admission = admit_task_solution(project, repo, lean, workspace, challenge)
    accepted_build = compile_library(lean, repo, workspace / "accepted")
    task_challenge = export_task(
        lean, exporter, accepted_build, challenge, workspace / "task-challenge"
    )
    task_solution = export_task(
        lean, exporter, accepted_build, trusted_solution, workspace / "task-solution"
    )
    task_config = {
        "namespace_name": "TNDTask",
        "expected_exports": ["TNDTask.mapExists"],
        "display_exports": [],
        "descriptions": {},
        "contributors": {},
        "citations": {},
        "source_paths": {"TNDTask.mapExists": "tasks/map_exists.lean"},
    }
    task_report = check_exports(
        lean, checker, task_config, task_challenge, task_solution, workspace / "task-check"
    )

    promoted = promote(repo, trusted_solution)
    exact = clone_exact_commit(repo, workspace / "promoted-commit", promoted)
    promotion_admission = admit_promoted_library(project, exact, lean, workspace)
    promoted_build = compile_library(lean, exact, workspace / "promoted")
    library_export = export_module(
        lean,
        exporter,
        "TNDLib",
        "TNDLib",
        [promoted_build],
        workspace / "promoted/library.ndjson",
    )
    library_config = json.loads((exact / "audit/exports.json").read_text())
    library_report = check_exports(
        lean,
        checker,
        library_config,
        library_export,
        library_export,
        workspace / "library-check",
    )
    promoted_entries = [
        item for item in library_report["declarations"] if item["name"] == PROMOTED_DECLARATION
    ]
    if (
        len(promoted_entries) != 1
        or promoted_entries[0]["axioms"] != []
        or promoted_entries[0]["statement_axioms"] != []
        or promoted_entries[0]["source_path"] != PROMOTED_PATH
        or promoted_entries[0]["description"] != DESCRIPTION
        or promoted_entries[0]["contributor"] != CONTRIBUTOR
        or promoted_entries[0]["citation"] != CITATION
    ):
        raise ValueError("promoted declaration evidence is incomplete or nonconstructive")
    if len(library_report["declarations"]) != len(library_config["expected_exports"]):
        raise ValueError("full promoted library evidence does not cover its exact inventory")
    for path, before in original_hashes.items():
        if _sha256(path) != before:
            raise ValueError("promotion rehearsal changed the real published corpus")
    require_development_only(exact)
    return {
        "schema_version": 1,
        "status": "passed",
        "scope": "development-only-task-to-promotion-rehearsal",
        "certification_issued": False,
        "temporary_commits": {
            "baseline": baseline,
            "accepted_task": accepted,
            "promoted_library": promoted,
        },
        "task": {
            "id": "map_exists",
            "admission": task_admission["status"],
            "proof_check": task_report["status"],
        },
        "promotion": {
            "declaration": PROMOTED_DECLARATION,
            "admission": promotion_admission["status"],
            "proof_check": library_report["status"],
            "export_count": len(library_report["declarations"]),
            "axioms": promoted_entries[0]["axioms"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--exporter", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tnd-promotion-rehearsal-") as temporary:
        result = rehearse(
            args.project,
            args.lean,
            args.checker,
            args.exporter,
            Path(temporary),
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
