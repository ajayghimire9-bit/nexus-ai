"""R1 development demonstration of the observation-to-replay check (NOT LOCKED; de3/dev only, reusable).
For every dev world:
  build view (ticks 1-8, from the engineer's visible archive) and ops view (ticks 1-14, the LIVE log the environment wrote
  with retention, publication and incidents):
    replay functions   grow_obs (observation-driven), pre-fix grow (f7bc420: every partition directory at tick 1),
                       post-fix grow (0bc3e0c: a partition appears with its first segment)
    mutations of the correct view (the mutation may use future knowledge; the monitor never does):
      M1 partition_early   every partition directory of the whole archive exists from tick 1
      M2a segment_omitted  one available orders_cdc segment is removed from its publication tick on
      M2b partition_omitted manifests/p0 is removed from tick 4 on
      M3 future_schema     every registry segment of the archive is present from tick 1
      M4 reorder           the first two records of one orders_cdc segment are swapped
      M5 ack_beyond_durable  commit_protocol=offsets_first under every enumerated crash point at tick 4 (consumer check);
                             the two correct commit protocols as controls
  A mutation is DETECTED when the monitor reports >= 1 violation at the first tick where the mutated view differs from the
  correct view (an independent tree + content comparison), and the correct view has 0 violations at every tick.
  Ops only: grow_obs over the archive is compared byte-for-byte with the live log directory at every tick (fidelity against
  the real environment, not against the monitor).
  python scripts/r1_dev_monitor.py OUT.json"""
import hashlib, json, os, shutil, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import r1_seeds, seed_registry as R  # noqa: F401
from nexus import r1_env as RE, r1_monitor as M, r1_checks as RC, r1_template as RT, s4_checks as C
from nexus.wave31_evaluator import ledger_append


def tree(d):
    out = {}
    for p in sorted(Path(d).rglob("*")):
        rel = str(p.relative_to(d))
        if rel.startswith("_obs"):
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
    return out


