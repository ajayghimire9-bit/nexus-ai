"""Wave 28 driver: the postcondition-core-filter engine (src/nexus/wave29_core.py) on the Wave 26 Phase 4 / 5 tasks
and compositional Phase 6 target worlds (copied from scripts/wave28_confirm.py).

  --phase 4|5|6 --dev --seeds ...        dev units (Phase 4 seeds 721-725, Phase 5 streams 731-735, Phase 6
                                         orderings 741-745); reusable dev data
  --phase 4|5|6 --confirm                one-use Wave 29 ranges 4021-4025 / 5021-5025 / 6021-6025 (checkpointed per
                                         unit; the artifact is written before any replay)
  --phase BX --confirm                   post-lock wave29_paired_check on Group B + external ARC (3011-3030, 2 tasks
                                         per seed, orderings 6001-6005) through the token-gated loader (owner registry
                                         override; aggregates only): does the 10/40 coverage return?
  --replay-of ART --seeds ...            fresh-process replay (PYTHONHASHSEED=271828) of the listed units
Gates are declared in docs/NEXUS_WAVE29_OCCAM_MARGIN.md before confirmation.
"""
import argparse, importlib.util, json, os, pickle, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
SEALED_BX = (("group_b", range(3011, 3021)), ("external_arc_1d_grid", range(3021, 3031)))
DEV = {"4": range(721, 726), "5": range(731, 736), "6": range(741, 746)}
CONFIRM = {"4": ("wave29_p4", "confirm", range(4021, 4026)), "5": ("wave29_p5", "confirm", range(5021, 5026)),
           "6": ("wave29_p6", "confirm", range(6021, 6026)),
           "A": ("phase3", "vault_group_a", range(3001, 3011)), "BX": ("phase6", "orderings_confirm", range(6001, 6006))}


def ledger(run, wall, status, **kw):
    with LEDGER.open("a") as f:
        f.write(json.dumps(dict(run=run, wall_s=wall, status=status, **kw)) + "\n")


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_GIDS = {}


def _gid(key):
    if key not in _GIDS:
        _GIDS[key] = f"group{len(_GIDS):02d}"
    return _GIDS[key]


def run_unit(phase, seed, dev, state):
    """One unit. `state` carries cross-unit memory where the design has it (sealed A library, sealed BX Fresh)."""
    from nexus import wave29_eval as E
    if phase == "4":
        return E.run_phase4(seed)
    if phase == "5":
        return E.run_phase5(seed)
    if phase == "6":
        return E.run_phase6(seed)
    if phase == "A":
        from nexus.wave29_core import EpistemicLibrary
        lib = state.setdefault("lib", EpistemicLibrary())
        _GIDS.clear(); _GIDS.update(state.setdefault("gids", {}))
        rows = E.run_sealed_a(lib, seed, _gid)
        state["gids"] = dict(_GIDS)
        return dict(seed=seed, rows=rows, library_after=lib.summary(), events=list(lib.events))
    if phase == "BX":
        from nexus.wave26_phase6 import sealed_stream_factory
        fc = state.setdefault("fresh_cache", {})
        return E.run_phase6(seed, sealed_stream_factory(SEALED_BX), fresh_cache=fc)
    raise SystemExit(f"unknown phase {phase}")


def unit_digest(o):
    from nexus.standing_gates import json_digest
    return json_digest(o)


