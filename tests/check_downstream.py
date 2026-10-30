#!/usr/bin/env python3
"""Exercise an exact Git-pinned Lake consumer and reject transitive packages."""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = ("lean-toolchain", "lakefile.toml", "lake-manifest.json", "TNDLib.lean")


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> bytes:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=True,
        timeout=300,
        capture_output=True,
    ).stdout


def main() -> None:
    # Resolve the selected Lake executable before changing into the temporary
    # consumer. A relative PATH entry would otherwise be reinterpreted from the
    # consumer directory and could silently select a different elan toolchain.
    lake = shutil.which("lake")
    if lake is None:
        raise SystemExit("lake is not available")
    lake = str(Path(lake).resolve())
    with tempfile.TemporaryDirectory(prefix="tndlib-downstream-") as directory:
        root = Path(directory)
        library, consumer = root / "tndlib", root / "consumer"
        library.mkdir()
        consumer.mkdir()
        for name in SOURCE_FILES:
            shutil.copy2(ROOT / name, library / name)
        shutil.copytree(ROOT / "TNDLib", library / "TNDLib")
        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "TND downstream fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "TND downstream fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
        run(["git", "init", "-q", "--initial-branch=main"], cwd=library, env=git_env)
        run(["git", "add", "--", *SOURCE_FILES, "TNDLib"], cwd=library, env=git_env)
        run(
            ["git", "commit", "-qm", "Exact tndlib downstream fixture"],
            cwd=library,
            env=git_env,
        )
        revision = run(["git", "rev-parse", "HEAD"], cwd=library, env=git_env).decode().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise SystemExit("Temporary library did not produce a full Git revision")
        repository = library.resolve().as_uri()

        (consumer / "lean-toolchain").write_text((ROOT / "lean-toolchain").read_text())
        (consumer / "lakefile.toml").write_text(
            f'name = "tnd-consumer-check"\ndefaultTargets = ["Consumer"]\n\n'
            f'[[require]]\nname = "tndlib"\ngit = "{repository}"\nrev = "{revision}"\n\n'
            f'[[lean_lib]]\nname = "Consumer"\n'
        )
        (consumer / "Consumer.lean").write_text(
            "import TNDLib\n\nexample : TNDLib.Nat.sumTo 3 = 6 := rfl\n"
        )
        subprocess.run(
            [lake, "build"],
            cwd=consumer,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=True,
            timeout=300,
        )
        library_packages = json.loads((library / "lake-manifest.json").read_text())["packages"]
        consumer_packages = json.loads((consumer / "lake-manifest.json").read_text())["packages"]
        # The initial baseline permits no external packages. This is stricter
        # than checking a package name or URL, which a Mathlib fork could rename.
        # Deliberate future dependencies require an explicit policy/test review.
        if library_packages:
            raise SystemExit("The initial library baseline must have no external packages")
        if (
            len(consumer_packages) != 1
            or consumer_packages[0].get("name") != "tndlib"
            or consumer_packages[0].get("type") != "git"
            or consumer_packages[0].get("url") != repository
            or consumer_packages[0].get("inputRev") != revision
            or consumer_packages[0].get("rev") != revision
        ):
            raise SystemExit("Consumer resolved unexpected transitive packages")
        checkout = consumer / ".lake/packages/tndlib"
        resolved = run(["git", "rev-parse", "HEAD"], cwd=checkout, env=git_env).decode().strip()
        nested_packages = json.loads((checkout / "lake-manifest.json").read_text())["packages"]
        if resolved != revision or nested_packages:
            raise SystemExit("Consumer did not build the exact dependency-free Git revision")
        print(f"Downstream build succeeded at exact Git revision {revision}; no transitives.")


if __name__ == "__main__":
    main()