def prefix_grow(full, dst, upto, spec, keep=6):
    """Pre-fix s4_checks.grow (git 0bc3e0c^), verbatim except the module references."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    for d in Path(full).glob("*/p*"):
        if d.parent.name == "_obs":
            continue
        (dst / d.parent.name / d.name).mkdir(parents=True, exist_ok=True)
    for topic, part, f in C.segments(full):
        first = json.loads(f.read_text().split("\n", 1)[0])
        tk = C.tick_of(first["ingest_ts"], spec)
        if upto - keep < tk <= upto:
            shutil.copy(f, dst / topic / f"p{part}" / f.name)
    return dst


def mutate(kind, view, full, k, spec, last):
    view, full = Path(view), Path(full)
    obs_last = json.loads((full / "_obs" / f"tick_{last:04d}.json").read_text())
    if kind == "M1":
        for p in obs_last["partitions"]:
            (view / p["topic"] / f"p{p['part']}").mkdir(parents=True, exist_ok=True)
    elif kind == "M2a":
        seg = next(s for s in obs_last["segments"] if s["topic"] == "orders_cdc" and s["part"] == 0 and s["pub"] >= 2)
        f = view / "orders_cdc" / "p0" / f"{seg['base']:08d}.jsonl"
        if f.exists():
            f.unlink()
    elif kind == "M2b":
        if k >= 4 and (view / "manifests" / "p0").exists():
            shutil.rmtree(view / "manifests" / "p0")
    elif kind == "M3":
        for s in obs_last["segments"]:
            if s["topic"] == "_schemas":
                (view / "_schemas" / "p0").mkdir(parents=True, exist_ok=True)
                shutil.copy(full / "_schemas" / "p0" / f"{s['base']:08d}.jsonl", view / "_schemas" / "p0")
    elif kind == "M4":
        seg = next(s for s in obs_last["segments"] if s["topic"] == "orders_cdc" and s["part"] == 0 and s["pub"] >= 3
                   and s["end"] - s["base"] >= 2)
        f = view / "orders_cdc" / "p0" / f"{seg['base']:08d}.jsonl"
        if f.exists():
            ls = f.read_text().split("\n")
            ls[0], ls[1] = ls[1], ls[0]
            f.write_text("\n".join(ls))
    return view


def run_views(full, ticks, spec, base_fn, work, live=None):
    """Returns per replay function / mutation: {tick: (n_violations, kinds, differs_from_correct)}."""
    out = {}
    fns = {"grow_obs": lambda k, d: RC.grow_obs(full, d, k),
           "prefix_grow": lambda k, d: prefix_grow(full, d, k, spec),
           "postfix_grow": lambda k, d: C.grow(full, d, k, spec)}
    if live is not None:
        fns["live"] = lambda k, d: (shutil.rmtree(d, ignore_errors=True), shutil.copytree(live[k], d), Path(d))[2]
    for name in list(fns) + ["M1", "M2a", "M2b", "M3", "M4"]:
        res = {}
        for k in ticks:
            ref = base_fn(k, work / "ref")
            if name in fns:
                v = fns[name](k, work / "v")
            else:
                v = mutate(name, base_fn(k, work / "v"), full, k, spec, ticks[-1])
            obs = M.load_obs(full, k)
            viol = M.check_view(v, obs)
            res[k] = (len(viol), sorted({x["kind"] for x in viol}), tree(v) != tree(ref))
        out[name] = res
    return out


def verdict(res, clean):
    first = next((k for k, x in sorted(res.items()) if x[2]), None)
    det_at = next((k for k, x in sorted(res.items()) if x[0]), None)
    return dict(first_change=first, first_violation=det_at, detected_at_first_change=first is not None and det_at == first,
                false_before=det_at is not None and (first is None or det_at < first),
                kinds=sorted({kk for x in res.values() for kk in x[1]}), clean_violations=sum(x[0] for x in clean.values()))


def ack_mutation(w, enc, work):
    full = work / "vis" / "log"
    runner = C.Runner()
    out = {}
    for proto in ("offsets_first", "sink_then_offsets", "transactional"):
        b = work / f"b_{proto}"
        b.mkdir(parents=True, exist_ok=True)
        ch = dict(RT.correct_choice(), commit_protocol=proto)
        (b / "pipeline.py").write_text(RT.emit(ch))
        (b / "config.json").write_text(json.dumps(RT.config_from_spec(w["spec"])))
        C.GROW = RC.grow_obs
        try:
            _, pre = C.replay(runner, b, full, w["spec"], work / f"pre_{proto}", range(1, 4))
            lg = RC.grow_obs(full, work / "lg4", 4)
            probe = work / "probe"
            if probe.exists():
                shutil.rmtree(probe)
            shutil.copytree(pre, probe)
            P = runner.run(b, lg, probe, tick=4, mode="count")["steps"] or 0
            viol, trials = 0, 0
            for kk in range(1, P + 2):
                s = work / f"cr_{proto}_{kk}"
                shutil.copytree(pre, s)
                runner.run(b, lg, s, tick=4, mode="crash", k=kk)
                v = M.check_consumer(s, M.load_obs(full, 4))
                viol += bool(v)
                trials += 1
                shutil.rmtree(s)
        finally:
            C.GROW = None
        out[proto] = dict(crash_points=trials, flagged=viol)
    return out, runner.cpu_s


def main(outp):
    t0 = time.perf_counter()
    res = {}
    for seed in R.REGISTRY[("de3", "dev")]:
        w = RE.make_world(seed, "dev")
        work = Path(tempfile.mkdtemp(prefix="r1mon_"))
        enc = RE.encode(w, "build")
        RE.write_log(enc, work / "vis", 8, archive=True)
        full = work / "vis" / "log"
        b = run_views(full, list(range(1, 9)), w["spec"], lambda k, d: RC.grow_obs(full, d, k), work)
        encs, incs = RE.ops_world(w, "dev", seed)
        live, arch = work / "live", work / "arch"
        snaps = {}
        rt = dict(state=str(work / "nostate"), log=str(live / "log"))
        for t in range(1, 15):
            RE.write_tick(encs, live, t)
            RE.write_tick(encs, arch, t)
            RE.retention(live, t)
            for inc in incs:
                try:
                    inc.on_tick_start(t, rt)
                except Exception:
                    pass
            RE.partition_states(live, t)
            Obs = RE.Obs(arch)
            for e in RE.Obs(live).events():                      # the archive shares the live availability facts
                if e["ev"] == "partition_state" and e["tick"] == t:
                    Obs.event(**e)
            Obs.materialize(t)
            snaps[t] = work / f"snap{t}"
            for d in sorted((live / "log").glob("*/p*")):        # snapshot what a consumer can read at this tick
                if d.parent.name == "_obs" or not os.access(d, os.R_OK):
                    continue
                (snaps[t] / d.parent.name / d.name).mkdir(parents=True, exist_ok=True)
                for f in d.glob("*.jsonl"):
                    shutil.copy(f, snaps[t] / d.parent.name / d.name / f.name)
        for d in (live / "log").glob("*/p*"):
            os.chmod(d, 0o755)
        o = run_views(arch / "log", list(range(1, 15)), w["spec"], lambda k, d: RC.grow_obs(arch / "log", d, k), work, live=snaps)
        fidelity = {k: tree(RC.grow_obs(arch / "log", work / "fid", k)) == tree(snaps[k]) for k in range(1, 15)}
        post_fid = {k: tree(C.grow(arch / "log", work / "fid", k, w["spec"])) == tree(snaps[k]) for k in range(1, 15)}
        pre_fid = {k: tree(prefix_grow(arch / "log", work / "fid", k, w["spec"])) == tree(snaps[k]) for k in range(1, 15)}
        ack, cpu = ack_mutation(w, enc, work)
        res[w["spec"]["project"]] = dict(
            build={n: verdict(v, b["grow_obs"]) for n, v in b.items()}, ops={n: verdict(v, o["grow_obs"]) for n, v in o.items()},
            ops_fidelity=dict(grow_obs=sum(fidelity.values()), postfix_grow=sum(post_fid.values()), prefix_grow=sum(pre_fid.values()),
                              ticks=14, first_postfix_mismatch=next((k for k, x in sorted(post_fid.items()) if not x), None)),
            ack=ack, pipeline_cpu_s=round(cpu, 2), raw_build={n: {str(k): x for k, x in v.items()} for n, v in b.items()},
            raw_ops={n: {str(k): x for k, x in v.items()} for n, v in o.items()})
        shutil.rmtree(work, ignore_errors=True)
        print(w["spec"]["project"], {n: (x["first_change"], x["first_violation"]) for n, x in res[w["spec"]["project"]]["build"].items()},
              res[w["spec"]["project"]]["ops_fidelity"], ack, "%.0fs" % (time.perf_counter() - t0), flush=True)
    Path(outp).write_text(json.dumps(dict(projects=res), indent=1, sort_keys=True, default=str))
    ledger_append(dict(run="r1-dev-monitor", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main(sys.argv[1])
