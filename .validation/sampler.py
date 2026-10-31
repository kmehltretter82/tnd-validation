"""Record peak quota and host memory use by stage until killed."""
import json, os, sys, time
from pathlib import Path
out, stage_file = Path(sys.argv[1]), Path(sys.argv[2])
peaks, host, last = {}, {}, 0.0
def mounts():
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        path = line.split()[4]
        if "tnd-boundary-" in path:
            yield path
while True:
    stage = stage_file.read_text().strip() if stage_file.exists() else "idle"
    for path in mounts():
        try:
            v = os.statvfs(path)
        except OSError:
            continue
        # A mount removed between the listing and statvfs reads the disk beneath.
        if v.f_frsize * v.f_blocks > 2**30:
            continue
        name = stage + ":" + path.rsplit("/", 1)[1]
        p = peaks.setdefault(name, {"bytes": 0, "inodes": 0, "capacity": v.f_frsize * v.f_blocks})
        p["bytes"] = max(p["bytes"], (v.f_blocks - v.f_bfree) * v.f_frsize)
        p["inodes"] = max(p["inodes"], v.f_files - v.f_ffree)
    m = {l.split(":")[0]: int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines()}
    h = host.setdefault(stage, {"min_available_mib": 10**9, "max_swap_used_mib": 0, "max_shmem_mib": 0})
    h["min_available_mib"] = min(h["min_available_mib"], m["MemAvailable"] // 1024)
    h["max_swap_used_mib"] = max(h["max_swap_used_mib"], (m["SwapTotal"] - m["SwapFree"]) // 1024)
    h["max_shmem_mib"] = max(h["max_shmem_mib"], m["Shmem"] // 1024)
    if time.monotonic() - last > 2:
        out.write_text(json.dumps({"quota": peaks, "host": host}, indent=1))
        last = time.monotonic()
    time.sleep(0.1)
