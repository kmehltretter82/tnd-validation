"""Prevent validation-profile leakage into an exact production candidate snapshot."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gate.verify.production_profile import check_repository, require_development_profile

APPROVED = {
    "schema_version": 1,
    "source_binding_validated": False,
    "resource_boundary_validated": False,
    "resource_limits": None,
    "reason": "Certification awaits an explicit evidence review.",
}


def test_approved_uncertified_policy_is_accepted():
    require_development_profile(APPROVED)


@pytest.mark.parametrize(
    "change",
    [
        {"source_binding_validated": True},
        {"resource_boundary_validated": True},
        {"source_binding_validated": 0},
        {"resource_boundary_validated": "false"},
        {"schema_version": True},
        {"resource_limits": {"build_bytes": 2**30}},
        {"reason": ""},
        {"test_only": True},
    ],
)
def test_validation_flags_limits_and_ambiguous_values_are_refused(change):
    with pytest.raises(ValueError, match="uncertified profile"):
        require_development_profile({**APPROVED, **change})


def test_missing_policy_and_duplicate_fields_are_refused(tmp_path):
    with pytest.raises(OSError):
        check_repository(tmp_path)
    policy = tmp_path / ".choir/certification.json"
    policy.parent.mkdir()
    policy.write_text('{"source_binding_validated": true, "source_binding_validated": false}')
    with pytest.raises(ValueError, match="duplicate"):
        check_repository(tmp_path)


def test_exact_commit_check_cannot_be_fooled_by_replacing_worktree_policy(tmp_path):
    policy = tmp_path / ".choir/certification.json"
    policy.parent.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Profile fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Profile fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }

    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], env=env).decode()

    git("init", "-q")
    policy.write_text(json.dumps(APPROVED))
    git("add", ".choir/certification.json")
    git("commit", "-qm", "Approved production development profile")
    approved_revision = git("rev-parse", "HEAD").strip()
    check_repository(tmp_path, approved_revision)

    policy.write_text(json.dumps({**APPROVED, "source_binding_validated": True}))
    git("add", ".choir/certification.json")
    git("commit", "-qm", "Unreviewed validation profile")
    validation_revision = git("rev-parse", "HEAD").strip()
    # A safe-looking worktree cannot hide the committed validation flags.
    policy.write_text(json.dumps(APPROVED))
    check_repository(tmp_path)
    with pytest.raises(ValueError, match="uncertified profile"):
        check_repository(tmp_path, validation_revision)
    check_repository(tmp_path, approved_revision)


def test_nonimmutable_revision_is_refused(tmp_path):
    with pytest.raises(ValueError, match="full lowercase Git commit SHA"):
        check_repository(Path(tmp_path), "main")
