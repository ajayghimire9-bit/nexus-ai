"""Wave 40 Step 6 (NOT LOCKED; owner-requested post-use audit of a CONSUMED sealed split): the PROSE-confirm tasks (Wave 39, claim
wave39/confirm_prose, already spent) on which Fresh-v5's program passed Checker v5 (SCOPE_UNIQUE) yet failed held-out pairs.
Run once, after the Wave 40 Step 5 confirmation, by this runner only (NEXUS_SEALED_HARNESS_TOKEN; every file's SHA-256 checked
against the committed Wave 39 manifest). The audited tasks are marked BURNED (artifacts/external/prose_confirm/BURNED.json): they
can never again serve as sealed or untouched data. Nothing here trains or selects anything.
Per case: public examples, query, the certified program (reproduced by re-running the frozen Wave 39 Fresh-v5 solve in-process;
must match the Wave 39 artifact's certificate and held-out score), kernel verdict summary, every held-out pair (expected, got,
whether the input was labelled unique), and a mechanical classification of the first failing pair:
  * IN_SCOPE_NOT_DISTINGUISHED : some in-scope chain fits the public pairs AND the failing pair (a distinguishing query would have
    exposed the ambiguity; the v5 extra-query warning did not cover this input);
  * OUTSIDE_SCOPE              : no chain within the declared v5 scope fits public + failing pair (the true mechanism is outside
    v5; the certified program is a spurious in-scope fit).
Also: the count of JSON null values over all 129 tasks (for the Checker v4 None audit)."""
import hashlib, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))


def main():
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed PROSE-confirm may be loaded only by this runner (NEXUS_SEALED_HARNESS_TOKEN)")
    import w39_child as C
    import w39_prose as P
    from nexus import checker_kernel_v5 as V5, w38_learn as K, w39_eval as WE, w39_lang as L, w39_scope as S, w40_search as Q
    from w40_v4_none_audit import has_null
    t0 = time.perf_counter()
    man = json.loads((ROOT / "artifacts/external/prose_confirm/MANIFEST.json").read_text())
    art = json.loads((ROOT / "artifacts/w39_prose_confirm.json").read_text())["tasks"]
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave39_prose_confirm"
    nulls, cases = 0, []
    names = sorted(n for n, v in art.items() if v.get("Fresh-v5", {}).get("certified") and not v["Fresh-v5"].get("held_out_verified"))
    for n, h in sorted(man["sha256"].items()):
        b = (vault / f"{n}.json").read_bytes()
        if hashlib.sha256(b).hexdigest() != h:
            raise SystemExit(f"manifest hash mismatch: {n}")
        spec = json.loads(b)
        nulls += int(has_null(spec))
        if n not in names:
            continue
        t, _ = P.convert(spec, True)
        extra = [x for x, _ in t["heldout"][1:17]]

        class Chan:
            def ask(self, m):
                if m["req"] == "check":
                    self.v = V5.check(json.loads(json.dumps(m["evidence"])))
                    return self.v
                return {"error": True}
        ch = Chan()
        ev, meter, info = C.solve(ch, {"public": t["public"], "query": t["query"], "depth": 3, "seed": f"prose:{n}", "prior": None,
                                       "budget": 4_000_000, "extra": extra})
        prog = ev["candidate"]
        rows = []
        uniq = [True] + [e["answers"] == 1 for e in ch.v.get("extra", [])]
        for i, (x, y) in enumerate(t["heldout"]):
            got = L.run(prog, x)
            rows.append(dict(input=x, expected=y, got=got, ok=L.key(got) == L.key(y), labelled_unique=uniq[i] if i < len(uniq) else None,
                             was_extra_query=1 <= i <= 16))
        fail = next(r for r in rows if not r["ok"])
        sc = S.scope(t["public"], t["query"], 3)
        pub2 = t["public"] + [[fail["input"], fail["expected"]]]
        alt = Q.search(pub2, t["query"], sc["tools"], 3, K.cost_matrix(None, sc["tools"]), budget=4_000_000)
        cases.append(dict(name=n, split=man["split"][n], public=t["public"], query=t["query"], certified_program=prog,
                          claimed_answer=ev["claimed_answer"], verdict=dict(label=ch.v["label"], warnings=ch.v.get("warnings"),
                                                                            extra_answer_counts=[e["answers"] for e in ch.v.get("extra", [])]),
                          reproduces_w39=(ch.v["label"] == "SCOPE_UNIQUE" and
                                          abs(sum(r["ok"] for r in rows) / len(rows) - art[n]["Fresh-v5"]["heldout_pass"]) < 1e-9),
                          heldout=rows, first_failure=fail,
                          classification="IN_SCOPE_NOT_DISTINGUISHED" if alt else "OUTSIDE_SCOPE", alternative_program=alt,
                          n_tools=len(sc["tools"])))
    out = dict(audited=names, nulls_in_129_tasks=nulls, cases=cases)
    (ROOT / "artifacts/w40_step6_heldout_audit.json").write_text(json.dumps(out, indent=1, default=repr))
    (ROOT / "artifacts/external/prose_confirm/BURNED.json").write_text(json.dumps(
        {"burned": names, "reason": "Wave 40 Step 6 owner-requested post-use audit: task content read by the audit runner and "
                                    "reported; never usable as sealed or untouched data again"}, indent=1))
    print(json.dumps(dict(audited=names, nulls=nulls, classes=[c["classification"] for c in cases],
                          reproduce=[c["reproduces_w39"] for c in cases])))
    WE.ledger_append(dict(run="w40-step6-heldout-audit", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
