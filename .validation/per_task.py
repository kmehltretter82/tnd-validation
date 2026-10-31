"""Run the real verifier and comparator on each task's solution, then on all of them."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from audit.resource_boundary import Limits
from audit.resource_stages import QuotaStages
from gate.verify import tnd_comparator as tc
from gate.verify.comparator import classify_output
from gate.verify.comparator_cli import materialize_workspace
base, head, lean, landrun, tool, parent = sys.argv[1:7]
BUILD, EXPORT = Limits(2**30, 100000), Limits(2**28, 4096)
registry = {t["source_path"]: t for t in json.loads(Path("audit/tasks.json").read_text())["tasks"]}
def stage(name): Path("reports/stage.txt").write_text(name)
def git(*a):
    return subprocess.run(["git", "-c", "user.name=v", "-c", "user.email=v@example.invalid", "-c", "commit.gpgsign=false", *a], check=True, capture_output=True, text=True).stdout.strip()
def verify(label, target):
    stage("verify:" + label)
    out = Path(f"reports/audit-{label}.json")
    started = time.monotonic()
    done = subprocess.run([sys.executable, "audit/run.py", "--repo", ".", "--base", base, "--head", target, "--quota-parent", parent, "--output", str(out)], capture_output=True, text=True)
    report = json.loads(out.read_text()) if out.exists() else {}
    return {"status": report.get("status"), "reason": str(report.get("reason", done.stderr[-300:]))[-300:], "seconds": round(time.monotonic() - started, 1),
            "axioms": sorted({a for t in report.get("tasks", []) for d in t.get("proof_check", {}).get("declarations", []) for a in d.get("axioms", [])}), "tasks": [t.get("status") for t in report.get("tasks", [])]}
def compare(label, path, decl, target):
    stage("comparator:" + label)
    started = time.monotonic()
    try:
        reason = tc._applicability_reason(base, path, decl)
        if reason:
            return {"outcome": "not-applicable", "message": reason}
        with tempfile.TemporaryDirectory(prefix="cmp-") as d:
            root = Path(d); ws = root / "workspace"; tools = root / "tools"; ws.mkdir(); tools.mkdir()
            materialize_workspace(base, target, path, decl, ("propext", "Quot.sound"), ws)
            shutil.copyfile(landrun, tools / "landrun"); (tools / "landrun").chmod(0o755)
            for n, s in {"which": '#!/bin/sh\ncommand -v "$1"\n', "git": '#!/bin/sh\necho "Git is unavailable" >&2\nexit 125\n'}.items():
                (tools / n).write_text(s); (tools / n).chmod(0o755)
            with QuotaStages(Path(parent), BUILD, EXPORT) as q:
                r = q.comparator(ws, tools, Path(lean), Path(tool).resolve(), arguments=tc.docker_arguments)
            o, m, _ = classify_output(r.returncode, (r.stdout + b"\n" + r.stderr).decode("utf-8", "replace"))
            return {"outcome": o.value, "message": m[:200], "seconds": round(time.monotonic() - started, 1)}
    except Exception as e:
        return {"outcome": "error", "message": f"{type(e).__name__}: {e}"[:300]}
results = {}
for path in subprocess.run(["git", "diff", "--name-only", base, head, "--", "tasks"], check=True, capture_output=True, text=True).stdout.split():
    task = registry[path]; tid = task["id"]; decl = task["expected_exports"][0]
    git("checkout", "-q", base); git("checkout", head, "--", path); git("commit", "-q", "-m", "solve " + tid)
    single = git("rev-parse", "HEAD"); git("checkout", "-q", base)
    results[tid] = {"verify": verify(tid, single), "comparator": compare(tid, path, decl, single)}
    print(tid, json.dumps(results[tid]), flush=True)
results["ALL"] = {"verify": verify("all", head)}
print("ALL", json.dumps(results["ALL"]), flush=True)
stage("idle")
Path("reports/per-task.json").write_text(json.dumps(results, indent=1))
