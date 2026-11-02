"""Exercise the matching pilot's maintained graph and exact Git-blob boundary."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
LOADER = importlib.util.spec_from_file_location(
    "tnd_matching_snapshot", PROJECT / "tests/matching/check_source.py",
)
snapshot = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(snapshot)
FROZEN_REVISION = "286cdc677a418f994c4814d9492ebdd3726700e5"


def small_policy():
    return {
        "profile": snapshot.PROFILE,
        "source_files": [
            {
                "module_name": snapshot.MODULE,
                "path": "pilot/TNDLib/Matching/Pilot.lean",
                "imports": ["TNDLib.Matching.Dependency"],
            },
            {
                "module_name": "TNDLib.Matching.Dependency",
                "path": "pilot/TNDLib/Matching/Dependency.lean",
                "imports": ["Init"],
            },
        ],
    }


def test_maintained_policy_is_a_complete_reachable_fourteen_module_graph():
    policy = json.loads((PROJECT / "audit/matching/source-policy.json").read_text())
    specs = snapshot.validate_policy(policy)
    assert len(specs) == 14
    assert {spec["path"] for spec in specs} == {
        "TNDLib/Finite.lean",
        *(f"pilot/TNDLib/Matching/{name}.lean" for name in (
            "Algorithm", "Basic", "Cardinality", "Completion", "History", "Invariants",
            "Measure", "Pilot", "Progress", "Proposal", "Rank", "StableMatch", "Termination",
        )),
    }


@pytest.mark.parametrize("external", ["Mathlib", "Lean", "Unreviewed.Plugin"])
def test_external_import_cannot_enter_the_maintained_closure(external):
    policy = small_policy()
    policy["source_files"][1]["imports"] = [external]
    with pytest.raises(ValueError, match="unapproved external"):
        snapshot.validate_policy(policy)


def test_cycles_and_unreachable_modules_are_refused():
    cycle = small_policy()
    cycle["source_files"][1]["imports"] = [snapshot.MODULE]
    with pytest.raises(ValueError, match="cycle"):
        snapshot.validate_policy(cycle)
    unreachable = small_policy()
    unreachable["source_files"].append({
        "module_name": "TNDLib.Matching.Orphan",
        "path": "pilot/TNDLib/Matching/Orphan.lean",
        "imports": ["Init"],
    })
    with pytest.raises(ValueError, match="unreachable"):
        snapshot.validate_policy(unreachable)


@pytest.mark.parametrize("duplicate", ["module", "path", "both"])
def test_duplicate_inventory_entries_are_refused(duplicate):
    policy = small_policy()
    extra = copy.deepcopy(policy["source_files"][1])
    if duplicate == "module":
        extra["path"] = "pilot/TNDLib/Matching/Other.lean"
    elif duplicate == "path":
        extra["module_name"] = "TNDLib.Matching.Other"
    policy["source_files"].append(extra)
    with pytest.raises(ValueError, match="duplicate"):
        snapshot.validate_policy(policy)


def test_module_path_disagreement_and_duplicate_imports_are_refused():
    mismatched = small_policy()
    mismatched["source_files"][1]["path"] = "pilot/TNDLib/Matching/Other.lean"
    with pytest.raises(ValueError, match="source path or import"):
        snapshot.validate_policy(mismatched)
    repeated = small_policy()
    repeated["source_files"][0]["imports"] *= 2
    with pytest.raises(ValueError, match="source path or import"):
        snapshot.validate_policy(repeated)


def test_exact_frozen_snapshot_stages_only_fourteen_sources_and_maintained_config(tmp_path):
    revision = subprocess.run(
        ["git", "-C", str(PROJECT), "cat-file", "-e", f"{FROZEN_REVISION}^{{commit}}"],
        capture_output=True, check=False,
    )
    if revision.returncode:
        pytest.skip("frozen integration commit is absent from this shallow/source-only checkout")
    specs = snapshot.validate_policy(
        json.loads((PROJECT / "audit/matching/source-policy.json").read_text()),
    )
    hashes = snapshot.stage(FROZEN_REVISION, specs, tmp_path)
    paths = {spec["path"] for spec in specs}
    assert set(hashes) == paths
    assert {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file()} == (
        paths | {"lakefile.toml", "lean-toolchain"}
    )
    for path in paths:
        original = subprocess.check_output(
            ["git", "-C", str(PROJECT), "show", f"{FROZEN_REVISION}:{path}"],
        )
        assert (tmp_path / path).read_bytes() == original
        assert hashes[path] == hashlib.sha256(original).hexdigest()
    assert (tmp_path / "lakefile.toml").read_bytes() == (PROJECT / "lakefile.toml").read_bytes()
    assert (tmp_path / "lean-toolchain").read_bytes() == (PROJECT / "lean-toolchain").read_bytes()


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    repo = tmp_path / "candidate"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Matching source fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Matching source fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], env=env).decode().strip()

    git("init", "-q")
    for spec in small_policy()["source_files"]:
        path = repo / spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import Init\n")
    (repo / "lakefile.toml").write_text('name = "trusted-fixture"\n')
    (repo / "lean-toolchain").write_text("leanprover/lean4:v4.35.0\n")

    def commit():
        git("add", "-A")
        git("commit", "-qm", "Candidate fixture")
        return git("rev-parse", "HEAD")

    monkeypatch.setattr(snapshot, "ROOT", repo)
    return repo, git, commit


@pytest.mark.parametrize("mode", ["symlink", "executable"])
def test_candidate_source_must_be_regular_nonexecutable_git_blob(candidate, tmp_path, mode):
    repo, git, commit = candidate
    source = repo / "pilot/TNDLib/Matching/Dependency.lean"
    if mode == "symlink":
        source.unlink()
        source.symlink_to("../../../lakefile.toml")
    else:
        source.chmod(0o755)
    revision = commit()
    assert git("ls-tree", revision, "--", str(source.relative_to(repo))).startswith(
        "120000" if mode == "symlink" else "100755",
    )
    with pytest.raises(ValueError, match="unapproved pilot file or file mode"):
        snapshot.stage(revision, small_policy()["source_files"], tmp_path / "staged")


@pytest.mark.parametrize("unexpected", ["Extra.lean", "Plugin.so", "Basic.olean"])
def test_unexpected_pilot_files_are_rejected_even_if_never_imported(
    candidate, tmp_path, unexpected,
):
    repo, _, commit = candidate
    (repo / "pilot/TNDLib/Matching" / unexpected).write_bytes(b"unreviewed candidate bytes")
    revision = commit()
    with pytest.raises(ValueError, match="unapproved pilot file"):
        snapshot.stage(revision, small_policy()["source_files"], tmp_path / "staged")


def test_candidate_config_and_dependency_payloads_never_enter_staged_snapshot(candidate, tmp_path):
    repo, _, commit = candidate
    malicious = b'name = "candidate"\n[[require]]\nname = "Mathlib"\n'
    (repo / "lakefile.toml").write_bytes(malicious)
    (repo / "lake-manifest.json").write_text('{"packages": [{"name": "plugin"}]}')
    payload = repo / ".lake/packages/plugin/Plugin.olean"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"unreviewed binary")
    revision = commit()
    # Maintained configuration belongs to the trusted checkout, never the candidate.
    trusted = b'name = "maintained"\n'
    (repo / "lakefile.toml").write_bytes(trusted)
    staged = tmp_path / "staged"
    staged.mkdir()
    hashes = snapshot.stage(revision, small_policy()["source_files"], staged)
    assert len(hashes) == 2
    assert (staged / "lakefile.toml").read_bytes() == trusted
    assert {str(path.relative_to(staged)) for path in staged.rglob("*") if path.is_file()} == {
        "pilot/TNDLib/Matching/Pilot.lean", "pilot/TNDLib/Matching/Dependency.lean",
        "lakefile.toml", "lean-toolchain",
    }


@pytest.mark.parametrize("size", [0, snapshot.MAX_FILE + 1])
def test_file_size_is_checked_before_reading_the_candidate_blob(
    candidate, tmp_path, monkeypatch, size,
):
    repo, _, commit = candidate
    (repo / "pilot/TNDLib/Matching/Dependency.lean").write_bytes(b"x" * size)
    revision = commit()
    calls = []
    original = snapshot.git

    def observed(*args):
        calls.append(args)
        if args[:2] == ("cat-file", "blob"):
            pytest.fail("source blob was read before its oversized/empty length was rejected")
        return original(*args)

    monkeypatch.setattr(snapshot, "git", observed)
    with pytest.raises(ValueError, match="per-file limit"):
        snapshot.stage(revision, small_policy()["source_files"], tmp_path / "staged")
    assert any(args[:2] == ("cat-file", "-s") for args in calls)