def score(phase, outs):
    if phase == "4":
        rep = _script("phase4_invent").score_synth(outs)
        rows = [r for o in outs for r in o["mixed"] + o["deletion"] if r.get("generated")]
        rep["routes_core"] = sum(r["route"] == "core" for r in rows)
        rep["audits"] = {k: sum(r.get("audit") == k for r in rows) for k in ("passed", "counterexample", "unavailable")}
        rep["consolidated"] = sum(e[0] == "consolidated" for o in outs for ev in o["events"].values() for e in ev)
        rep["demoted"] = sum(e[0] == "demoted" for o in outs for ev in o["events"].values() for e in ev)
        rep["gate"] = rep["gate_router"] and rep["gate_primitives"] and rep["false_certificates"] == 0
        return rep
    if phase == "5":
        rep = _script("phase5_memory").score(outs)
        rep["demoted"] = sum(e[0] == "demoted" for o in outs for e in o["events"])
        rep["consolidated"] = sum(e[0] == "consolidated" for o in outs for e in o["events"])
        rep["audit_counterexamples"] = sum(r["audits"].get("counterexample", 0) for o in outs for r in o["rows"])
        rep["gate"] = rep["gate_revisit"] and rep["gate_interference"] and rep["gate_retirement"]
        return rep
    if phase in ("6", "BX"):
        from nexus.wave29_eval import score_phase6
        return score_phase6(outs)
    if phase == "A":
        rows = [r for o in outs for r in o["rows"]]
        seen, enc = {}, []
        for r in rows:
            r = dict(r, encounter=seen.get(r["group"], 0))
            seen[r["group"]] = r["encounter"] + 1
            enc.append(r)
        lib_summary = outs[-1]["library_after"] if outs else {}
        rep = _script("phase4_invent").score_sealed(enc, lib_summary)
        rep["consolidated"] = sum(v["status"] == "CONSOLIDATED" for v in lib_summary.values())
        rep["routes_core"] = sum(r.get("route") == "core" for r in rows)
        return rep
    raise SystemExit(phase)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True)
    for f in ("--dev", "--confirm", "--digest-only"):
        ap.add_argument(f, action="store_true")
    ap.add_argument("--replay-of")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    ap.add_argument("--wall-cap", type=float, default=840.0)
    a = ap.parse_args()
    from nexus import seed_registry as R
    ph = a.phase
    tag = f"wave29-p{ph}"

    if a.digest_only:
        # replay of units [a.seeds]; carried state (sealed A library) is rebuilt from the earliest unit of the run
        state, out = {}, {}
        first = CONFIRM[ph][2][0] if ph in ("A",) else None
        seeds = list(range(first, max(a.seeds) + 1)) if first is not None else a.seeds
        for s in seeds:
            o = json.loads(json.dumps(run_unit(ph, s, a.dev, state), default=repr))
            if s in a.seeds:
                out[s] = unit_digest(o)
        print(json.dumps(out))
        return

    if a.replay_of:
        art = json.loads(Path(a.replay_of).read_text())
        t0 = time.perf_counter()
        try:
            env = dict(os.environ, PYTHONHASHSEED="271828")
            cmd = [sys.executable, __file__, "--phase", ph, "--digest-only", "--seeds", *map(str, a.seeds)] + \
                (["--dev"] if art.get("dev") else [])
            got = json.loads(subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
                             .stdout.strip().splitlines()[-1])
        finally:
            ledger(f"{tag}-replay", time.perf_counter() - t0, "COMPLETE", seeds=a.seeds)
        rp = art["report"].setdefault("G_replay_per_unit", {})
        for s, d in got.items():
            rec = art["report"]["digests"][s]
            rp[s] = dict(recorded=rec, replayed=d, passed=rec == d)
        art["report"]["G_replay"] = len(rp) == len(art["report"]["digests"]) and all(v["passed"] for v in rp.values())
        Path(a.replay_of).write_text(json.dumps(art, default=repr, sort_keys=True))
        print(json.dumps(rp), art["report"]["G_replay"])
        return

    if not a.checkpoint or not a.out:
        raise SystemExit("--checkpoint and --out are required")
    ck = Path(a.checkpoint)
    if a.dev:
        seeds = a.seeds or list(DEV[ph])
        R.claim(f"phase{ph}", "dev", seeds, run_id=f"{tag}-dev", record=False)
    else:
        key0, key1, rng_ = CONFIRM[ph]
        seeds = list(rng_)
        if not ck.exists():
            if ph in ("A", "BX"):
                from nexus.sealed_vault_loader import verify_vault
                verify_vault()                                 # refuse before any registry claim
                reason = "wave29_paired_check: owner-authorised post-lock fourth pass (locked Wave 29 engine) on Group B + ARC"
                keys = [("phase3", "vault_group_a")] if ph == "A" else \
                    [("phase6", "orderings_confirm"), ("phase3", "vault_group_b"), ("phase3", "vault_external")]
                for k in keys:
                    R.owner_override(*k, reason=reason, approved_by="owner (2026-10-26 message)")
                    R.claim(*k, R.REGISTRY[k], run_id=f"{tag}-paired-check")
            else:
                R.claim(key0, key1, seeds, run_id=f"{tag}-confirm")

    t0, outs, done = time.perf_counter(), [], set()
    state_p = Path(str(ck) + ".state.pkl")
    state = pickle.loads(state_p.read_bytes()) if state_p.exists() else {}
    if ck.exists():
        for l in ck.read_text().splitlines():
            o = json.loads(l); outs.append(o); done.add(o["seed"])
    status = ["COMPLETE"]
    run_name = f"{tag}-{'dev' if a.dev else 'confirm'}"

    def on_term(signum, frame):
        ledger(run_name, time.perf_counter() - t0, "KILLED_AT_CAP", seeds=seeds)
        os._exit(124)
    signal.signal(signal.SIGTERM, on_term)
    longest = 0.0
    try:
        for s in seeds:
            if s in done:
                continue
            if time.perf_counter() - t0 + longest > a.wall_cap:
                status[0] = "PARTIAL_WALL_CAP"
                break
            u0 = time.perf_counter()
            o = json.loads(json.dumps(run_unit(ph, s, a.dev, state), default=repr))
            longest = max(longest, time.perf_counter() - u0)
            outs.append(o)
            with ck.open("a") as f:
                f.write(json.dumps(o, default=repr, sort_keys=True) + "\n")
            state_p.write_bytes(pickle.dumps(state))
            print(f"unit {s} done in {time.perf_counter() - u0:.0f}s", flush=True)
    finally:
        ledger(run_name, time.perf_counter() - t0, status[0], seeds=seeds)
    from nexus.standing_gates import g_tycho
    rep = score(ph, outs)
    rep["digests"] = {str(o["seed"]): unit_digest(o) for o in outs}
    rows = []
    for o in outs:
        for key in ("mixed", "deletion", "rows"):
            rows += [r for r in o.get(key, []) if "work_by" in r]
        for arm in o.get("arms", {}).values():
            rows += [r for r in arm["rows"] if "work_by" in r]
    rep["G_tycho"] = g_tycho(rows)
    rep["status"] = status[0] if len(outs) == len(seeds) else "PARTIAL"
    Path(a.out).write_text(json.dumps(dict(schema=f"wave29_phase{ph}", dev=a.dev, report=rep, seeds_raw=outs),
                                      default=repr, sort_keys=True))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("library_final", "orderings", "net_benefit")},
                     default=repr)[:3000])


if __name__ == "__main__":
    main()
