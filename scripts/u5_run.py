"""u5 end-to-end runner (NOT LOCKED).  python scripts/u5_run.py SPLIT [--seeds a,b] [--part k/n]
SPLIT pdev | val | val_b | test. Arms are composed from the promoted pillar artifacts (artifacts/u5_dev/p*.json):
  NEXUS_U5            every promoted pillar
  NEXUS_U5-P<i>       NEXUS_U5 with pillar i removed (only for promoted pillars):  -P1 flat dictionary template for the
                      lifecycle stream; -P2 baseline enumerator policy; -P3 no learned functions; -P4 the learner before
                      the curriculum; -P5 the learner before the meta-improver
  NEXUS_NoLearning    baseline enumerator, no library, continuation-split classes (no learned search knowledge at all)
  Fixed_Policy        author-written pipeline from the documented spec; known fault classes handled; escalates the rest
  Conventional        the same handlers, no registry-unit handling, no monitors
val / val_b: NEXUS_U5, Fixed_Policy, Conventional; one-use (claimed whole); the gate is read from artifacts/u5_freeze.json.
test: every arm; one-use; only with NEXUS_SEALED_HARNESS_TOKEN; reads only vault blobs whose sha256 match
artifacts/u5_test_vault/MANIFEST.json; parts run in order, each once; a crash stops the run (CRASHED; no traceback)."""
import hashlib, json, os, sys, time, traceback
from pathlib import Path
from u5_common import ROOT, ART, load, node_load, learner_cfg
from nexus import u5_platform as PL, u5_construct as K, evolvable_learner as EL, seed_registry as R

OUT = ROOT / "artifacts"


def learners():
    P = load("p2_policy.json")
    p1, p2, p3, p4 = (load(f"p{i}.json")["promoted"] for i in (1, 2, 3, 4))
    p5 = load("p5.json")
    cfg3 = learner_cfg(p2, P)
    lib3 = [] if p3 == "none" else [(f, p, node_load(b)) for f, p, b in load("p3_libs.json")[p3]]
    L = dict(P3=(cfg3, lib3))
    if p4 == "boundary":
        a = load("p4_boundary.json")
        L["P4"] = (learner_cfg(p2, dict(op_cost=a["op_cost"], weights=a["weights"], bias=a["bias"])), [(f, p, node_load(b)) for f, p, b in a["library"]])
    else:
        L["P4"] = L["P3"]
    if p5["promoted"]:
        L["P5"] = EL.to_config(PL.tuplify(p5["deployed_L"]))
        L["P5"] = (L["P5"][0], [PL.tuplify(x) for x in L["P5"][1]])
    else:
        L["P5"] = L["P4"]
    full = L["P5"]
    mk = lambda c, l: dict(cfg=c, lib=l, solver="hybrid")  # noqa: E731
    arms = {"NEXUS_U5": (mk(*full), "statesplit")}
    if p1:
        arms["NEXUS_U5-P1"] = (mk(*full), "flat")
    if p2 != "baseline" and full[1]:                    # with an empty library -P2 == NEXUS_NoLearning (not run twice)
        arms["NEXUS_U5-P2"] = (mk(K.default_config("baseline"), full[1]), "statesplit")
    if p3 != "none":
        arms["NEXUS_U5-P3"] = (mk(full[0], []), "statesplit")
    if p4 == "boundary":
        arms["NEXUS_U5-P4"] = (mk(*L["P3"]), "statesplit")
    if p5["promoted"]:
        arms["NEXUS_U5-P5"] = (mk(*L["P4"]), "statesplit")
    arms["NEXUS_NoLearning"] = (mk(K.default_config("baseline"), []), "statesplit")
    return arms, dict(p1=p1, p2=p2, p3=p3, p4=p4, p5=p5["promoted"])


def make_arms(names):
    nx, prom = learners()
    out = []
    for n in names:
        if n in nx:
            out.append(PL.NexusArm(n, nx[n][0], b_mode=nx[n][1]))
        elif n == "Fixed_Policy":
            out.append(PL.FixedArm(n))
        elif n == "Conventional":
            out.append(PL.FixedArm(n, monitored=False, handle_units=False))
    return out, prom


def all_arm_names():
    nx, _ = learners()
    return list(nx) + ["Fixed_Policy", "Conventional"]


def ledger_rows():
    p = ROOT / "runs/experimental/wave24-agi/ledger.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def projects(split, seeds):
    if split != "test":
        return [(s, lambda s=s: PL.Project(s, split)) for s in seeds]
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
    man = json.loads((OUT / "u5_test_vault/MANIFEST.json").read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"])
    out = []
    for k, s in enumerate(seeds):
        rel = f"u5_test/{k}.json"
        blob = (vault / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != man["files"][rel]:
            raise SystemExit(f"vault blob {rel} does not match the committed manifest")
        out.append((s, lambda b=blob: PL.Project.from_json(b.decode())))
    return out


def main():
    split = sys.argv[1]
    args = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    seeds = list(R.REGISTRY[("u5", split)])
    part = args.get("--part")
    if split in ("val", "val_b", "test"):
        fr = json.loads((OUT / "u5_freeze.json").read_text())
        if split == "val_b" and not fr.get("revision"):
            raise SystemExit("val_b only after one disclosed revision")
        k, n = map(int, (part or "1/1").split("/"))
        done = [r for r in ledger_rows() if r.get("run", "").startswith(f"u5-{split}-part")]
        if any(r.get("status") == "CRASHED" for r in done):
            raise SystemExit(f"{split} crashed earlier: no rerun")
        if any(r.get("run") == f"u5-{split}-part{k}of{n}" and r.get("status") in ("COMPLETE", "FAILED", "TIMEOUT") for r in done):
            raise SystemExit(f"{split} part {k}/{n} already ran")
        if k == 1:
            R.claim("u5", split, seeds, run_id=f"u5-{split}")
        chunk = [s for i, s in enumerate(seeds) if i % n == k - 1]
        names = all_arm_names() if split == "test" else ["NEXUS_U5", "Fixed_Policy", "Conventional"]
        dst = OUT / f"u5_{split}" / f"part{k}of{n}.json"
    else:
        chunk = [int(x) for x in args["--seeds"].split(",")] if "--seeds" in args else seeds
        names = args["--arms"].split(",") if "--arms" in args else all_arm_names()
        dst = ART / f"pdev_{'_'.join(map(str, chunk))}_{args.get('--tag', 'run')}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    arms, prom = make_arms(names)
    allp = dict(projects(split, seeds))
    res, status = [], "COMPLETE"
    for s in chunk:
        for arm in arms:
            P = allp[s]()
            try:
                r = PL.run_project(P, arm)
            except Exception as e:                                    # noqa: BLE001
                status = "CRASHED"
                res.append(dict(arm=arm.name, project=s, outcome="CRASHED", error=type(e).__name__ if split == "test" else traceback.format_exc()))
                break
            res.append(r)
            print(s, P.domain, P.fault, arm.name, "OK" if r["data_ok"] else "BAD", "indep" if r.get("independently_correct") else "-",
                  "silent" if r.get("silent") else "", "human", r["human_repairs"], r["outcome"], flush=True)
        if status == "CRASHED":
            break
    dst.write_text(json.dumps(dict(split=split, seeds=chunk, arms=names, promoted=prom, status=status, results=res), indent=1, default=str))
    print("STATUS", status, "->", dst)
    if status == "CRASHED":
        sys.exit(3)


if __name__ == "__main__":
    main()
