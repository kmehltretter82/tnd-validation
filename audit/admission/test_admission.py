#!/usr/bin/env python3
"""Adversarial syntax/inventory fixtures; no candidate code is ever executed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import admit


# The fixture runner intentionally batches many source cases in one Lean
# process and shares one temporary workspace for cross-case hash checks.
def main() -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    source = admit.HERE.parent.parent
    paths = [entry["path"] for entry in json.loads(admit.POLICY.read_text())["source_files"]]
    initial = {path: (source / path).read_text() for path in paths}
    cases = []

    def add(name, path=None, transform=None, accepted=False):
        files = dict(initial)
        if path is not None:
            files[path] = transform(files[path])
        cases.append((name, files, accepted))

    add("initial_corpus", accepted=True)
    add(
        "arithmetic_and_order_notation",
        "TNDLib/Nat.lean",
        lambda s: s.replace("n ≤ sumTo n", "n * 1 < sumTo n + 1", 1),
        accepted=True,
    )
    add(
        "nested_comments_are_data",
        "TNDLib.lean",
        lambda s: '/- outer /- #eval "not executed" -/ initialize text -/\n' + s,
        True,
    )
    add(
        "ordinary_proof_term",
        "TNDLib/Nat.lean",
        lambda s: s.replace(":= rfl", ":= Eq.refl _"),
        True,
    )
    commands = {
        "eval_artifact_replacement": (
            '#eval IO.FS.writeBinFile ".lake/build/lib/lean/TNDLib/Nat.olean" ByteArray.empty'
        ),
        "initialize": 'initialize do IO.println "untrusted"',
        "run_cmd": 'run_cmd Lean.logInfo "untrusted"',
        "macro": 'macro "attack" : term => `(True.intro)',
        "elab": 'elab "attack" : command => pure ()',
        "syntax": 'syntax "attack" : command',
        "notation": 'notation "attack" => True',
        "option": "set_option debug.skipKernelTC true",
        "attribute": "attribute [simp] TNDLib.Logic.notOr",
        "root_declaration": "theorem _root_.escaped : True := True.intro",
        "outside_namespace": "theorem escaped : True := True.intro",
        "extra_namespace": "namespace Escaped\ntheorem escaped : True := True.intro\nend Escaped",
        "mid_file_import": 'import Evil\n#eval IO.println "hidden"',
        "early_exit": 'exit\n#eval IO.println "hidden"',
        "check_command": "#check True",
    }
    for name, command in commands.items():
        add(name, "TNDLib.lean", lambda s, c=command: s + "\n" + c + "\n")
    for modifier in ["private", "protected", "unsafe", "partial", "noncomputable", "@[simp]"]:
        add(
            "modifier_" + modifier,
            "TNDLib/Logic.lean",
            lambda s, m=modifier: s.replace(
                "theorem andOrDistribute", m + " theorem andOrDistribute", 1
            ),
        )
    for name, term in [
        ("tactic", "by exact rfl"),
        ("sorry", "sorry"),
        ("string", '"text"'),
        ("quotation", "`(True.intro)"),
        ("eval_percent", "eval% (pure True.intro)"),
        ("include_string", 'include_str "secret"'),
        ("unsupported_show", "show _ from rfl"),
        ("autoparam", "autoParam"),
        ("outparam", "outParam"),
        ("semi_outparam", "semiOutParam"),
        ("quoted_autoparam_identifier", "«autoParam»"),
        ("reflection", "Lean.Syntax.missing"),
        ("effectful_reference", "IO.println"),
        ("constructed_string", "String.ofList [Char.ofNat 97]"),
    ]:
        add(name, "TNDLib/Nat.lean", lambda s, t=term: s.replace(":= rfl", ":= " + t, 1))
    add(
        "root_qualified_name",
        "TNDLib/Logic.lean",
        lambda s: s.replace("theorem andOrDistribute", "theorem _root_.andOrDistribute", 1),
    )
    add(
        "qualified_name",
        "TNDLib/Logic.lean",
        lambda s: s.replace("theorem andOrDistribute", "theorem Other.andOrDistribute", 1),
    )
    add(
        "extra_axiom",
        "TNDLib/Logic.lean",
        lambda s: s.replace("end TNDLib.Logic", "axiom extra : False\nend TNDLib.Logic"),
    )
    add(
        "instance",
        "TNDLib/Logic.lean",
        lambda s: s.replace(
            "end TNDLib.Logic", "instance : Inhabited Nat := ⟨0⟩\nend TNDLib.Logic"
        ),
    )
    add("opaque", "TNDLib/Nat.lean", lambda s: s.replace("def sumTo :", "opaque sumTo :", 1))
    add("unclosed_comment", "TNDLib.lean", lambda s: s + "\n/- never closed")
    add(
        "comment_then_executable",
        "TNDLib.lean",
        lambda s: s + '\n/- inert /- nested -/ -/\n#eval IO.println "active"',
    )
    add("unclosed_namespace", "TNDLib/Nat.lean", lambda s: s.replace("end TNDLib.Nat", ""))
    for module in ["Lean", "Mathlib", "TNDLib.CustomSyntax"]:
        add(
            "forbidden_import_" + module,
            "TNDLib/Logic.lean",
            lambda s, m=module: s.replace("import Init", "import " + m, 1),
        )
    add("prelude", "TNDLib/Logic.lean", lambda s: "prelude\n" + s)
    add("module_header", "TNDLib/Logic.lean", lambda s: "module\n" + s)
    add("missing_root_import", "TNDLib.lean", lambda s: s.replace("import TNDLib.Nat\n", ""))

    with tempfile.TemporaryDirectory(prefix="tnd-admission-fixtures-") as temporary:
        root = Path(temporary)
        staged_roots, expected = [], []
        for index, (name, files, accepted) in enumerate(cases):
            candidate, staged = root / str(index), root / ("staged-" + str(index))
            candidate.mkdir()
            staged.mkdir()
            for path, text in files.items():
                target = candidate / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            admit.snapshot(candidate, staged)
            staged_roots.append(str(staged))
            expected.append((name, accepted))
        roots_json = root / "roots.json"
        roots_json.write_text(json.dumps(staged_roots))
        lean = args.lean.resolve()
        env = dict(
            os.environ, PATH=str(lean.parent) + os.pathsep + "/usr/bin:/bin", LEAN_NUM_THREADS="2"
        )
        for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LEAN_PLUGIN_PATH"):
            env.pop(name, None)
        command = [
            str(lean),
            "--run",
            str(admit.HERE / "Main.lean"),
            "--batch",
            str(admit.POLICY),
            str(roots_json),
        ]
        result = subprocess.run(
            command,
            cwd=admit.HERE,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        reports = json.loads(result.stdout)
        assert len(reports) == len(expected)
        for (name, accepted), report in zip(expected, reports, strict=True):
            actual = report.get("status") == "admitted-source-syntax"
            assert actual == accepted, (name, report)
            print(json.dumps({"fixture": name, "passed": True, "result": report["status"]}))

        # The Python boundary rejects extra importable modules and disguised bytes
        # before Lean sees the input. Test symlinks without following them.
        fs_cases = [
            "unimported_module",
            "root_shadow_module",
            "binary_source",
            "source_symlink",
            "directory_symlink",
            "extra_build_artifact",
        ]
        for name in fs_cases:
            candidate = root / name
            candidate.mkdir()
            for path, text in initial.items():
                target = candidate / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            if name == "unimported_module":
                (candidate / "TNDLib/Evil.lean").write_text("axiom TNDLib.evil : False\n")
            elif name == "root_shadow_module":
                (candidate / "Init.lean").write_text("axiom forged : False\n")
            elif name == "binary_source":
                (candidate / "TNDLib/Nat.lean").write_bytes(b"\0olean\xff")
            elif name == "source_symlink":
                (candidate / "TNDLib/Nat.lean").unlink()
                (candidate / "TNDLib/Nat.lean").symlink_to(candidate / "TNDLib/List.lean")
            elif name == "directory_symlink":
                (candidate / "TNDLib/Other").symlink_to(
                    candidate / "TNDLib", target_is_directory=True
                )
            else:
                (candidate / "TNDLib/Nat.olean").write_bytes(b"fake")
            staged = root / (name + "-stage")
            staged.mkdir()
            try:
                admit.snapshot(candidate, staged)
            except (OSError, ValueError):
                pass
            else:
                raise AssertionError(name + " was admitted")
            print(json.dumps({"fixture": name, "passed": True, "result": "rejected"}))

        # Task solution syntax is checked against the maintained task policy,
        # separately from the exact-byte-only trusted placeholder.
        solution = (source / "tests/tasks/MapExistsSolution.lean").read_text()
        challenge = (source / "tasks/map_exists.lean").read_text()
        task_cases = [
            ("task_solution", solution, True),
            (
                "task_by_tactic",
                solution.replace(
                    "fun h => Exists.elim h (fun x hx => Exists.intro (f x) hx)",
                    "by exact fun h => h",
                ),
                False,
            ),
            ("task_artifact_attack", solution + '\n#eval IO.println "attack"\n', False),
            ("task_bad_import", solution.replace("import TNDLib", "import Lean"), False),
            ("task_bad_universe", solution.replace("universe u v", "universe u w"), False),
            (
                "task_extra_declaration",
                solution.replace("end TNDTask", "theorem extra : True := True.intro\nend TNDTask"),
                False,
            ),
            (
                "task_reflection",
                solution.replace(
                    "fun h => Exists.elim h (fun x hx => Exists.intro (f x) hx)", "autoParam"
                ),
                False,
            ),
        ]
        task_roots = []
        for name, content, _ in task_cases:
            candidate = root / name
            candidate.mkdir()
            for path, text in initial.items():
                target = candidate / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            (candidate / "Task.lean").write_text(content)
            staged = root / (name + "-staged")
            staged.mkdir()
            admit.snapshot(candidate, staged, "map_exists", "solution")
            task_roots.append(str(staged))
        task_policy = root / "task-policy.json"
        task_policy.write_text(json.dumps(admit.policy_for("map_exists", "solution")[0]))
        task_roots_file = root / "task-roots.json"
        task_roots_file.write_text(json.dumps(task_roots))
        task_result = subprocess.run(
            [
                str(lean),
                "--run",
                str(admit.HERE / "Main.lean"),
                "--batch",
                str(task_policy),
                str(task_roots_file),
            ],
            cwd=admit.HERE,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if task_result.returncode:
            raise AssertionError(task_result.stdout + task_result.stderr)
        reports = json.loads(task_result.stdout)
        assert len(reports) == len(task_cases)
        for (name, _, accepted), report in zip(task_cases, reports, strict=True):
            assert (report.get("status") == "admitted-source-syntax") == accepted, (name, report)
            print(json.dumps({"fixture": name, "passed": True, "result": report["status"]}))

        baseline = root / "task-baseline"
        baseline.mkdir()
        for path, text in initial.items():
            target = baseline / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        (baseline / "Task.lean").write_text(challenge)
        baseline_stage = root / "task-baseline-stage"
        baseline_stage.mkdir()
        hashes = admit.snapshot(baseline, baseline_stage, "map_exists", "challenge")
        assert hashes["Task.lean"] == hashlib.sha256(challenge.encode()).hexdigest()
        admit.verify_exact(baseline_stage, hashes)
        (baseline_stage / "Task.lean").write_text(challenge + "\n")
        try:
            admit.verify_exact(baseline_stage, hashes)
        except ValueError:
            pass
        else:
            raise AssertionError("modified staged task passed exact hash check")
        (baseline / "Task.lean").write_text(challenge + "\n")
        altered_stage = root / "altered-baseline"
        altered_stage.mkdir()
        try:
            admit.snapshot(baseline, altered_stage, "map_exists", "challenge")
        except ValueError:
            pass
        else:
            raise AssertionError("modified challenge passed exact-byte policy")
        wrong_hashes = dict(hashes)
        wrong_hashes["TNDLib.lean"] = "0" * 64
        (baseline / "Task.lean").write_text(challenge)
        try:
            admit.admit_into(
                lean,
                baseline,
                root / "wrong-git-hash-stage",
                expected_hashes=wrong_hashes,
                task_id="map_exists",
                role="challenge",
            )
        except ValueError as exc:
            assert "differs from exact Git source hashes" in str(exc), exc
        else:
            raise AssertionError("incorrect Git source hashes were accepted")
        print(
            json.dumps(
                {"fixture": "task_exact_bytes", "passed": True, "result": "rejected-tampering"}
            )
        )
        solution_source = root / "task_solution"
        solution_hashes = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in admit.source_bytes(
                solution_source, set(initial) | {"Task.lean"}
            ).items()
        }
        report = admit.admit_into(
            lean,
            solution_source,
            root / "task-admitted",
            expected_hashes=solution_hashes,
            task_id="map_exists",
            role="solution",
        )
        assert report["scope"] == "approved-library-and-task-source"
        assert report["source_sha256"] == solution_hashes
        assert report["task"]["compiled_path"] == "Task.lean"
        admit.verify_exact(root / "task-admitted", solution_hashes)
        print(
            json.dumps({"fixture": "task_admit_into", "passed": True, "result": report["status"]})
        )
        print(
            json.dumps(
                {
                    "passed": len(cases) + len(fs_cases) + len(task_cases) + 2,
                    "development_only": True,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
