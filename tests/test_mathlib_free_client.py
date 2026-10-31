"""Claiming a task in this Mathlib-free project must not reach for Mathlib."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from client import mathlib_cache
from client.build_store import format_cache_report
from client.tooling import read_tools_recommendation


def unreachable(_workspace):
    raise AssertionError("no dependency fetch for a manifest with no packages")


def test_this_repository_locks_no_packages_and_fetches_nothing():
    assert json.loads(Path("lake-manifest.json").read_text())["packages"] == []
    assert mathlib_cache.prepare_workspace_deps(Path("."), cache_get=unreachable) == "no-deps"


def test_this_repository_opts_out_of_the_mathlib_search_advisory():
    assert read_tools_recommendation(Path(".")) == "off"


def test_no_deps_outcome_adds_no_claim_advisory():
    assert format_cache_report({"deps": "no-deps"}) == ""


@pytest.mark.parametrize(
    "manifest",
    [
        "{not json", "[]", '{"version": "1.3.0"}', '{"packages": null}',
        '{"packages": [{"name": "x"}]}',
    ],
)
def test_anything_but_an_explicit_empty_list_keeps_the_normal_path(tmp_path, monkeypatch, manifest):
    (tmp_path / "lake-manifest.json").write_text(manifest)
    monkeypatch.setattr(mathlib_cache, "store_root", lambda: tmp_path / "store")
    fetched = []

    def fetch(workspace):
        fetched.append(workspace)
        return False

    assert mathlib_cache.prepare_workspace_deps(tmp_path, cache_get=fetch) == "skipped"
    assert fetched == [tmp_path]
