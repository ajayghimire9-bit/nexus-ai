"""Phase 10E Stage 4 loader development check (NOT LOCKED; the 16 Phase 10C external DEV-audit tasks; no search, no repair).
  python scripts/agi10e_loader_dev.py
For each task: extload10e.load on the text AS WRITTEN -> funnel stage reached, notes (which general rules fired), and whether the
lifted stages lower to canonical text that lifts back identically and executes on DuckDB over the bound input."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase6 import engines6 as E, ir6  # noqa: E402
from nexus.de_phase10e import extload10e as X  # noqa: E402
import agi10c_external as EXT  # noqa: E402


def main():
    for t in EXT.TASKS:
        L = X.load(t["legacy"], t["lang"], t["tables"])
        rt = None
        if L.ok:
            try:
                back = [ir6.lift(X.lower_stage(s), "sql") for s in L.stages]
                cur, hdr = L.input_rows, L.header
                for s in L.stages:
                    res = E.ENGINES["duckdb"]().run(ir6.lower(s, "duckdb"), hdr, cur, {})
                    cur = [{c: ("" if v is None else str(v)) for c, v in r.items()} for r in res["clean"]]
                    hdr = list(cur[0].keys()) if cur else hdr
                rt = dict(roundtrip=back == L.stages, duckdb_rows=len(cur))
            except Exception as e:                                   # noqa: BLE001
                rt = dict(error=f"{type(e).__name__}: {str(e)[:100]}")
        print(t["id"], t["lang"], X.describe(L), json.dumps(rt), json.dumps(L.stages)[:300] if L.ok else "", flush=True)


if __name__ == "__main__":
    main()
