#!/usr/bin/env python3
"""Development profile fixtures; candidate text is parsed, never elaborated.

The fixture policy is described once from the fixed trusted baseline below.
Every hostile case changes only candidate bytes, retaining that same policy.
This harness is not a production certification or sandbox acceptance test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "audit/matching/Main.lean"
POLICY = ROOT / "audit/matching/source-policy.json"
PROFILE = "matching-plain-term-v1"
BASE = """import Init
namespace Fixture
structure Box where
  value : Nat
inductive Verdict where
  | accepted : Nat → Verdict
  | rejected : Verdict

def sample (n : Nat) : Nat := n

theorem proof (n : Nat) : n = n := rfl
end Fixture
"""
SAMPLE = "def sample (n : Nat) : Nat := n"
PROOF = "theorem proof (n : Nat) : n = n := rfl"


def body(expression: str) -> str:
    return BASE.replace(SAMPLE, "def sample (n : Nat) : Nat :=\n  " + expression)


def fixtures() -> list[tuple[str, bool, str]]:
    positives = {
        "baseline": BASE,
        "ordinary_if": body("if n = 0 then 1 else n"),
        "dependent_if": body("if same : n = 0 then 0 else n"),
        "plain_let": body("let x := n\n  x"),
        "typed_let": body("let x : Nat := n\n  x"),
        "explicit_argument": body("@id Nat n"),
        "named_argument": body("id (α := Nat) n"),  # noqa: RUF001
        "show_from": body("show Nat from n"),
        "type_ascription": body("(n : Nat)"),
        "substitution": body("Eq.refl n ▸ n"),
        "instance_inference_term": body("let decision := inferInstanceAs (Decidable (n = 0))\n  n"),
        "calculation": BASE.replace(
            PROOF, "theorem proof (n : Nat) : n = n :=\n  calc n = n := rfl"
        ),
        "not_equal_not_member_subset": BASE.replace(
            SAMPLE, "def sample (n : Nat) : Prop := n ≠ 0 ∧ n ∉ [n] ∧ [n] ⊆ [n]"
        ),
    }
    negatives = {
        "sorry": body("sorry"),
        "opaque": BASE.replace(SAMPLE, "opaque sample (n : Nat) : Nat := n"),
        "axiom": BASE.replace(SAMPLE, "axiom sample : Nat → Nat"),
        "initialize": BASE.replace(
            "end Fixture", 'initialize do IO.println "untrusted"\nend Fixture'
        ),
        "run_command": BASE.replace("end Fixture", 'run_cmd Lean.logInfo "untrusted"\nend Fixture'),
        "macro": BASE.replace("end Fixture", 'macro "attack" : term => `(True.intro)\nend Fixture'),
        "elaborator": BASE.replace(
            "end Fixture", 'elab "attack" : command => pure ()\nend Fixture'
        ),
        "notation": BASE.replace("end Fixture", 'notation "attack" => True\nend Fixture'),
        "option_command": BASE.replace(
            "end Fixture", "set_option debug.skipKernelTC true\nend Fixture"
        ),
        "attribute_command": BASE.replace(
            "end Fixture", "attribute [simp] Fixture.proof\nend Fixture"
        ),
        "root_declaration": BASE.replace(PROOF, "theorem _root_.proof (n : Nat) : n = n := rfl"),
        "qualified_declaration": BASE.replace(
            PROOF, "theorem Other.proof (n : Nat) : n = n := rfl"
        ),
        "early_exit": BASE.replace("end Fixture", 'exit\n#eval IO.println "hidden"\nend Fixture'),
        "check_command": BASE.replace("end Fixture", "#check True\nend Fixture"),
        "include_string": body('include_str "secret"'),
        "eval_percent": body("eval% (pure n)"),
        "out_param": body("outParam"),
        "semi_out_param": body("semiOutParam"),
        "quoted_auto_param": body("«autoParam»"),
        "constructed_string": body("String.ofList [Char.ofNat 97]"),
        "unclosed_comment": BASE + "\n/- never closed",
        "mutual_family": BASE.replace(
            "inductive Verdict where", "mutual\ninductive Verdict where"
        ).replace("  | rejected : Verdict", "  | rejected : Verdict\nend"),
        "nested_constructor": BASE.replace(
            "  | rejected : Verdict", "  | rejected : List Verdict → Verdict"
        ),
        "class": BASE.replace("structure Box", "class Box"),
        "extends": BASE.replace("structure Box where", "structure Box extends Nat where"),
        "explicit_constructor": BASE.replace(
            "structure Box where", "structure Box where\n  custom ::"
        ),
        "extra_field": BASE.replace("  value : Nat", "  value : Nat\n  extra : Nat"),
        "missing_field": BASE.replace("  value : Nat", "  changed : Nat"),
        "duplicate_field": BASE.replace("  value : Nat", "  value : Nat\n  value : Nat"),
        "changed_field_type": BASE.replace("  value : Nat", "  value : Bool"),
        "pure_field_default": BASE.replace("  value : Nat", "  value : Nat := 0"),
        "tactic_field_default": BASE.replace("  value : Nat", "  value : Nat := by exact 0"),
        "tactic_field_type": BASE.replace("  value : Nat", "  value : (by exact Nat)"),
        "field_attribute": BASE.replace("  value : Nat", "  @[simp] value : Nat"),
        "field_private": BASE.replace("  value : Nat", "  private value : Nat"),
        "structure_deriving": BASE.replace(
            "  value : Nat", "  value : Nat\n  deriving DecidableEq"
        ),
        "extra_constructor": BASE.replace(
            "  | rejected : Verdict", "  | rejected : Verdict\n  | extra : Verdict"
        ),
        "missing_constructor": BASE.replace("  | rejected : Verdict\n", ""),
        "duplicate_constructor": BASE.replace(
            "  | rejected : Verdict", "  | rejected : Verdict\n  | rejected : Verdict"
        ),
        "recursive_constructor": BASE.replace(
            "  | rejected : Verdict", "  | rejected : Verdict → Verdict"
        ),
        "indexed_family": BASE.replace(
            "inductive Verdict where", "inductive Verdict : Nat → Type where"
        ),
        "constructor_attribute": BASE.replace(
            "  | rejected : Verdict", "  | @[simp] rejected : Verdict"
        ),
        "inductive_deriving": BASE.replace(
            "  | rejected : Verdict", "  | rejected : Verdict\n  deriving Repr"
        ),
        "private_declaration": BASE.replace(PROOF, "private " + PROOF),
        "protected_declaration": BASE.replace(PROOF, "protected " + PROOF),
        "unsafe_declaration": BASE.replace(SAMPLE, "unsafe " + SAMPLE),
        "partial_declaration": BASE.replace(SAMPLE, "partial " + SAMPLE),
        "noncomputable_declaration": BASE.replace(SAMPLE, "noncomputable " + SAMPLE),
        "declaration_attribute": BASE.replace(PROOF, "@[simp] " + PROOF),
        "instance": BASE.replace(SAMPLE, "instance sample : Inhabited Nat := ⟨0⟩"),
        "local_instance": BASE.replace(SAMPLE, "local instance sample : Inhabited Nat := ⟨0⟩"),
        "scoped_instance": BASE.replace(SAMPLE, "scoped instance sample : Inhabited Nat := ⟨0⟩"),
        "priority_instance": BASE.replace(
            SAMPLE, "instance (priority := 100) sample : Inhabited Nat := ⟨0⟩"
        ),
        "let_instance": body("letI : Inhabited Nat := ⟨0⟩\n  n"),
        "let_recursive": body("let rec recur (x : Nat) : Nat := recur x\n  recur n"),
        "let_pattern": body("let (x, y) := (n, n)\n  x"),
        "let_configuration": body("let +nondep x := n\n  x"),
        "attached_where": body("helper n\nwhere\n  helper (x : Nat) : Nat := x"),
        "termination_annotation": body("n\ntermination_by n"),
        "tactic_body": body("by exact n"),
        "tactic_if_condition": body("if (by exact True) then n else n"),
        "tactic_if_branch": body("if n = 0 then (by exact n) else n"),
        "tactic_named_argument": body("id (α := by exact Nat) n"),  # noqa: RUF001
        "tactic_let_value": body("let x := by exact n\n  x"),
        "tactic_calc_step": BASE.replace(
            PROOF, "theorem proof (n : Nat) : n = n :=\n  calc n = n := by rfl"
        ),
        "effectful_identifier": body("IO.run"),
        "reflective_under_explicit": body("@Lean.Elab.Term.elabTerm"),
        "reflective_under_show": body("show Nat from unsafeCast n"),
        "reflective_under_inference": body("inferInstanceAs (IO Nat)"),
        "reflective_under_substitution": body("Eq.refl n ▸ unsafeCast n"),
        "root_qualified_identifier": body("_root_.id n"),
        "auto_param": body("let x : autoParam Nat n := n\n  x"),
        "string_literal": body('"candidate"'),
        "syntax_quotation": body("(term| n)"),
        "do_block": body("do pure n"),
        "extra_declaration": BASE.replace("end Fixture", "def extra : Nat := 0\nend Fixture"),
        "duplicate_declaration": BASE.replace("end Fixture", SAMPLE + "\nend Fixture"),
        "changed_namespace": BASE.replace("namespace Fixture", "namespace Other"),
        "nested_namespace": BASE.replace(SAMPLE, "namespace Inner\n" + SAMPLE + "\nend Inner"),
        "reopened_namespace": BASE.replace(
            "end Fixture", "end Fixture\nnamespace Fixture\nend Fixture"
        ),
        "missing_namespace_end": BASE.replace("end Fixture", ""),
        "lean_import": BASE.replace("import Init", "import Lean"),
        "mathlib_import": BASE.replace("import Init", "import Mathlib"),
        "unknown_import": BASE.replace("import Init", "import Unreviewed"),
        "duplicate_import": BASE.replace("import Init", "import Init\nimport Init"),
        "prelude": "prelude\n" + BASE,
        "late_import": BASE + "import Init\n",
        "eval_command": BASE.replace("end Fixture", "#eval IO.println 123\nend Fixture"),
        "syntax_extension": BASE.replace("end Fixture", 'syntax "candidate" : term\nend Fixture'),
        "invalid_syntax": body("("),
        "deep_syntax": body("(" * 140 + "n" + ")" * 140),
    }
    return [(name, True, text) for name, text in positives.items()] + [
        (name, False, text) for name, text in negatives.items()
    ]


def invoke(lean: Path, args: list[str]) -> object:
    env = dict(os.environ)
    for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LEAN_PLUGIN_PATH"):
        env.pop(name, None)
    env["LEAN_NUM_THREADS"] = "2"
    result = subprocess.run(
        [str(lean), "--run", str(MAIN), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    lean = args.lean or Path(
        subprocess.check_output(["elan", "which", "lean"], cwd=ROOT, text=True).strip()
    )
    production = ROOT / "audit/admission/Main.lean"
    production_hash = hashlib.sha256(production.read_bytes()).hexdigest()
    full = invoke(lean, [str(POLICY), str(ROOT)])
    assert full["status"] == "admitted-source-syntax", full
    assert full["profile"] == PROFILE and full["development_only"] is True, full
    cases = fixtures()
    with tempfile.TemporaryDirectory(prefix="tnd-matching-admission-fixtures-") as tmp:
        work = Path(tmp)
        baseline = work / "baseline"
        baseline.mkdir()
        (baseline / "Fixture.lean").write_text(BASE)
        described = invoke(lean, ["--describe", str(baseline), "Fixture.lean"])
        assert described["status"] == "description-only"
        policy = {"profile": PROFILE, "source_files": described["source_files"]}
        policy_path = work / "fixture-policy.json"
        policy_path.write_text(json.dumps(policy))
        roots = []
        for index, (_name, _accepted, text) in enumerate(cases):
            root = work / str(index)
            root.mkdir()
            (root / "Fixture.lean").write_text(text)
            if _name == "unknown_import":
                # This file must stay inert: headers are parsed, never imported.
                (root / "Unreviewed.lean").write_text(
                    'import Lean\ninitialize do IO.FS.writeFile "candidate-executed" "bad"\n'
                )
            roots.append(str(root))
        roots_path = work / "roots.json"
        roots_path.write_text(json.dumps(roots))
        reports = invoke(lean, ["--batch", str(policy_path), str(roots_path)])
        assert len(reports) == len(cases)
        assert not list(work.rglob("candidate-executed"))
        assert not (ROOT / "candidate-executed").exists()
        results = []
        for (name, expected, _text), report in zip(cases, reports, strict=True):
            accepted = report.get("status") == "admitted-source-syntax"
            assert accepted == expected, (name, expected, report)
            results.append({"case": name, "expected_accepted": expected, "report": report})
    assert hashlib.sha256(production.read_bytes()).hexdigest() == production_hash
    evidence = {
        "development_only": True,
        "profile": PROFILE,
        "production_parser_sha256": production_hash,
        "development_parser_sha256": hashlib.sha256(MAIN.read_bytes()).hexdigest(),
        "source_policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        "fixture_harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "actual_source": full,
        "cases": results,
    }
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "actual_sources": full["source_files"],
                "positive_fixtures": sum(yes for _, yes, _ in cases),
                "negative_fixtures": sum(not yes for _, yes, _ in cases),
                "development_only": True,
            }
        )
    )


if __name__ == "__main__":
    main()
