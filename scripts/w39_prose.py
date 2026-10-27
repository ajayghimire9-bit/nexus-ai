"""Wave 39 external PROSE track (NOT LOCKED). --split dev (PROSE-dev: artifacts/external/prose, quarantined development data) |
confirm (PROSE-confirm: the sealed vault; frozen runner; manifest hashes verified; one-use claim wave39/confirm_prose).
Task format: >= 4 examples (else NOT_EVALUABLE); public = first 3 pairs, query = the 4th input, held-out = pairs 4.. (the query
pair included); future inputs given to the checker (extra queries) = held-out inputs 2..17. Multi-column inputs are lists of
strings (v5 harness); the v4 harness cannot express them (SKIPPED_FORMAT for Fresh-v4, as in Wave 38).
Arms (one sandboxed child per arm; budget = 2x cap = 4M executions per search; anytime curves read from this run):
  Fresh-v4 (Wave 38 language, Checker v4) | Fresh-v5 | Placebo-v5 | Fixed-v5 (hand-designed, category d) | Repr-v5 (learned
  representation prior) | Repr-core-v5 (core set: one certified program per source mechanism) | Online-hier-v5 (empty library,
  continual over the external stream in name order, HierLearner, certified updates only).
Priors are trained ONLY on internal source domains (all 4 program domains, source mechanisms, 2 instances each), solved by
Fresh-v5 in the sandbox (metered: source solving work and fitting work are both recorded). No external outcome trains anything.
External tasks have no oracle (probes are refused, not flagged)."""
import argparse, glob, hashlib, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CAP2 = 4_000_000
MANIFEST = ROOT / "artifacts/external/prose_confirm/MANIFEST.json"


