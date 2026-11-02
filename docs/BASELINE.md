# Reproducible development baseline, 2026-11-01

This is development evidence. It does not activate certification, approve a
public release, or prove that the source/resource boundaries are complete.
The continuation plan is now being executed locally.

## Frozen snapshots

| Tree | Exact commit | Publication and CI state |
| --- | --- | --- |
| Library initial baseline (`kmehltretter82/tndlib`) | `a76c3fc5516e263229a41eb597e3a7ce9f870c8a` | Initial pre-pilot baseline snapshot. |
| Library pilot & admission commit (`kmehltretter82/tndlib`) | `4eb427483923034000a9825cfd41f5d6a45c6861` | Published to `kmehltretter82/tndlib:main`; triggered initial push runs `41355670225` (`Maintainer Regression`, failed on shallow `fetch-depth: 1` history check) and `41355670224` (`Audit Main`, fails closed while `.choir/certification.json` is disabled). |
| Library CI follow-up (`kmehltretter82/tndlib`) | `3dbcf3013a8350e33c5e9950e0b01539cfc2915d` | Published to `kmehltretter82/tndlib:main` (`fetch-depth: 0` in `maintainer-ci.yml`); passed public `Maintainer Regression` run `41356432624`. |
| Library structural test alignment | `a8a92ecf13427d42fc7a04ec6d02ab8836ccf6c4` | Aligns `tests/test_choir_integration.py` `fetch-depth: 0` assertion with `3dbcf3013a8350e33c5e9950e0b01539cfc2915d`. |
| Platform baseline (`kmehltretter82/und`) | `5c796a47fc4dec9d73b5387b48cb28a50a9bd705` | Initial platform repository baseline. |

These commits capture the source before new mathematical pilot modules. Later
working-tree edits are not retroactively part of this baseline. Reproduction
used local clones with `--no-hardlinks` and detached exact commits, starting
without `.lake` or Python virtual-environment directories.

The local toolchain reported:

```text
Lean (version 4.35.0, arm64-apple-darwin24.6.0, commit eb6cafb7290e8bd5f2937522d8d804f58f02bafc, Release)
```

This reports the installed macOS toolchain; it is not a new verification of
the official Linux archive or hosted-runner isolation. The Python lock selected
CPython 3.12.13 for the library checks. Use `uv run --frozen --extra dev` for
Python checks that import the pinned dependencies; a system Python may lack
PyYAML and is not an equivalent environment.

## Reproduced results

Run from a fresh local clone at the exact library baseline:

```sh
lake build
lake env lean tests/corpus/Examples.lean
python3 tests/check_downstream.py
uv run --frozen --extra dev pytest -q
uv run --frozen --extra dev python -m unittest discover -s tests/audit -p 'test_*.py'
uv run --frozen --extra dev ruff check audit gate orchestrator client choir_cli viz tests
uv lock --check --offline
```

- The clean library build passed (9 Lake jobs), and executable corpus examples
  passed. The exact-Git downstream check passed with only `tndlib` in the
  consumer manifest and no nested or transitive packages. Its temporary source
  snapshot was `f6c3b1ed74dfdae6cdd834b3ddd0e40dd0cc28da`; each invocation creates
  its own temporary commit, so a later invocation may report a different SHA.
- The baseline Pytest run found **one stale test assertion**, with 434 passes,
  three Linux-only skips, and 73 passing subtests. The failing assertion in
  `tests/audit/test_driver.py` expected `schema_version` in the source-admission
  policy; that policy has no such field. The assertion confused admission and
  certification schemas. The audit unittest discovery reproduced that same
  failure (137 tests, three skips).
- Ruff and the frozen offline lock check passed at the frozen baseline.
- Applying only the corrected assertion, the new production-profile guard,
  and its tests to that fresh clone gave **447 Pytest passes, three Linux-only
  skips, and 73 passing subtests**. Audit unittest discovery passed all 137
  discovered tests with the same three skips. Ruff passed on that patched
  baseline. This is evidence for that explicit patch, not an assertion that
  every subsequent pilot edit has passed the full suite.
