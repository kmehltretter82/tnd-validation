#!/usr/bin/env python3
"""End-to-end mathematical boundary tests, using only trusted fixture sources.

These tests deliberately run fixture elaboration directly. They test proof-object
validation, not Docker isolation; never replace fixture inputs with PR sources.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

BASE = "import Init\nnamespace TNDLib\ntheorem target : (0 : Nat) = 0 := rfl\nend TNDLib\n"

CASES = [
    ("constructive", BASE, BASE, {}, True, ""),
    (
        "direct_choice",
        BASE,
        BASE.replace("rfl", "Classical.choice ⟨rfl⟩"),
        {},
        False,
        "Classical.choice",
    ),
    (
        "indirect_choice",
        BASE,
        "import Helper\nnamespace TNDLib\n"
        "theorem target : (0 : Nat) = 0 := Helper.proof\nend TNDLib\n",
        {"Helper": "import Init\ntheorem Helper.proof : (0 : Nat) = 0 := Classical.choice ⟨rfl⟩\n"},
        False,
        "Classical.choice",
    ),
    (
        "imported_sorry",
        BASE,
        "import Helper\nnamespace TNDLib\n"
        "theorem target : (0 : Nat) = 0 := Helper.proof\nend TNDLib\n",
        {"Helper": "import Init\ntheorem Helper.proof : (0 : Nat) = 0 := by sorry\n"},
        False,
        "sorryAx",
    ),
    (
        "custom_axiom",
        BASE,
        "import Init\naxiom unapproved : (0 : Nat) = 0\nnamespace TNDLib\n"
        "theorem target : (0 : Nat) = 0 := unapproved\nend TNDLib\n",
        {},
        False,
        "unapproved",
    ),
    (
        "native_evaluation",
        BASE,
        BASE.replace("rfl", "by native_decide"),
        {},
        False,
        "prohibited axiom",
    ),
    (
        "added_hypothesis",
        BASE,
        BASE.replace("theorem target :", "theorem target (h : False) :"),
        {},
        False,
        "statement do not match",
    ),
    (
        "changed_statement",
        BASE,
        BASE.replace("(0 : Nat) = 0 := rfl", "True := True.intro"),
        {},
        False,
        "statement do not match",
    ),
    (
        "extra_export",
        BASE,
        BASE.replace("end TNDLib", "theorem extra : True := True.intro\nend TNDLib"),
        {},
        False,
        "inventory",
    ),
]


def config_data(names: list[str], namespace: str = "TNDLib") -> dict:
    return {
        "namespace_name": namespace,
        "expected_exports": names,
        "display_exports": names,
        "descriptions": {name: "Trusted verifier fixture." for name in names},
        "contributors": {name: "TND test suite" for name in names},
        "citations": {name: "Synthetic verifier fixture" for name in names},
        "source_paths": {name: "Fixture.lean" for name in names},
    }


def run(
    args: list[str], env: dict, *, output: Path | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    with output.open("wb") if output else open(os.devnull, "wb") as handle:
        result = subprocess.run(
            args,
            env=env,
            stdout=handle if output else subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            cwd=cwd,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(
            f"fixture setup failed: {args}\n{result.stdout!r}\n{result.stderr.decode()}"
        )
    return result


def export_source(
    lean: Path,
    exporter: Path,
    workspace: Path,
    source: str,
    helpers: dict[str, str],
    env: dict,
    namespace: str = "TNDLib",
) -> Path:
    workspace.mkdir()
    build = workspace / "build"
    build.mkdir()
    env = dict(env, LEAN_PATH=str(build) + os.pathsep + env.get("LEAN_PATH", ""))
    for module, contents in [*helpers.items(), ("Fixture", source)]:
        path = workspace / (module + ".lean")
        path.write_text(contents)
        run([str(lean), "-o", str(build / (module + ".olean")), str(path)], env, cwd=workspace)
    export = workspace / "export.ndjson"
    run([str(exporter), "Fixture", namespace], env, output=export)
    return export


# This runner batches scenarios against shared challenge exports to limit build cost.
def main() -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--exporter", type=Path, required=True)
    args = parser.parse_args()
    args.lean, args.checker, args.exporter = (
        p.resolve() for p in (args.lean, args.checker, args.exporter)
    )
    env = dict(
        os.environ,
        PATH=str(args.lean.parent) + os.pathsep + os.environ["PATH"],
        LEAN_NUM_THREADS="2",
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="tnd-fixtures-") as tmp:
        root = Path(tmp)
        config = root / "config.json"
        config.write_text(json.dumps(config_data(["TNDLib.target"])))
        common_challenge = export_source(
            args.lean, args.exporter, root / "common-base", BASE, {}, env
        )
        for field in ("descriptions", "contributors", "citations"):
            incomplete = config_data(["TNDLib.target"])
            incomplete[field] = {}
            config.write_text(json.dumps(incomplete))
            check = subprocess.run(
                [str(args.checker), str(config), str(common_challenge), str(common_challenge)],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            report = json.loads(check.stdout)
            assert check.returncode != 0 and "metadata keys differ" in report.get("reason", ""), (
                report
            )
            results.append({"fixture": "missing_" + field, "passed": True, "result": "rejected"})
            incomplete = config_data(["TNDLib.target"])
            incomplete[field]["TNDLib.target"] = " \t\n"
            config.write_text(json.dumps(incomplete))
            check = subprocess.run(
                [str(args.checker), str(config), str(common_challenge), str(common_challenge)],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            report = json.loads(check.stdout)
            assert check.returncode != 0 and "metadata is blank" in report.get("reason", ""), report
            results.append({"fixture": "blank_" + field, "passed": True, "result": "rejected"})
        config.write_text(json.dumps(config_data(["TNDLib.target"])))
        for name, challenge_source, solution_source, helpers, accepted, reason in CASES:
            challenge = (
                common_challenge
                if challenge_source == BASE
                else export_source(
                    args.lean, args.exporter, root / (name + "-base"), challenge_source, {}, env
                )
            )
            solution = export_source(
                args.lean, args.exporter, root / (name + "-head"), solution_source, helpers, env
            )
            checked = subprocess.run(
                [str(args.checker), str(config), str(challenge), str(solution)],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            report = json.loads(checked.stdout)
            actual = checked.returncode == 0
            assert actual == accepted, (name, report)
            if reason:
                assert reason in report.get("reason", ""), (name, report)
            results.append({"fixture": name, "passed": True, "result": report["status"]})
            print(json.dumps(results[-1]), flush=True)

        definitions = (
            "import Init\nnamespace TNDLib\ndef value : Nat := 0\n"
            "theorem target : value = value := rfl\nend TNDLib\n"
        )
        challenge = export_source(
            args.lean, args.exporter, root / "definition-base", definitions, {}, env
        )
        solution = export_source(
            args.lean,
            args.exporter,
            root / "definition-head",
            definitions.replace("Nat := 0", "Nat := 1"),
            {},
            env,
        )
        config.write_text(json.dumps(config_data(["TNDLib.target", "TNDLib.value"])))
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(solution)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert (
            check.returncode != 0 and "Const does not match" in json.loads(check.stdout)["reason"]
        ), check.stdout
        results.append({"fixture": "changed_definition", "passed": True})

        statement_choice = (
            "import Init\nnoncomputable def Hidden.value : Nat := Classical.choice ⟨0⟩\n"
            "namespace TNDLib\ntheorem target : Hidden.value = Hidden.value := rfl\nend TNDLib\n"
        )
        challenge = export_source(
            args.lean, args.exporter, root / "statement-choice", statement_choice, {}, env
        )
        config.write_text(json.dumps(config_data(["TNDLib.target"])))
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(challenge)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert check.returncode != 0 and "Classical.choice" in json.loads(check.stdout)["reason"], (
            check.stdout
        )
        results.append({"fixture": "choice_in_statement", "passed": True})

        challenge = export_source(args.lean, args.exporter, root / "forged-proof", BASE, {}, env)
        # A raw proof object claiming a numeral is a proof of Nat equality must
        # reach and fail the independent kernel, without running Lean source.
        lines = [json.loads(line) for line in challenge.read_text().splitlines()]
        next_expr = 1 + max(item.get("ie", 0) for item in lines)
        names = {0: ""}
        for index, item in enumerate(lines):
            if "in" in item:
                part = item.get("str", item.get("num"))
                tail = part.get("str", str(part.get("i")))
                names[item["in"]] = ".".join(x for x in (names[part["pre"]], tail) if x)
            if "thm" in item and names[item["thm"]["name"]] == "TNDLib.target":
                lines[index]["thm"]["value"] = next_expr
                lines.insert(index, {"ie": next_expr, "natVal": "7"})
                break
        forged = root / "forged.ndjson"
        forged.write_text("\n".join(json.dumps(item) for item in lines) + "\n")
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(forged)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert check.returncode != 0 and "type mismatch" in json.loads(check.stdout)["reason"], (
            check.stdout
        )
        results.append(
            {
                "fixture": "forged_proof_object",
                "passed": True,
                "reason": json.loads(check.stdout)["reason"],
            }
        )

        project = Path(__file__).resolve().parents[2]
        task_env = dict(env, LEAN_PATH=str(project / ".lake/build/lib/lean"))
        task_base = (project / "tasks/map_exists.lean").read_text()
        task_solution = (project / "tests/tasks/MapExistsSolution.lean").read_text()
        config.write_text(json.dumps(config_data(["TNDTask.mapExists"], "TNDTask")))
        challenge = export_source(
            args.lean, args.exporter, root / "task-base", task_base, {}, task_env, "TNDTask"
        )
        solution = export_source(
            args.lean, args.exporter, root / "task-solution", task_solution, {}, task_env, "TNDTask"
        )
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(solution)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert check.returncode == 0, check.stdout
        results.append({"fixture": "approved_task_solution", "passed": True})
        weakened = task_solution.replace("(p : β → Prop) :", "(p : β → Prop) (extra : False) :")
        solution = export_source(
            args.lean, args.exporter, root / "task-weakened", weakened, {}, task_env, "TNDTask"
        )
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(solution)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert (
            check.returncode != 0 and "statement do not match" in json.loads(check.stdout)["reason"]
        ), check.stdout
        results.append({"fixture": "changed_task_statement", "passed": True})

        # Regression witness for the unresolved coverage gap: a publishable
        # module not imported by the root is invisible to root-only export.
        # The proof-object checker accepts this, so production MUST stay off.
        config.write_text(json.dumps(config_data(["TNDLib.target"])))
        challenge = common_challenge
        solution = export_source(
            args.lean,
            args.exporter,
            root / "unimported-module",
            BASE,
            {
                "Evil": "import Init\nnamespace TNDLib.Evil\naxiom unapproved : False\n"
                "theorem boom : False := unapproved\nend TNDLib.Evil\n"
            },
            env,
        )
        check = subprocess.run(
            [str(args.checker), str(config), str(challenge), str(solution)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert check.returncode == 0, check.stdout
        certification = json.loads((project / ".choir/certification.json").read_text())
        assert certification["source_binding_validated"] is False
        assert certification["resource_boundary_validated"] is False
        assert certification["resource_limits"] is None
        results.append(
            {
                "fixture": "unimported_module_known_gap",
                "passed": True,
                "production_disabled": True,
                "known_gap": True,
            }
        )
    print(json.dumps({"passed": len(results), "fixtures": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