def tasks_for(split):
    if split == "dev":
        files = {Path(f).stem: Path(f) for f in sorted(glob.glob(str(ROOT / "artifacts/external/prose/*.json")))}
        return {n: json.loads(f.read_text()) for n, f in files.items()}, {n: "dev" for n in files}
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("PROSE-confirm may be loaded only by the frozen runner (NEXUS_SEALED_HARNESS_TOKEN)")
    man = json.loads(MANIFEST.read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave39_prose_confirm"
    out = {}
    for n, h in sorted(man["sha256"].items()):
        b = (vault / f"{n}.json").read_bytes()
        if hashlib.sha256(b).hexdigest() != h:
            raise SystemExit(f"manifest hash mismatch: {n}")
        out[n] = json.loads(b)
    return out, man["split"]


def convert(spec, multi_ok):
    ex = spec["Examples"]
    if len(ex) < 4:
        return None, "NOT_EVALUABLE"
    multi = any(len(e["Input"]) != 1 for e in ex)
    if multi and not multi_ok:
        return None, "SKIPPED_FORMAT"
    conv = (lambda e: list(e["Input"])) if multi else (lambda e: e["Input"][0])
    t = {"public": [[conv(e), e["Output"]] for e in ex[:3]], "query": conv(ex[3]), "answer": ex[3]["Output"],
         "teacher": [{"op": "strip"}], "heldout": [[conv(e), e["Output"]] for e in ex[3:]]}
    return t, None


def score(row, t, run):
    """Harness side: held-out evaluation of the chosen program (HELD_OUT_VERIFIED) and per-input silent failures."""
    if not row.get("candidate"):
        row.update(heldout_pass=None, held_out_verified=False, inputs=[]); return row
    c = row.pop("candidate")
    key = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"))
    ok = [key(run(c, x)) == key(y) for x, y in t["heldout"]]
    row["heldout_pass"] = sum(ok) / len(ok)
    row["held_out_verified"] = bool(row.get("certified")) and all(ok)
    labels = [row.get("certified")] + [e["answers"] == 1 for e in row.get("extra", [])] if row.get("certified") else []
    row["inputs"] = [dict(ok=o, unique=bool(u)) for o, u in zip(ok, labels)]
    row["chain_len"] = len(c)
    return row


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default="Fresh-v4,Fresh-v5,Placebo-v5,Fixed-v5,Repr-v5,Repr-core-v5,Online-hier-v5")
    ap.add_argument("--max-s", type=float, default=850)
    a = ap.parse_args()
    from nexus import w38_domains as Dm, w38_eval as WE4, w38_lang as L4, w39_eval as WE, w39_lang as L, w38_online as O
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    if a.split == "confirm" and "claimed" not in res:
        from nexus import seed_registry as R
        R.claim("wave39", "confirm_prose", [7846], run_id="w39-confirm_prose")
        res["claimed"] = True
    specs, split_of = tasks_for(a.split)
    ev = WE.Eval()
    if "source" not in res:                                       # internal source training (metered)
        src = Dm.stream("w39-src", Dm.DOMAINS, "source", 2)
        ch = ev.child(); rows, progs, mech_seen, core = [], [], set(), []
        for i, t in enumerate(src):
            r = ev.solve(ch, t, len(t["teacher"]), f"w39-src:{i}")
            rows.append(dict(work=r["work"], certified=r.get("certified"), wrong=r["wrong"]))
            if r.get("certified"):
                progs.append(r["candidate"])
                if (t["domain"], t["mechanism"]) not in mech_seen:
                    mech_seen.add((t["domain"], t["mechanism"])); core.append(r["candidate"])
        fits = {k: ev.call(ch, job) for k, job in (("learned", {"cmd": "fit", "kind": "learned", "programs": progs}),
                                                   ("placebo", {"cmd": "fit", "kind": "placebo", "programs": progs, "seed": "w39-src"}),
                                                   ("repr", {"cmd": "fit", "kind": "repr", "programs": progs}),
                                                   ("repr_core", {"cmd": "fit", "kind": "repr", "programs": core}))}
        ch.close()
        res["source"] = dict(n=len(src), certified=len(progs), core=len(core), wrong=sum(r["wrong"] for r in rows),
                             solve_work=sum(r["work"] for r in rows), fit_instr={k: v["_instr"] for k, v in fits.items()},
                             priors={k: v["prior"] for k, v in fits.items()})
        p.write_text(json.dumps(res, sort_keys=True))
    pri = res["source"]["priors"]
    priors = {"Fresh-v5": None, "Placebo-v5": pri["placebo"], "Fixed-v5": {"kind": "fixed5"}, "Repr-v5": pri["repr"],
              "Repr-core-v5": pri["repr_core"]}
    names = sorted(specs)
    res.setdefault("tasks", {n: {"split": split_of[n]} for n in names})
    for arm in a.arms.split(","):
        if res.get("done", {}).get(arm):
            continue
        if arm == "Online-hier-v5":
            todo = [(n, convert(specs[n], True)[0]) for n in names]
            for n, t in todo:
                if t is None:
                    res["tasks"][n][arm] = {"label": "NOT_EVALUABLE"}
            todo = [(n, t) for n, t in todo if t]
            rows, learn, declared = ev.stream([t for _, t in todo], dict(O.BASELINE_80F9CC2, gate="hier"), f"prose-{a.split}-online",
                                              budget=CAP2, extras=[[x for x, _ in t["heldout"][1:17]] for _, t in todo],
                                              oracle=False, depth=3)
            for (n, t), r in zip(todo, rows):
                res["tasks"][n][arm] = score(r, t, L.run)
            res["online_learn_instr"], res["online_declared"] = learn, declared
        else:
            v4 = arm == "Fresh-v4"
            E = WE4.Eval() if v4 else ev
            ch = E.child()
            for n in names:
                if arm in res["tasks"][n]:
                    continue
                t, why = convert(specs[n], not v4)
                if t is None:
                    res["tasks"][n][arm] = {"label": why}; continue
                if v4:
                    r = E.solve(ch, t, 3, f"prose:{n}", prior=None, budget=CAP2)
                    r["certified"] = r["label"] == "exhaustive_UNIQUE" and not any(r["flags"].values())
                    r["extra"] = []
                    res["tasks"][n][arm] = score(r, t, L4.run)
                else:
                    r = E.solve(ch, t, 3, f"prose:{n}", prior=priors[arm], budget=CAP2,
                                extra=[x for x, _ in t["heldout"][1:17]], oracle=False)
                    res["tasks"][n][arm] = score(r, t, L.run)
                if time.perf_counter() - t0 > a.max_s:
                    break
            ch.close()
        if all(arm in res["tasks"][n] for n in names):
            res.setdefault("done", {})[arm] = True
        p.write_text(json.dumps(res, sort_keys=True))
        print(arm, "done" if res.get("done", {}).get(arm) else "partial", "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    WE.ledger_append(dict(run=f"w39-prose-{a.split}", wall_s=time.perf_counter() - t0, status="CHECKPOINT"))


if __name__ == "__main__":
    main()
