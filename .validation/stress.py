"""Fill both accepted quotas with a container at its memory limit; the host must survive."""
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from audit.resource_boundary import ExperimentalBoundary, Limits
IMAGE = "ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac"
def meminfo():
    m = {l.split(":")[0]: int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines()}
    return {"available_mib": m["MemAvailable"] // 1024, "swap_used_mib": (m["SwapTotal"] - m["SwapFree"]) // 1024, "shmem_mib": m["Shmem"] // 1024}
Path("reports/stage.txt").write_text("stress")
report = {"before": meminfo()}
with ExperimentalBoundary(Path(sys.argv[1]), Limits(2**30, 100000), Limits(2**28, 4096)) as o:
    b, e = o.verify("build"), o.verify("export")
    script = ("dd if=/dev/zero of=/build/f bs=1M count=2048 2>&1 | tail -1; dd if=/dev/zero of=/export/f bs=1M count=512 2>&1 | tail -1; "
              "ls -l /build/f /export/f; cat /sys/fs/cgroup/memory.max; head -c 3000m /dev/zero | tail -c 2900m | wc -c; echo survived")
    done = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", f"{os.getuid()}:{os.getgid()}", "--memory", "2g", "--memory-swap", "2g", "--pids-limit", "128",
        "--mount", f"type=bind,src={b},dst=/build", "--mount", f"type=bind,src={e},dst=/export", IMAGE, "sh", "-c", script], capture_output=True, text=True, timeout=300)
    report["container"] = {"status": done.returncode, "stdout": done.stdout[-500:], "stderr": done.stderr[-200:]}
    report["both_full"] = meminfo()
    report["sizes"] = {"build": (b / "f").stat().st_blocks * 512, "export": (e / "f").stat().st_blocks * 512}
report["after_close"] = meminfo()
Path("reports/stress.json").write_text(json.dumps(report, indent=1)); print(json.dumps(report, indent=1))
Path("reports/stage.txt").write_text("idle")
