"""Resource limits and provenance checks for the trusted runner."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "tnd_audit_runner", Path(__file__).parents[2] / "audit/run.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class DriverBoundaryTests(unittest.TestCase):
    def setUp(self):
        # CI exports the verified install; these cases select their own source.
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("TND_LEAN_ROOT", None)

    def test_certification_requires_validated_exact_resource_limits(self):
        quota = {
            "schema_version": 1,
            "build_bytes": 65536,
            "build_inodes": 64,
            "export_bytes": 65536,
            "export_inodes": 64,
        }
        policy = {
            "schema_version": 1,
            "source_binding_validated": True,
            "resource_boundary_validated": True,
            "resource_limits": quota,
        }
        build, export = runner.certified_resource_limits(policy)
        self.assertEqual((build.bytes, build.inodes), (65536, 64))
        self.assertEqual((export.bytes, export.inodes), (65536, 64))
        for invalid in (
            {**policy, "schema_version": True},
            {**policy, "resource_boundary_validated": False},
            {**policy, "resource_limits": None},
            {**policy, "resource_limits": {**quota, "schema_version": True}},
            {**policy, "resource_limits": {**quota, "extra": 1}},
            {**policy, "resource_limits": {**quota, "build_bytes": True}},
            {**policy, "resource_limits": {**quota, "build_bytes": 0}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                runner.certified_resource_limits(invalid)

    def test_pinned_lean_resolution_uses_supported_elan_run_and_sanitized_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin/lean"
            binary.parent.mkdir()
            binary.write_text("trusted fixture")
            binary.chmod(0o755)
            calls = []

            def run(args, **kwargs):
                calls.append((args, kwargs))
                if args[0] == "elan":
                    return SimpleNamespace(stdout=str(root) + "\n")
                if args[-1] == "--print-prefix":
                    return SimpleNamespace(stdout=str(root) + "\n")
                if args[-1] == "--version":
                    return SimpleNamespace(stdout="Lean (version 4.35.0, Release)\n")
                raise AssertionError(args)

            poison = {"ELAN_TOOLCHAIN": "wrong", "LEAN_SYSROOT": "/wrong", "LEAN_PATH": "/wrong"}
            with patch.dict(os.environ, poison), patch.object(runner, "command", side_effect=run):
                self.assertEqual(runner.pinned_lean_root(), root.resolve())
            self.assertEqual(
                calls[0][0], ["elan", "run", runner.TOOLCHAIN, "lean", "--print-prefix"]
            )
            for _, kwargs in calls:
                self.assertTrue(kwargs["text"])
                for name in poison:
                    self.assertNotIn(name, kwargs["env"])

    def test_verified_ci_install_is_validated_without_consulting_elan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binary = root / "bin/lean"
            binary.parent.mkdir()
            binary.write_text("trusted fixture")
            binary.chmod(0o755)
            calls = []

            def run(args, **kwargs):
                calls.append((args, kwargs))
                if args[0] == "elan":
                    raise AssertionError("elan must not select the verified install")
                if args[-1] == "--print-prefix":
                    return SimpleNamespace(stdout=str(root) + "\n")
                return SimpleNamespace(stdout="Lean (version 4.35.0, Release)\n")

            with (
                patch.dict(os.environ, {"TND_LEAN_ROOT": str(root)}),
                patch.object(runner, "command", side_effect=run),
            ):
                self.assertEqual(runner.pinned_lean_root(), root)
            self.assertEqual(calls[0][0], [str(binary), "--print-prefix"])
            self.assertNotIn("TND_LEAN_ROOT", calls[0][1]["env"])

    def test_verified_ci_install_must_still_pass_every_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for value in ("", "relative/lean", f"{root}\n/other", str(root / "missing")):
                with (
                    self.subTest(value=value),
                    patch.dict(os.environ, {"TND_LEAN_ROOT": value}),
                    patch.object(runner, "command", side_effect=AssertionError("not reached")),
                    self.assertRaises(ValueError),
                ):
                    runner.pinned_lean_root()

    def test_pinned_lean_rejects_bad_prefixes_wrong_version_and_escaped_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin/lean"
            binary.parent.mkdir()
            binary.write_text("trusted fixture")
            binary.chmod(0o755)

            def answers(prefix, reported, version):
                return [
                    SimpleNamespace(stdout=prefix),
                    SimpleNamespace(stdout=reported),
                    SimpleNamespace(stdout=version),
                ]

            for prefix in ("", "relative/path", "/tmp/a\n/tmp/b"):
                with (
                    self.subTest(prefix=prefix),
                    patch.object(runner, "command", return_value=SimpleNamespace(stdout=prefix)),
                    self.assertRaisesRegex(ValueError, "invalid Lean toolchain prefix"),
                ):
                    runner.pinned_lean_root()
            with (
                patch.object(runner, "command", side_effect=answers(str(root), "/tmp/other", "")),
                self.assertRaisesRegex(ValueError, "different toolchain prefix"),
            ):
                runner.pinned_lean_root()
            for version in ("Lean (version 4.34.0, Release)", "Lean (version 4.35.0-rc1, Release)"):
                with (
                    self.subTest(version=version),
                    patch.object(
                        runner, "command", side_effect=answers(str(root), str(root), version)
                    ),
                    self.assertRaisesRegex(ValueError, "does not match 4.35.0"),
                ):
                    runner.pinned_lean_root()
            binary.unlink()
            target = root / "outside"
            target.write_text("untrusted fixture")
            target.chmod(0o755)
            binary.symlink_to(target)
            with (
                patch.object(runner, "command", return_value=SimpleNamespace(stdout=str(root))),
                self.assertRaisesRegex(ValueError, "outside its toolchain"),
            ):
                runner.pinned_lean_root()

    def test_isolated_python_can_start_runner_outside_repository(self):
        script = Path(__file__).resolve().parents[2] / "audit/run.py"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", str(script), "--help"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_unvalidated_source_binding_disables_production(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / ".choir").mkdir()
            (path / ".choir/certification.json").write_text('{"source_binding_validated": false}')
            with (
                patch.object(runner.platform, "system", return_value="Linux"),
                patch.object(runner.os, "getuid", return_value=1000),
                self.assertRaisesRegex(ValueError, "production certification is disabled"),
            ):
                runner.verify(SimpleNamespace(repo=path))

    def test_bounded_build_export_closes_quota_before_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scratch = root / "scratch"
            scratch.mkdir()
            events = []
            testcase = self

            class FakeBoundary:
                def record_container(self, _name):
                    pass

                def __init__(self, parent, build, export):
                    testcase.assertEqual(parent, root)
                    testcase.assertEqual((build.bytes, export.inodes), (65536, 64))
                    self.paths = {name: root / name for name in ("build", "export")}
                    for path in self.paths.values():
                        path.mkdir()

                def __enter__(self):
                    events.append("mount")
                    return self

                def verify(self, name):
                    events.append("verify-" + name)
                    return self.paths[name]

                def close(self):
                    testcase.assertFalse((scratch / "checked-input.ndjson").exists())
                    events.append("unmount")

            def execute(args):
                events.append("run")
                if "/opt/tnd-export" in args[-1]:
                    (root / "export/export.ndjson").write_bytes(b"{}\n")
                return subprocess.CompletedProcess(args, 0, b"", b"")

            def cleanup(_name):
                events.append("reap")

            limit = runner.resource_boundary.Limits(65536, 64)
            with (
                patch.object(runner.resource_boundary, "ExperimentalBoundary", FakeBoundary),
                patch.object(runner, "require_default_seccomp"),
                patch.object(runner, "command", side_effect=execute),
                patch.object(runner, "ensure_container_removed", side_effect=cleanup),
            ):
                result = runner.bounded_build_export(
                    runner.IMAGE, root, scratch, root, root, root, limit, limit
                )
            self.assertEqual(result.read_bytes(), b"{}\n")
            self.assertEqual(result.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                [event for event in events if event in {"run", "reap", "unmount"}],
                ["run", "reap", "run", "reap", "unmount"],
            )

    def test_bounded_build_export_retains_mounts_when_cleanup_is_uncertain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scratch = root / "scratch"
            scratch.mkdir()
            closed = []

            class FakeBoundary:
                def record_container(self, _name):
                    pass

                def __init__(self, *_args):
                    self.paths = {name: root / name for name in ("build", "export")}
                    for path in self.paths.values():
                        path.mkdir()

                def __enter__(self):
                    return self

                def verify(self, name):
                    return self.paths[name]

                def close(self):
                    closed.append(True)

            limit = runner.resource_boundary.Limits(65536, 64)
            with (
                patch.object(runner.resource_boundary, "ExperimentalBoundary", FakeBoundary),
                patch.object(runner, "require_default_seccomp"),
                patch.object(runner, "command"),
                patch.object(
                    runner,
                    "ensure_container_removed",
                    side_effect=ValueError("daemon unavailable"),
                ),
                self.assertRaisesRegex(ValueError, "mounts retained"),
            ):
                runner.bounded_build_export(
                    runner.IMAGE, root, scratch, root, root, root, limit, limit
                )
            self.assertEqual(closed, [])
            self.assertFalse((scratch / "checked-input.ndjson").exists())

    def test_subprocess_output_flood_is_stopped(self):
        with self.assertRaisesRegex(ValueError, "output exceeded"):
            runner.command(
                [sys.executable, "-c", "import os\nwhile True: os.write(1, b'x' * 65536)"]
            )

    def test_binary_output_is_preserved(self):
        result = runner.command([sys.executable, "-c", "import os; os.write(1, bytes(range(256)))"])
        self.assertEqual(result.stdout, bytes(range(256)))

    def test_source_link_must_name_verified_input(self):
        proof = {"declarations": [{"name": "TNDLib.foo", "source_path": "TNDLib/Foo.lean"}]}
        inventory = {"source_paths": {"TNDLib.foo": "TNDLib/Foo.lean"}}
        with self.assertRaisesRegex(ValueError, "missing approved source"):
            runner.bind_declarations(proof, inventory, {"TNDLib.lean": "hash"}, "a" * 40)

    def test_shared_checker_boundary_requires_development_wrapper_and_matching_toolchain(self):
        proof = {"status": "verified-proof-objects", "toolchain": "4.35.0", "declarations": []}
        wrapper = {
            "status": "development-proof-check",
            "development_only": True,
            "proof_check": proof,
        }
        path = Path("/trusted")
        with patch.object(
            runner.checker_sandbox, "run_isolated_checker", return_value=wrapper
        ) as run:
            self.assertEqual(runner.check_proof(runner.IMAGE, path, path, path, path, path), proof)
            self.assertIs(run.call_args.kwargs["check_seccomp"], runner.require_default_seccomp)
            self.assertIs(run.call_args.kwargs["cleanup"], runner.ensure_container_removed)
        for invalid in (
            {"status": "verified-proof-objects", "proof_check": proof},
            {"status": "development-proof-check", "development_only": False, "proof_check": proof},
            {"status": "development-proof-check", "development_only": True, "proof_check": {}},
            {
                "status": "development-proof-check",
                "development_only": True,
                "proof_check": {"status": "verified-proof-objects", "toolchain": "4.33.1"},
            },
        ):
            with (
                patch.object(runner.checker_sandbox, "run_isolated_checker", return_value=invalid),
                self.assertRaises(ValueError),
            ):
                runner.check_proof(runner.IMAGE, path, path, path, path, path)

    def test_task_verification_uses_shared_isolated_checker_and_binds_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "audit"
            audit.mkdir()
            (audit / "tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "map_exists",
                                "source_path": "tasks/map_exists.lean",
                                "namespace_name": "TNDTask",
                                "expected_exports": ["TNDTask.mapExists"],
                            }
                        ]
                    }
                )
            )
            base, head = "a" * 40, "b" * 40
            args = SimpleNamespace(base=base, head=head, image=runner.IMAGE)
            proof = {
                "status": "verified-proof-objects",
                "toolchain": "4.35.0",
                "declarations": [
                    {"name": "TNDTask.mapExists", "source_path": "tasks/map_exists.lean"}
                ],
            }

            def snapshot(repo, revision, scratch, lean_root, task, role, image):
                scratch.mkdir()
                source = scratch / "source"
                source.mkdir()
                return source, {"tasks/map_exists.lean": revision}, {"source_sha256": {}}

            def export(image, source, scratch, lean_root, exporter, module, namespace):
                result = scratch / "proof.ndjson"
                result.write_text("{}\n")
                return result

            with (
                patch.object(runner, "git", return_value=b"tasks/map_exists.lean\0"),
                patch.object(runner, "admitted_snapshot", side_effect=snapshot),
                patch.object(runner.admission, "verify_exact"),
                patch.object(runner, "check_proof", return_value=proof) as check,
            ):
                reports = runner.verify_tasks(args, root, audit, root, root, root, root, export)
            check.assert_called_once()
            self.assertEqual(check.call_args.args[2].parent.name, "task-map_exists-base")
            self.assertEqual(check.call_args.args[3].parent.name, "task-map_exists-head")
            self.assertEqual(reports[0]["proof_check"]["declarations"][0]["source_sha"], head)
            self.assertEqual(
                reports[0]["proof_check"]["declarations"][0]["source_blob_sha256"], head
            )

    def test_mutable_image_tag_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
                runner.docker_arguments("ubuntu:latest", path, path, path, path, path)
            for image in ("ubuntu@sha256:" + "a" * 64, "--env=BAD@sha256:" + "a" * 64):
                with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
                    runner.docker_arguments(image, path, path, path, path, path)

    def test_module_name_cannot_inject_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, "invalid trusted module"):
                runner.docker_arguments(
                    runner.IMAGE, path, path, path, path, path, module="Task; touch /output/forged"
                )

    def test_git_snapshot_rejects_unapproved_top_level_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)

            def git(repo, *args):
                if args[:2] == ("cat-file", "-e"):
                    return b""
                if args[:3] == ("ls-tree", "-rz", "--name-only"):
                    return b"TNDLib.lean\0Foo.lean\0"
                if args[:2] == ("ls-tree", "-z"):
                    name = args[-1]
                    return f"100644 blob {name}\t{name}\0".encode()
                if args[:2] == ("cat-file", "blob"):
                    return runner.PUBLISHED_PACKAGE[args[-1]]
                raise AssertionError(args)

            with (
                patch.object(runner, "git", side_effect=git),
                self.assertRaisesRegex(ValueError, "unapproved Lean source"),
            ):
                runner.source_snapshot(path, "a" * 40, path)

    def test_real_git_snapshot_rejects_additional_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, target = root / "repo", root / "copy"
            repo.mkdir()
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "TNDLib.lean").write_text("import Init\n")
            (repo / "Other.lean").write_text("axiom TNDLib.hidden : False\n")
            for name, content in runner.PUBLISHED_PACKAGE.items():
                (repo / name).write_bytes(content)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            with self.assertRaisesRegex(ValueError, "Other.lean"):
                runner.source_snapshot(repo, sha, target)

    def test_published_package_policy_rejects_unchecked_build_configuration(self):
        mutations = {
            "alternate lakefile": ("lakefile.lean", b"import Lake\nopen Lake DSL\npackage rogue\n"),
            "extra library root": (
                "lakefile.toml",
                runner.PUBLISHED_PACKAGE["lakefile.toml"] + b'\n[[lean_lib]]\nname = "Evil"\n',
            ),
            "extra dependency": (
                "lake-manifest.json",
                b'{"name":"tndlib","packages":[{"name":"mathlib"}]}\n',
            ),
            "changed toolchain": ("lean-toolchain", b"leanprover/lean4:v4.33.1\n"),
            "tracked build artifact": (".lake/build/lib/lean/TNDLib.olean", b"forged"),
            "tracked build symlink": (".lake", None),
        }
        for case, (filename, contents) in mutations.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, target = root / "repo", root / "snapshot"
                repo.mkdir()
                target.mkdir()
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                (repo / "TNDLib.lean").write_text("import Init\n")
                for name, content in runner.PUBLISHED_PACKAGE.items():
                    (repo / name).write_bytes(content)
                changed = repo / filename
                changed.parent.mkdir(parents=True, exist_ok=True)
                if contents is None:
                    changed.symlink_to("/tmp/forged-build")
                else:
                    changed.write_bytes(contents)
                subprocess.run(["git", "-C", str(repo), "add", "-f", "."], check=True)
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "-c",
                        "user.name=Fixture",
                        "-c",
                        "user.email=fixture@example.invalid",
                        "commit",
                        "-qm",
                        "fixture",
                    ],
                    check=True,
                )
                sha = subprocess.check_output(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
                ).strip()
                with self.assertRaisesRegex(ValueError, "package|Lake|artifacts"):
                    runner.source_snapshot(repo, sha, target)

    def test_published_package_policy_accepts_exact_package_from_git(self):
        project = Path(__file__).parents[2]
        for name, expected in runner.PUBLISHED_PACKAGE.items():
            self.assertEqual((project / name).read_bytes(), expected, name)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, target = root / "repo", root / "snapshot"
            repo.mkdir()
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            policy, _ = runner.admission.policy_for()
            for entry in policy["source_files"]:
                source = repo / entry["path"]
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("import Init\n")
            for name, content in runner.PUBLISHED_PACKAGE.items():
                (repo / name).write_bytes(content)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            self.assertEqual(
                runner.source_snapshot(repo, sha, target)["TNDLib.lean"],
                hashlib.sha256(b"import Init\n").hexdigest(),
            )

    def test_snapshot_rejects_extra_library_file_before_staging_candidate_blobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, target = root / "repo", root / "snapshot"
            repo.mkdir()
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            policy, _ = runner.admission.policy_for()
            for entry in policy["source_files"]:
                source = repo / entry["path"]
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("import Init\n")
            (repo / "TNDLib/Extra.lean").write_text("import Init\n")
            for name, content in runner.PUBLISHED_PACKAGE.items():
                (repo / name).write_bytes(content)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture",
                ],
                check=True,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                runner.source_snapshot(repo, sha, target)
            self.assertEqual(list(target.rglob("*.lean")), [])

    def test_export_stage_cannot_write_build_or_read_reference_material(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            build = runner.docker_arguments(
                runner.IMAGE, path, path, path, path, path, stage="build"
            )
            export = runner.docker_arguments(
                runner.IMAGE, path, path, path, path, path, stage="export"
            )
            self.assertIn(f"type=bind,src={path},dst=/work/.lake", build)
            self.assertIn(f"type=bind,src={path},dst=/work/.lake,readonly", export)
            self.assertFalse(any("dst=/opt/tnd-export" in arg for arg in build))
            self.assertTrue(any("dst=/opt/tnd-export,readonly" in arg for arg in export))
            self.assertFalse(any("dst=/output" in arg for arg in build))
            self.assertTrue(any("dst=/output" in arg for arg in export))
            self.assertNotIn("lake env", export[-1])
            for args in (build, export):
                self.assertIn("--pull=never", args)
                for option, value in (
                    ("--memory", "2g"),
                    ("--memory-swap", "2g"),
                    ("--shm-size", "64m"),
                    ("--log-driver", "none"),
                ):
                    self.assertEqual(args[args.index(option) + 1], value)
                self.assertFalse(any("seccomp=" in arg or arg == "--privileged" for arg in args))

    def test_seccomp_requires_unambiguous_builtin_profile(self):
        valid = ["name=seccomp,profile=builtin", "name=cgroupns"]
        with patch.object(runner, "command") as query:
            query.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(valid))
            runner.require_default_seccomp()
            query.assert_called_once_with(
                ["docker", "info", "--format", "{{json .SecurityOptions}}"], text=True
            )
            for options in (
                [],
                None,
                {},
                [None],
                ["name=seccomp,profile=unconfined"],
                ["name=seccomp,profile=default"],
                ["name=seccomp,profile=/custom"],
                [*valid, "name=seccomp,profile=unconfined"],
                [*valid, "name=seccomp,profile=builtin"],
            ):
                query.return_value.stdout = json.dumps(options)
                with self.subTest(options=options), self.assertRaises(ValueError):
                    runner.require_default_seccomp()
            query.return_value.stdout = "not json"
            with self.assertRaises(ValueError):
                runner.require_default_seccomp()
            query.side_effect = OSError("daemon unavailable")
            with self.assertRaises(ValueError):
                runner.require_default_seccomp()

    def test_failed_seccomp_preflight_prevents_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (
                patch.object(runner, "require_default_seccomp", side_effect=ValueError("seccomp")),
                patch.object(runner, "command") as run,
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaisesRegex(ValueError, "seccomp"),
            ):
                runner.build_export(runner.IMAGE, path, path, path, path)
            run.assert_not_called()
            cleanup.assert_not_called()

    def test_seccomp_rechecked_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (
                patch.object(
                    runner, "require_default_seccomp", side_effect=[None, ValueError("seccomp")]
                ) as check,
                patch.object(runner, "command") as run,
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaisesRegex(ValueError, "seccomp"),
            ):
                runner.build_export(runner.IMAGE, path, path, path, path)
            self.assertEqual(check.call_count, 2)
            run.assert_called_once()
            cleanup.assert_called_once()

    def test_build_is_reaped_before_read_only_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            events = []

            def execute(args):
                events.append(("run", args[-1]))
                if "/opt/tnd-export" in args[-1]:
                    (path / "output/export.ndjson").write_bytes(b"{}\n")

            def reap(name):
                events.append(("reap", name))

            with (
                patch.object(runner, "command", side_effect=execute),
                patch.object(runner, "require_default_seccomp"),
                patch.object(runner, "ensure_container_removed", side_effect=reap),
            ):
                result = runner.build_export(runner.IMAGE, path, path, path, path)
            self.assertEqual([item[0] for item in events], ["run", "reap", "run", "reap"])
            self.assertIn("lake build", events[0][1])
            self.assertIn("/opt/tnd-export", events[2][1])
            self.assertNotEqual(events[1][1], events[3][1])
            self.assertEqual(result.read_bytes(), b"{}\n")

    def test_failed_build_never_starts_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (
                patch.object(runner, "command", side_effect=ValueError("build failed")) as run,
                patch.object(runner, "require_default_seccomp"),
                patch.object(runner, "ensure_container_removed") as reap,
                self.assertRaisesRegex(ValueError, "build failed"),
            ):
                runner.build_export(runner.IMAGE, path, path, path, path)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(reap.call_count, 1)

    def test_cleanup_failure_blocks_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (
                patch.object(runner, "command") as run,
                patch.object(runner, "require_default_seccomp"),
                patch.object(
                    runner, "ensure_container_removed", side_effect=ValueError("still running")
                ),
                self.assertRaisesRegex(ValueError, "still running"),
            ):
                runner.build_export(runner.IMAGE, path, path, path, path)
            self.assertEqual(run.call_count, 1)

    def test_container_absence_requires_successful_docker_query(self):
        with patch.object(runner.subprocess, "run"), patch.object(runner, "command") as query:
            query.return_value = subprocess.CompletedProcess([], 0, stdout="tnd-audit-test\n")
            with self.assertRaisesRegex(ValueError, "cleanup did not remove"):
                runner.ensure_container_removed("tnd-audit-test")
            query.side_effect = subprocess.CalledProcessError(1, ["docker"])
            with self.assertRaises(subprocess.CalledProcessError):
                runner.ensure_container_removed("tnd-audit-test")

    def test_git_task_hash_is_bound_to_admitted_task_and_original_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = b"task source"
            seen = {}

            def snapshot(repo, revision, raw):
                (raw / "TNDLib.lean").write_bytes(b"library")
                return {"TNDLib.lean": hashlib.sha256(b"library").hexdigest()}

            def git(repo, *args):
                if args[0] == "ls-tree":
                    return b"100644 blob 1234\ttasks/map_exists.lean\n"
                if args[:2] == ("cat-file", "blob"):
                    return original
                raise AssertionError(args)

            def admit(raw, source, lean_root, **kwargs):
                seen.update(kwargs)
                self.assertEqual((raw / "Task.lean").read_bytes(), original)
                self.assertEqual(lean_root, root)
                source.mkdir()
                return {
                    "source_sha256": kwargs["expected_hashes"],
                    "task": {"source_path": "tasks/map_exists.lean"},
                }

            task = {"id": "map_exists", "source_path": "tasks/map_exists.lean"}
            with (
                patch.object(runner, "source_snapshot", side_effect=snapshot),
                patch.object(runner, "git", side_effect=git),
                patch.object(runner.admission, "admit_into") as host_parser,
                patch.object(runner.parser_sandbox, "admit_into_container", side_effect=admit),
            ):
                source, hashes, report = runner.admitted_snapshot(
                    root, "a" * 40, root / "scratch", root, task, "challenge", "custom-image"
                )
            self.assertEqual(seen["role"], "challenge")
            host_parser.assert_not_called()
            self.assertEqual(seen["task_id"], "map_exists")
            self.assertEqual(seen["image"], "custom-image")
            self.assertIs(seen["cleanup"], runner.ensure_container_removed)
            self.assertIs(seen["check_seccomp"], runner.require_default_seccomp)
            self.assertEqual(seen["expected_hashes"]["Task.lean"], hashes["tasks/map_exists.lean"])
            self.assertEqual(report["source_sha256"], seen["expected_hashes"])
            self.assertTrue((source / "lake-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
