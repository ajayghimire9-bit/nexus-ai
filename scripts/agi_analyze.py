"""Multi-world campaign: source / meta stage summaries and the R / L inventory (NOT LOCKED; reads saved artifacts only).
  python scripts/agi_analyze.py source   -> artifacts/agi_src/summary.json
  python scripts/agi_analyze.py meta     -> artifacts/agi_meta/summary.json"""
import json, sys
from pathlib import Path
from nexus.campaign import state as ST, substrate as S
ROOT = Path(__file__).resolve().parents[1]
COH = ("Full", "Fixed-M0", "Random-Proposal")


def lineage_summary(doc):
    rows = [r for r in doc["rows"] if r.get("phase") == "source"]
    st = ST.from_json(doc["state"])
    by = lambda key: {k: dict(n=sum(1 for r in rows if r[key] == k), solved=sum(r["solved"] for r in rows if r[key] == k))  # noqa: E731
                      for k in sorted({r[key] for r in rows})}
    rounds = doc["rounds"]
    props = [p for rd in rounds for p in rd["proposals"]]
    inv = {}
    for tab in ("L", "R"):
        for iid, it in st[tab].items():
            inv[iid] = dict(kind=tab, src=it["src"], expanded=S.to_src(ST.expand(it["body"], st)), size=it["size"],
                            holes=it.get("holes") or [it.get("tin")], out=it.get("out") or it.get("tout"), mdl=it["mdl"],
                            method=it["method"], birth_task=it["birth_task"], birth_round=it["birth_round"],
                            support=it["support"], admission=it.get("admission"), source_uses=it["uses"], util=it["util"],
                            cost=st["pi"]["costs"].get(f"{tab}:{iid}", st["pi"].get("item_cost", 2)))
    pi0 = ST.pi0()
    dcost = {k: [pi0["costs"].get(k), v] for k, v in st["pi"]["costs"].items() if pi0["costs"].get(k) != v and k[:2] not in ("L:", "R:")}
    return dict(name=doc["name"], elapsed=doc["elapsed"], cpu=doc["cpu"], stop=doc["stop_reason"], tasks=len(rows),
                solved=sum(r["solved"] for r in rows), silent=sum(r["silent"] for r in rows),
                queries=sum(r["queries"] for r in rows), by_world=by("world"), by_level=by("level"),
                rounds=len(rounds), proposals=len(props), admitted=sum(p["ok"] for p in props),
                admitted_by_kind={k: sum(1 for p in props if p["ok"] and p["kind"] == k) for k in ("L", "R", "pi_costs", "pi_params")},
                proposed_by_kind={k: sum(1 for p in props if p["kind"] == k) for k in ("L", "R", "pi_costs", "pi_params")},
                meta_edits=doc["meta_log"], meta_adopted=sum(m["adopted"] for m in doc["meta_log"]), M=st["M"],
                pi_params={k: st["pi"][k] for k in ("margin", "n_probes", "lam_max", "feat_k", "qsel", "confirm_q", "fit_alpha")},
                pi_cost_changes=dcost, inventory=inv, pruned=st.get("pruned", []), digest=doc["digest"],
                schedule_len=len(doc["schedule"]),
                solve_curve=[(r["t"], sum(q["solved"] for q in rows[:i + 1])) for i, r in enumerate(rows)][::5])


def source():
    out = {}
    for r in range(3):
        for c in COH:
            p = ROOT / f"artifacts/agi_src/{c}_r{r}.json"
            if p.exists():
                out[f"{c}_r{r}"] = lineage_summary(json.loads(p.read_text()))
    (ROOT / "artifacts/agi_src/summary.json").write_text(json.dumps(out, indent=1, default=list))
    for k, v in out.items():
        print(k, "tasks", v["tasks"], "solved", v["solved"], "silent", v["silent"], "rounds", v["rounds"], "admitted",
              v["admitted_by_kind"], "of", v["proposed_by_kind"], "meta", v["meta_adopted"], "/", len(v["meta_edits"]),
              "L/R", len([i for i in v["inventory"].values() if i["kind"] == "L"]),
              len([i for i in v["inventory"].values() if i["kind"] == "R"]), "stop", v["stop"], "elapsed", v["elapsed"])
        for iid, it in v["inventory"].items():
            print("    ", iid, it["src"], "| mdl", it["mdl"], "| support", len(it["support"]), "| uses", len(it["source_uses"]),
                  "| adm", (it["admission"] or {}).get("why") or (it["admission"] or {}).get("d_solved"))
        print("    pi", v["pi_params"], "cost changes", len(v["pi_cost_changes"]))


def meta():
    out = {}
    for r in range(3):
        for m in ("Mstar", "M0", "Mrand"):
            p = ROOT / f"artifacts/agi_meta/r{r}_{m}.json"
            if p.exists():
                out[f"r{r}_{m}"] = lineage_summary(json.loads(p.read_text()))
    (ROOT / "artifacts/agi_meta/summary.json").write_text(json.dumps(out, indent=1, default=list))
    for k, v in out.items():
        print(k, "tasks", v["tasks"], "solved", v["solved"], "silent", v["silent"], "rounds", v["rounds"], "admitted",
              v["admitted_by_kind"], "L/R", len([i for i in v["inventory"].values() if i["kind"] == "L"]),
              len([i for i in v["inventory"].values() if i["kind"] == "R"]), "elapsed", v["elapsed"])


if __name__ == "__main__":
    {"source": source, "meta": meta}[sys.argv[1]]()
