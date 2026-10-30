"""Install the pinned official Lean archive after verifying its exact bytes.

CI must not trust an installer that picks and fetches its own toolchain. This
maintained script names the only acceptable release asset for each supported
Linux architecture, checks its size and SHA-256 before extraction, and refuses
to reuse an existing destination. The digests were read from the official
`leanprover/lean4` GitHub Releases API on 2026-10-30.

It uses only the standard library so it can run before any locked Python
environment exists. A checksum establishes which bytes were installed, not that
those bytes are correct: this is a supply-chain control, not certification.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TOOLCHAIN = b"leanprover/lean4:v4.35.0\n"
RELEASE = "https://github.com/leanprover/lean4/releases/download/v4.35.0"
VERSION = re.compile(r"\bversion 4\.35\.0(?:,|\s|\))")
CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Asset:
    name: str
    size: int
    sha256: str


ASSETS = {
    "x86_64": Asset(
        "lean-4.35.0-linux.tar.zst",
        594481375,
        "7289597a44543246c9227b8cae501767e095ce17f6d448b95fc4a8dc97268f6d",
    ),
    "aarch64": Asset(
        "lean-4.35.0-linux_aarch64.tar.zst",
        594868592,
        "c8f0f8a3920e839718b1343e6781fd80a3e9b1024fbcd7078eb30f54e806b028",
    ),
}


def select_asset(system: str, machine: str) -> Asset:
    if system != "Linux" or machine not in ASSETS:
        raise ValueError(f"no reviewed Lean archive for {system}/{machine}")
    return ASSETS[machine]


def check_toolchain_pin(path: Path) -> None:
    if path.read_bytes() != TOOLCHAIN:
        raise ValueError(f"{path} does not match the reviewed Lean pin")


def download(asset: Asset, target: Path) -> None:
    """Fetch over HTTPS only; verification, not transport, decides acceptance."""
    subprocess.run(
        [
            "curl", "--fail", "--silent", "--show-error", "--location",
            "--proto", "=https", "--proto-redir", "=https", "--tlsv1.2",
            "--retry", "3", "--connect-timeout", "30", "--max-time", "1200",
            "--max-filesize", str(asset.size),
            "--output", str(target), f"{RELEASE}/{asset.name}",
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        timeout=1300,
    )


def verify_archive(asset: Asset, path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("downloaded Lean archive is not a regular file")
    if path.stat().st_size != asset.size:
        raise ValueError("Lean archive size does not match the reviewed pin")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    if digest.hexdigest() != asset.sha256:
        raise ValueError("Lean archive SHA-256 does not match the reviewed pin")


def check_installed(root: Path) -> None:
    """Require the extracted binary to identify itself as the pinned install."""
    binary = root / "bin/lean"
    env = {"PATH": os.environ.get("PATH", "")}
    prefix = subprocess.run(
        [str(binary), "--print-prefix"],
        check=True, capture_output=True, text=True, timeout=60, env=env,
    ).stdout.strip()
    if Path(prefix).resolve() != root.resolve():
        raise ValueError("installed Lean reports a different toolchain prefix")
    version = subprocess.run(
        [str(binary), "--version"],
        check=True, capture_output=True, text=True, timeout=60, env=env,
    ).stdout
    if VERSION.search(version) is None:
        raise ValueError("installed Lean does not report version 4.35.0")


def install(asset: Asset, dest: Path, *, fetch=download) -> Path:
    """Install into a new canonical `dest`, leaving nothing behind on failure."""
    if not dest.is_absolute() or dest.parent.resolve(strict=True) != dest.parent:
        raise ValueError("destination parent must be canonical and absolute")
    if dest.exists() or dest.is_symlink():
        raise ValueError("destination already exists")
    with tempfile.TemporaryDirectory(prefix=".lean-install-", dir=dest.parent) as work:
        archive = Path(work) / asset.name
        fetch(asset, archive)
        verify_archive(asset, archive)
        unpacked = Path(work) / "toolchain"
        unpacked.mkdir()
        subprocess.run(
            ["tar", "--zstd", "--extract", "--no-same-owner",
             "--strip-components=1", "--file", str(archive),
             "--directory", str(unpacked)],
            check=True,
            stdin=subprocess.DEVNULL,
            timeout=900,
        )
        archive.unlink()
        unpacked.rename(dest)
    try:
        check_installed(dest)
    except BaseException:
        shutil.rmtree(dest)
        raise
    return dest


def publish_to_github(root: Path) -> None:
    """Expose the verified tools to later steps of the same job."""
    with Path(os.environ["GITHUB_PATH"]).open("a", encoding="utf-8") as stream:
        stream.write(f"{root / 'bin'}\n")
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
        stream.write(f"TND_LEAN_ROOT={root}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument(
        "--github", action="store_true", help="export the install to this Actions job"
    )
    args = parser.parse_args(argv)
    try:
        check_toolchain_pin(Path(__file__).resolve().parents[1] / "lean-toolchain")
        asset = select_asset(platform.system(), platform.machine())
        root = install(asset, args.dest)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Lean installation refused: {error}", file=sys.stderr)
        return 1
    if args.github:
        publish_to_github(root)
    print(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
