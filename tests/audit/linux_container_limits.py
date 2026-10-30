"""Attack the exact parser and build container settings on native Linux.

Development evidence only, for an expendable host; it is not collected by the
test suites and cannot issue a certificate. Each attack runs inside the argument
lists the maintained stages build, with only the final command replaced, and
then hostile Lean source goes through the real parser path. Prints one JSON
report and exits nonzero if any limit fails to hold.

    python3 tests/audit/linux_container_limits.py --lean-root /path/to/lean-4.35.0
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from audit import run as driver  # noqa: E402
from audit.admission import admit, sandbox  # noqa: E402

GIB = 1024**3
# Half the bytes of a hostile source, leaving room for the approved text.
LIMIT = admit.MAX_FILE // 3
FILL = 'dd if=/dev/zero of={path}/fill bs=1M count={count} 2>&1 | tail -1; ls -l {path}/fill'
ATTACKS = {
    "memory": "head -c 3000m /dev/zero | tail -c 2900m | wc -c",
    "processes": (
        "cat /sys/fs/cgroup/pids.max; i=0; while [ $i -lt 400 ]; do sleep 20 & "
        "i=$((i+1)); done 2>/dev/null; cat /sys/fs/cgroup/pids.current"
    ),
    "tmp": FILL.format(path="/tmp", count=512),
    "shm": FILL.format(path="/dev/shm", count=512),
    "network": "cat /proc/net/route | wc -l; cat /proc/net/dev | grep -vc -E 'lo:|Inter|face'",
    "identity": (
        "id -u; grep -E 'CapEff|NoNewPrivs|Seccomp:' /proc/self/status; "
        "touch /rootfs-write 2>/dev/null; echo root_write=$?; "
        "touch /opt/lean/w 2>/dev/null; echo lean_write=$?; "
        "ls /var/run/docker.sock 2>/dev/null; echo socket=$?; "
        "mount -t tmpfs tmpfs /tmp 2>/dev/null; echo mount=$?"
    ),
    "exec_from_tmp": "cp /bin/true /tmp/t && /tmp/t; echo status=$?",
}


def attack(args: list[str], image: str, script: str, timeout: int = 180) -> dict:
    """Run `script` with the stage's exact limits under a fresh container name."""
    name = "tnd-limits-" + uuid.uuid4().hex
    position = args.index(image)
    command = [*args[:position], image, "sh", "-c", script]
    if "--name" in command:
        command[command.index("--name") + 1] = name
    else:
        command[2:2] = ["--name", name]
    started = time.monotonic()
    try:
        done = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
        result = {"status": done.returncode, "stdout": done.stdout.strip()[-400:],
                  "stderr": done.stderr.strip()[-200:]}
    except subprocess.TimeoutExpired:
        result = {"status": "timeout"}
    driver.ensure_container_removed(name)
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


def verdicts(results: dict, tmp_mib: int) -> dict:
    identity = results["identity"]["stdout"]

    def size(key):
        fields = results[key]["stdout"].splitlines()[-1].split()
        return int(fields[4]) if len(fields) > 4 and fields[4].isdigit() else None

    # A forking shell may die at the cap, so a final count is not guaranteed.
    processes = results["processes"]["stdout"].splitlines()
    peak = processes[-1] if len(processes) > 1 else "0"
    return {
        "memory_killed": results["memory"]["status"] != 0
            or str(2900 * 1024**2) not in results["memory"]["stdout"],
        "processes_capped": processes[0] == "128" and peak.isdigit() and int(peak) <= 128,
        "tmp_capped": size("tmp") is not None and size("tmp") <= tmp_mib * 1024**2,
        "shm_capped": size("shm") is not None and size("shm") <= 64 * 1024**2,
        "no_routes": results["network"]["stdout"].splitlines()[0] == "1",
        "no_interfaces": results["network"]["stdout"].splitlines()[1] == "0",
        "unprivileged": identity.splitlines()[0] != "0" and "CapEff:\t0000000000000000" in identity,
        "no_new_privileges": "NoNewPrivs:\t1" in identity,
        "seccomp_filtering": "Seccomp:\t2" in identity,
        "root_read_only": "root_write=1" in identity,
        "toolchain_read_only": "lean_write=1" in identity,
        "no_docker_socket": "socket=2" in identity,
        "cannot_mount": "mount=0" not in identity,
        "tmp_noexec": "status=126" in results["exec_from_tmp"]["stdout"],
    }


