"""Phase 2 job runner (copy of scripts/mi3_jobs.py with the Phase 2 budget guard) (NOT LOCKED).  python scripts/mi3_jobs.py JOBS.json STATUS.json MAX_PAR TIMEOUT_S
JOBS.json = [{"run": "mi-3-...", "cap": seconds, "args": [script, arg, ...]}, ...]; each job runs as
  python scripts/mi_exec.py RUN CAP -- ARGS...   (metered: the ledger row, CPU cap and log come from mi_exec)
Tracks every child by PID and exit code (never by log markers), at most MAX_PAR at once; writes STATUS.json atomically after
every change (pid, start, end, wall, exit code, the mi_exec status line); prints progress and an ETA from the mean wall time of
COMPLETED jobs. After TIMEOUT_S of wall time it stops launching, terminates only its own still-running children (by PID) and
records them as killed. Exit 0 iff every job exited 0."""
import json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agi2_budget as mi3_budget  # noqa: E402


def save(p, obj):
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(p)


def main(jobs_p, status_p, max_par, timeout_s):
    jobs = json.loads(Path(jobs_p).read_text())
    max_par, timeout_s = int(max_par), float(timeout_s)
    st = [dict(run=j["run"], state="pending") for j in jobs]
    live, T0, nxt = {}, time.time(), 0
    logs = Path(status_p).with_suffix(".logs")
    logs.mkdir(exist_ok=True)
    while nxt < len(jobs) or live:
        timed_out = time.time() - T0 > timeout_s
        while not timed_out and nxt < len(jobs) and len(live) < max_par:
            j = jobs[nxt]
            res = [float(jobs[i]["cap"]) for i in live]
            ok, info = mi3_budget.allow(j["run"], float(j["cap"]), sum(res), sum(
                float(jobs[i]["cap"]) for i in live if mi3_budget.stage_of(jobs[i]["run"]) == mi3_budget.stage_of(j["run"])))
            if not ok:
                st[nxt].update(state="refused_budget", info=info)
                print(f"REFUSED {j['run']} cap {j['cap']}: {info}", flush=True)
                nxt += 1
                continue
            out = open(logs / f"{j['run']}.out", "w")
            p = subprocess.Popen([sys.executable, "scripts/mi_exec.py", j["run"], str(j["cap"]), "--"] + j["args"], cwd=ROOT,
                                 stdout=out, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            live[nxt] = (p, out)
            st[nxt].update(state="running", pid=p.pid, start=round(time.time() - T0, 1))
            nxt += 1
        for i, (p, out) in list(live.items()):
            rc = p.poll()
            if rc is None and timed_out:
                p.terminate()
                try:
                    rc = p.wait(20)
                except subprocess.TimeoutExpired:
                    p.kill()
                    rc = p.wait()
                st[i]["state"] = "killed_at_timeout"
            if rc is not None:
                out.close()
                tail = (logs / f"{jobs[i]['run']}.out").read_text().strip().splitlines()[-1:] or [""]
                st[i].update(state=st[i]["state"] if st[i]["state"] != "running" else ("done" if rc == 0 else "failed"),
                             exit=rc, end=round(time.time() - T0, 1), wall=round(time.time() - T0 - st[i]["start"], 1),
                             mi_exec=tail[0][:300])
                del live[i]
                done = [s for s in st if s["state"] in ("done", "failed")]
                mean = sum(s["wall"] for s in done) / len(done)
                left = len(jobs) - len(done)
                eta = mean * left / max_par if left else 0.0
                print(f"[{time.time() - T0:7.1f}s] {jobs[i]['run']} exit {rc} wall {st[i]['wall']}s | {len(done)}/{len(jobs)} done, "
                      f"ETA ~{eta:.0f}s (mean completed wall {mean:.1f}s, {min(max_par, left)} parallel)", flush=True)
        save(status_p, dict(elapsed=round(time.time() - T0, 1), timeout_s=timeout_s, jobs=st))
        if live or nxt < len(jobs):
            time.sleep(2)
    bad = [s for s in st if s.get("exit") != 0]
    print("ALLJOBS", "ok" if not bad else f"{len(bad)} not ok: {[s['run'] for s in bad]}", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
