"""Phase 8 Stage 1 dev check (NOT LOCKED): what the fixed screen shortlists from F0 on development pool projects."""
import json, time
from nexus.de_phase8 import lineage8 as L8, seeds8 as S
b = S.RANGES[("agi8de", "dev")].start + 1000
blk = dict(train=range(b, b + 400), admit=range(b + 400, b + 550), pool=range(b + 550, b + 600), roll=range(b + 600, b + 800), down=range(b + 800, b + 900),
           conf=range(b + 900, b + 1000))
lin = L8.Lineage("dev_screen", "Full", blk, L8.WS / "dev" / "screen", time.time() + 60, "screen")
lin.cursor["pool"] = 12
rec = {}
pick = lin.screen(0, rec)
print(json.dumps(rec["screen"], default=str)[:1500])