- The independent checker/exporter, admission boundary, and Linux fixtures
  were not rebuilt or rerun in this baseline subtask. Their earlier evidence
  is recorded separately in [LOCAL-LINUX-EVIDENCE.md](../audit/LOCAL-LINUX-EVIDENCE.md).

At the exact platform baseline, `npm test` passed **32 JavaScript tests and
29 Python tests**. This run did not rerun browser engines or screen-reader
accessibility checks.

## Production and validation policy are different profiles

The production library policy remains:

```json
{
  "schema_version": 1,
  "source_binding_validated": false,
  "resource_boundary_validated": false,
  "resource_limits": null
}
```

The production file additionally contains an explanatory `reason`. Its complete
baseline bytes have SHA-256
`8670e9097989926fe519520b7b6729e88fa90b152ff539fe4eeee878619a6928`.

The **separate public validation repository** at commit
`cf400696f7a7fad9e2cfc2abb9d82594cfb62b8f` deliberately has both flags true and
test budgets (1 GiB/100,000 build inodes; 256 MiB/4,096 export inodes). Its reason
explicitly says these flags certify nothing and must never reach production.
A production-profile test failing against that activated test policy must not
be interpreted as a production certification result or fixed by copying it.

Use maintained code to inspect a proposed production candidate's actual Git
policy blob:

```sh
python3 -m gate.verify.production_profile --repo . --revision FULL_40_CHARACTER_COMMIT_SHA
```

The guard preserves the currently approved uncertified production profile.
It refuses activated flags/limits, ambiguous types or fields, duplicate JSON
keys, and a moving revision such as `main`. Its exact-commit test demonstrates
that a safe-looking uncommitted policy cannot conceal an activated candidate
policy. The guard itself does not authorize certification or replace checking
the exact final publication commit. A future explicit certification decision
must review the guard, policy, and evidence together.

## Other authoritative checks

Read-only API checks on 2026-11-01 confirmed the test repository still has all
eight required contexts pinned to GitHub Actions App 15368, `strict: true`, and
administrator enforcement. Ruleset 26325579 is active, restricts `main`
updates, and lists merge App 5555437 as its sole always-bypass actor.
The merge-lane enable variable is absent.

The App's authentication/wrong-head rejection worked in live run 41345526521.
Run 41345577332 failed during bypass-list verification because GitHub omits
`bypass_actors` on ruleset queries made by a GitHub App installation token with
read-only repository administration permission (`Administration: read`), while
still returning `current_user_can_bypass: "always"` for the Merge App token.
`orchestrator/tnd_verification.py` and `orchestrator/config_audit.py` now
separate owner-side unredacted ruleset auditing (`choir orch audit-merge-config`)
from runtime Merge App self-bypass verification (`current_user_can_bypass == "always"`).

## Selected frozen-input hashes

| Input | SHA-256 at the library baseline |
| --- | --- |
| `lean-toolchain` | `ca5f1f601d34c49079e38d7e7041eb0f2a9c227fbc1df0f404820069a052330c` |
| `lake-manifest.json` | `7c4fe516de6dcbbaafdceca943b4b1d99f854344007cfffd3be3a19dcbc05c4c` |
| `uv.lock` | `5756a4d67d771110bfd1cfd2eeca3ad85bb5e94f98566f95ecb640b89b7c47a9` |
| `audit/admission/policy.json` | `988c6e4da15b76bd9f447100f2ed1030da6d1bafed192d43e81d1b16b158657d` |
| `audit/exports.json` | `f461615043f8c32776cacf363703fb6371db7b5152251923a2f90746d7cfd6e6` |
| `audit/lake-manifest.json` | `5b55b5759e11581d1f6eea58f47acb28aeff2623a64368b64d0cadd09712d3cf` |

The baseline commit is the full source identity; this selected hash table is
an inspection aid. New source, policy, inventory, or documentation edits need
their own final commit and evidence before publication.
