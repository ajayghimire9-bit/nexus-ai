"""Phase 10G Stage 1: Phase 10F attribution closure (NOT LOCKED; owner-requested POST-HOC diagnostic on the 22 already-consumed
Phase 10F held-out targets; no retraining; the frozen Phase 10F code and checkpoints; rows are a diagnostic, not a new one-use
evaluation, and never replace a Phase 10F row).
  python scripts/agi10g_attrib.py counts OUT.json        step-50 replay source examples in every 10F checkpoint (no execution)
  python scripts/agi10g_attrib.py run CHUNK N OUT.jsonl  the bounded direct evaluation, rows appended + flushed
  python scripts/agi10g_attrib.py score OUT.json ROWS...
ARMS (A4 configuration = G_Lstar + L0 U L*, Phase 10F procedure, work 600, wall 4 s, declared-engine hidden verification):
  A4sub_r        rep{r}.subgroup.final (re-run: reproducibility check against the Phase 10F rows)
  A4cur_r        rep{r}.current.final (the Abs_current solver, never evaluated in Phase 10F)
  A4sub_noL10_1  rep1.subgroup.final with ONLY L10 (the ckey subgroup macro) removed
  A4sub_noL6_1   rep1.subgroup.final with ONLY L6 (the ckey-stripped broad macro) removed"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10f import lineage10f as LF, manifest10f as MF, world10f as W  # noqa: E402
TR = ROOT / "artifacts/agi10f_train"
RES = json.loads((ROOT / "artifacts/agi10f_eval/result.json").read_text())


def common22():
    rows = [json.loads(l) for f in sorted((ROOT / "artifacts/agi10f_eval").glob("rows_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["seed"], {})[r["arm"]] = r
    arms = {r["arm"] for r in rows}
    return sorted(s for s, v in by.items() if set(v) == arms and next(iter(v.values()))["group"] == "heldout"), by


def counts(out):
    res = {}
    for r in ("rep0", "rep1"):
        for rule in ("current", "subgroup"):
            ck = json.loads((TR / f"{r}.{rule}.N50.json").read_text())
            src = ck["memory"]["skill_src"]
            rows = []
            for s in src:
                e = s["edits"]
                for i in range(len(e) - 1):
                    if e[i][0] in ("add_partition",) and e[i + 1][0] == "set_dedup":
                        kind = "dream" if "#dream" in s["project"] else "partial" if "#partial" in s["project"] else "bridge" if "#bridge" in s["project"] else "wake"
                        rows.append(dict(project=s["project"], kind=kind, partition_key_has_ckey="ckey" in e[i][2][1], order_has_arrival="arrival" in e[i + 1][3][1]))
            wake = [json.loads(l) for l in (TR / f"{r}.{rule}.wake.jsonl").read_text().splitlines()]
            res[f"{r}.{rule}"] = dict(two_step_replay_sources=len(rows), verified_sources=sum(x["kind"] in ("wake", "dream", "bridge") for x in rows),
                                      verified_sources_with_ckey=sum(x["kind"] in ("wake", "dream", "bridge") and x["partition_key_has_ckey"] for x in rows),
                                      verified_projects_with_ckey=len({x["project"].split("#")[0] for x in rows if x["kind"] in ("wake", "dream", "bridge") and x["partition_key_has_ckey"]}),
                                      k_min=3, sources=rows,
                                      s_replay_wake_by_50=[(w["n"], w["verified"]) for w in wake if w["family"] == "S_replay" and w["n"] <= 50])
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: {kk: v[kk] for kk in ("two_step_replay_sources", "verified_sources", "verified_projects_with_ckey", "s_replay_wake_by_50")} for k, v in res.items()}, indent=1))


def arms():
    A = {}
    for r in ("rep0", "rep1"):
        for rule, tag in (("subgroup", "A4sub"), ("current", "A4cur")):
            m = json.loads((TR / f"{r}.{rule}.final.json").read_text())["memory"]
            A[f"{tag}_{r}"] = LF.arm_memory(skills=m["de"]["skills"], guide_w=m["guides"].get("Lstar"))
    m = json.loads((TR / "rep1.subgroup.final.json").read_text())["memory"]
    for drop in ("L10", "L6"):
        A[f"A4sub_no{drop}_rep1"] = LF.arm_memory(skills={k: v for k, v in m["de"]["skills"].items() if k != drop}, guide_w=m["guides"].get("Lstar"))
    return A


def run(chunk, n, out):
    seeds, _ = common22()
    man = {t["seed"]: t for t in MF.eval_manifest()}
    A = arms()
    with open(out, "a") as fh:
        for s in seeds[int(chunk)::int(n)]:
            t = man[s]
            p = W.make_project10d(t, s, ROOT / "var/agi10g_ws/attrib")
            for name in sorted(A):
                t0 = time.time()
                _, r, v, w = LF.investigate(p, A[name])
                fh.write(json.dumps(dict(seed=s, arm=name, family=t["family"], outcome=r["outcome"], verified=v, wrong=w, work=r["work"],
                                         macro_steps=r.get("macro_steps"), path=[list(e) for e in (r.get("path") or [])], row_wall=round(time.time() - t0, 3))) + "\n")
                fh.flush()


def score(out, *files):
    seeds, by10f = common22()
    rows = [json.loads(l) for f in files for l in Path(f).read_text().splitlines() if l.strip()]
    A = {}
    for r in rows:
        A.setdefault(r["arm"], {})[r["seed"]] = r
    res = dict(targets=len(seeds), arms={})
    for a, v in sorted(A.items()):
        res["arms"][a] = dict(n=len(v), verified=sum(x["verified"] for x in v.values()), wrong=sum(x["wrong"] for x in v.values()), work=sum(x["work"] for x in v.values()),
                              macro_use={m: sum(1 for x in v.values() if x["verified"] and any(st[2] == m for st in (x["macro_steps"] or []))) for m in ("L6", "L7", "L10")})
    for r in ("rep0", "rep1"):
        ours = A.get(f"A4sub_{r}", {})
        res[f"reproduces_10f_A4_{r}"] = dict(same_verdict=sum(ours[s]["verified"] == by10f[s][f"A4_{r}"]["verified"] for s in ours),
                                             same_work=sum(ours[s]["work"] == by10f[s][f"A4_{r}"]["work"] for s in ours), n=len(ours),
                                             phase10f_A4f=sum(by10f[s][f"A4f_{r}"]["verified"] for s in seeds))
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    {"counts": counts, "run": run, "score": score}[sys.argv[1]](*sys.argv[2:])