def hostile_sources(root: Path) -> dict:
    """Each replaces approved library text, as a malicious submission would."""
    return {
        "deep_nesting": "def x : Nat := " + "(" * 200_000 + "1" + ")" * 200_000 + "\n",
        # These fit the source size limit, so they reach the parser itself.
        "deep_parens_in_limit": "def x : Nat := " + "(" * LIMIT + "1" + ")" * LIMIT + "\n",
        "deep_binders_in_limit": "def x : Nat := " + "fun _ => " * (2 * LIMIT // 9) + "1\n",
        "unclosed_parens_in_limit": "def x : Nat := " + "(" * (2 * LIMIT) + "\n",
        "many_declarations_in_limit": "".join(
            f"def d{i} : Nat := {i}\n" for i in range(2 * LIMIT // 24)
        ),
        "unterminated_comment": "/- never closed\n",
        "unterminated_string": 'def x : String := "never closed\n',
        "malformed": "theorem : : : := := :=\n",
        "long_identifier": "def " + "a" * 200_000 + " : Nat := 1\n",
        "many_declarations": "".join(f"def d{i} : Nat := {i}\n" for i in range(40_000)),
        "invalid_utf8": b"def x : Nat := \xff\xfe 1\n",
        "elaborator_escape": "#eval IO.FS.writeFile \"/tmp/pwned\" \"x\"\n",
        "tactic_proof": "theorem t : True := by trivial\n",
        "macro": "macro \"evil\" : term => `(1)\n",
        "import_io": "import Lean\n",
    }


def source_attacks(args, work: Path) -> dict:
    report = {}
    target = next(path for path in sorted((PROJECT / "TNDLib").glob("*.lean")))
    for label, text in hostile_sources(work).items():
        case = work / f"source-{label}"
        case.mkdir()
        shutil.copytree(PROJECT / "TNDLib", case / "TNDLib")
        shutil.copy2(PROJECT / "TNDLib.lean", case / "TNDLib.lean")
        destination = case / "TNDLib" / target.name
        original = destination.read_bytes()
        addition = text if isinstance(text, bytes) else text.encode()
        destination.write_bytes(original + b"\n" + addition)
        started = time.monotonic()
        try:
            sandbox.admit_into_container(
                case, work / f"staged-{label}", args.lean_root.resolve(), image=driver.IMAGE,
                cleanup=driver.ensure_container_removed,
                check_seccomp=driver.require_default_seccomp,
            )
            outcome = "ADMITTED"
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            outcome = f"rejected: {type(error).__name__}: {str(error)[-140:]}"
        report[label] = {"outcome": outcome, "seconds": round(time.monotonic() - started, 1)}
        shutil.rmtree(case)
    return report


def main() -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-root", required=True, type=Path)
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        raise SystemExit("requires native Linux")
    driver.require_default_seccomp()
    lean = args.lean_root.resolve()
    report = {"development_only": True, "free_gib_before": round(
        shutil.disk_usage("/").free / GIB, 1)}
    with tempfile.TemporaryDirectory(prefix="tnd-limits-") as temporary:
        work = Path(temporary).resolve()
        for name in ("source", "build", "export"):
            (work / name).mkdir()
        (work / "source/.lake").mkdir()
        (work / "policy.json").write_text("{}")
        (work / "Main.lean").write_text("")
        (work / "tool").write_text("")
        if args.sources_only:
            report["sources"] = source_attacks(args, work)
            admitted = [k for k, v in report["sources"].items() if v["outcome"] == "ADMITTED"]
            print(json.dumps(report, indent=1))
            return 1 if admitted else 0
        profiles = {
            "parser": (sandbox.docker_arguments(
                driver.IMAGE, work / "source", work / "policy.json", work / "Main.lean", lean,
                "tnd-parser-" + "0" * 32), 32),
            "build": (driver.docker_arguments(
                driver.IMAGE, work / "source", work / "build", work / "export", lean,
                work / "tool", "TNDLib", "TNDLib", stage="build"), 256),
        }
        failed = []
        for profile, (arguments, tmp_mib) in profiles.items():
            results = {key: attack(arguments, driver.IMAGE, script)
                       for key, script in ATTACKS.items()}
            results["cpu_spin"] = (
                attack(arguments, driver.IMAGE, "while :; do :; done", timeout=100)
                if profile == "parser" else {"status": "not-limited-by-ulimit"}
            )
            checks = verdicts(results, tmp_mib)
            if profile == "parser":
                checks["cpu_ulimit_kills_spin"] = (
                    results["cpu_spin"]["status"] not in (0, "timeout")
                )
            report[profile] = {"checks": checks, "raw": results}
            failed += [f"{profile}.{key}" for key, value in checks.items() if not value]
        flood = sandbox.docker_arguments(
            driver.IMAGE, work / "source", work / "policy.json", work / "Main.lean", lean,
            "tnd-parser-" + uuid.uuid4().hex)
        name = flood[flood.index("--name") + 1]
        position = flood.index(driver.IMAGE)
        flood = [shutil.which("docker"), *flood[1:position], driver.IMAGE, "sh", "-c", "yes flood"]
        started = time.monotonic()
        try:
            done = admit.run_parser(flood, cwd=admit.HERE, env=None)
            report["output_flood"] = {"status": done.returncode, "bytes": len(done.stdout)}
            flood_ok = done.returncode != 0
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            report["output_flood"] = {"refused": f"{type(error).__name__}: {str(error)[-120:]}"}
            flood_ok = True
        report["output_flood"]["seconds"] = round(time.monotonic() - started, 1)
        driver.ensure_container_removed(name)
        if not flood_ok:
            failed.append("output_flood")
        report["sources"] = source_attacks(args, work)
        failed += [f"source.{key}" for key, value in report["sources"].items()
                   if value["outcome"] == "ADMITTED"]
    leftovers = subprocess.run(["docker", "ps", "-aq"], check=True, capture_output=True, text=True)
    report["residual_containers"] = len(leftovers.stdout.split())
    if report["residual_containers"]:
        failed.append("residual_containers")
    report["failed"] = failed
    print(json.dumps(report, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
