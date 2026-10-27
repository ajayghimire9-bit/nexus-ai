"""Wave 40 Step 1b (NOT LOCKED; audit only): which Wave 38 / Wave 39 tasks, solves or certificates were affected by Checker v4
(pin c07e21ec..., unchanged) using None both as its error sentinel (ERRK) and as a legitimate JSON null value.

Soundness argument for the filter (from the v4 source): a legitimate top-level None can only be produced by `get` / lambda
field access `f` on a null field, by `best` / `fold` returning a null element, or by a bare ["c", null] constant. No v4 tool
manufactures None from non-null data, and Wave 38/39 scopes contain null constants only inside eq / ne (boolean results; this
script asserts it per task). Hence a task whose public inputs, outputs and query contain no null cannot reach a legitimate None
at any depth, and v4's verdict on it is unaffected. Every null-bearing task gets an EXACT differential: v4._share vs a
shadow copy of v4 loaded in memory with a distinct sentinel object (the kernel file is not modified; RULE 2), plus v4's own
candidate pre-check conditions (a null public output or a null answer). Suites re-generated from their committed seeds:
Wave 38 LODO dev (841, 842) and confirm (7801-7805; sources + targets), meta / continual / evolution confirmation streams,
the Stage 4 6-phase program stream, Stage 4 PROSE-dev; Wave 39 Fresh-v4 on PROSE-dev (PROSE values are strings by format; the
sealed PROSE-confirm null count is produced by the Step 6 sealed runner). Planning and repair never used Checker v4."""
import argparse, json, sys, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))


def has_null(v):
    if v is None:
        return True
    if isinstance(v, list):
        return any(has_null(e) for e in v)
    if isinstance(v, dict):
        return any(has_null(e) for e in v.values())
    return False


def bare_null(e, inside_cmp=False):
    """True if a lambda / spec contains a null constant outside eq / ne."""
    if isinstance(e, list):
        if e[:1] == ["c"]:
            return e[1] is None and not inside_cmp
        cmp = bool(e) and e[0] in ("eq", "ne")
        return any(bare_null(x, cmp) for x in e[1:])
    if isinstance(e, dict):
        return any(bare_null(v) for k, v in e.items() if k in ("f", "p", "init", "g"))
    return False


def shadow_v4():
    src = (ROOT / "src/nexus/checker_kernel_v4.py").read_text()
    assert src.count("ERRK = None\n") == 1
    m = types.ModuleType("checker_kernel_v4_shadow")
    exec(compile(src.replace("ERRK = None\n", "ERRK = object()\n"), "v4_shadow", "exec"), m.__dict__)
    return m


def suites():
    import w38_online as O
    from nexus import seed_registry as R, w38_domains as D
    out = []
    for sd in (841, 842, *R.REGISTRY[("wave38", "confirm_lodo")]):
        for h in D.DOMAINS:
            others = tuple(d for d in D.DOMAINS if d != h)
            out += [(f"w38-lodo:{sd}:{h}:src", t) for t in D.stream(f"{sd}:src:{h}", others, "source", 2)]
            out += [(f"w38-lodo:{sd}:{h}:tgt", t) for t in D.stream(f"{sd}:tgt:{h}", (h,), "all", 2)]
    for sd in R.REGISTRY[("wave38", "confirm_online")]:
        out += [(f"w38-meta:{sd}", t) for t in O.program_stream(f"metac:{sd}", ("tables",), "all", 1)]
    for sd in R.REGISTRY[("wave38", "confirm_cont")]:
        for dom, sub in (("strings", "a"), ("graphs", "b"), ("strings", "c"), ("tables", "d")):
            out += [(f"w38-cont:{sd}", t) for t in O.program_stream(f"contc:{sd}:{sub}", (dom,), "source", 2)]
    for sd in R.REGISTRY[("wave38", "confirm_evo")]:
        out += [(f"w38-evo:{sd}", t) for t in O.program_stream(f"evoc:{sd}", O.FAST, "all", 1)]
    out += [("w38-stage4-program", t) for t in json.loads((ROOT / "artifacts/w38_stage4_tasks.json").read_text())]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(ROOT / "artifacts/w40_v4_none_audit.json"))
    ap.add_argument("--max-s", type=float, default=850)
    ap.add_argument("--resume", action="store_true", help="keep finished suites of an earlier (capped) run; do the rest")
    a = ap.parse_args()
    from nexus import checker_kernel_v4 as V4, w38_scope as S4, w39_eval as WE
    import w39_prose as P
    t0 = time.perf_counter()
    sh = shadow_v4()
    rows, summary = [], {}
    if a.resume and Path(a.out).exists():
        old = json.loads(Path(a.out).read_text())
        rows, summary = old["rows"], {k: v for k, v in old["summary"].items() if not k.startswith("_")}
        summary["_resumed_after_cap"] = sorted(summary)
    done = set(summary)
    tasks = [x for x in suites() if x[0].split(":")[0] not in done]
    dev, _ = P.tasks_for("dev")
    for n, spec in sorted(dev.items()):
        t, why = P.convert(spec, False)
        if t:
            tasks.append(("w38/w39-prose-dev", dict(t, domain="prose", mechanism=n)))
    for suite, t in tasks:
        depth = len(t["teacher"]) if suite != "w38/w39-prose-dev" else 3
        data_null = has_null([t["public"], t["query"], t.get("answer")])
        sc = S4.scope(t["public"], t["query"], depth)
        assert not any(bare_null(x) for x in sc["tools"]), "bare null constant in a v4 scope"
        s = summary.setdefault(suite.split(":")[0], dict(tasks=0, null_data=0, differential=0, affected=0))
        s["tasks"] += 1
        if not data_null:
            continue
        s["null_data"] += 1
        pre = any(y is None for _, y in t["public"]) or t.get("answer") is None
        pub = [(x, y) for x, y in t["public"]]
        r4 = V4._share(pub, t["query"], t.get("answer"), sc["tools"], depth, "exhaustive")
        rs = sh._share(pub, t["query"], t.get("answer"), sc["tools"], depth, "exhaustive")
        sig = lambda r: (r["label"], r.get("k"), r.get("fitting"), r.get("answers"), r.get("reason"))
        diff = sig(r4) != sig(rs) or pre
        s["differential"] += 1; s["affected"] += int(diff)
        rows.append(dict(suite=suite, domain=t["domain"], mechanism=t["mechanism"], v4=sig(r4), shadow=sig(rs), precheck_null=pre,
                         affected=diff))
        if time.perf_counter() - t0 > a.max_s:
            summary["_partial"] = True
            break
    status = "PARTIAL_AT_CAP" if summary.get("_partial") else "COMPLETE"
    Path(a.out).write_text(json.dumps(dict(summary=summary, rows=rows), indent=1, default=repr))
    print(json.dumps(summary, indent=1))
    print("affected:", [(r["suite"], r["mechanism"], r["v4"], r["shadow"]) for r in rows if r["affected"]][:20])
    WE.ledger_append(dict(run="w40-v4-none-audit", wall_s=time.perf_counter() - t0, status=status))


if __name__ == "__main__":
    main()
