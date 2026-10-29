"""Seed ranges for MI-3 (acceptance reliability + discovery efficiency diagnostic; NOT LOCKED). Fresh ranges above every
registered range (max registered stop 28400 = mi2/btest, which stays closed) and above every spent seed (max 27099); checked
disjoint at import. Episode identity is (family, seed) through mi_ocean's RNG key.
  dev                 development diagnosis, repair design, runtime calibration (development data; reusable)
  accept_audit        ONE-USE independent acceptance audit (240 constructed candidates; claimed whole on first use)
  screen_calibration  Stage 2 screening calibration pool (development data; reusable)
  discovery           Stage 3 discovery pools (development data)
  selection           Stage 3 within-run winner selection pools (development data)
  winner_eval         ONE-USE Stage 4 fresh winner evaluation (claimed whole on first use)"""
from nexus import mi2_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("mi3", "dev"): range(28400, 28800), ("mi3", "accept_audit"): range(28800, 29100),
          ("mi3", "screen_calibration"): range(29100, 29400), ("mi3", "discovery"): range(29400, 29700),
          ("mi3", "selection"): range(29700, 29900), ("mi3", "winner_eval"): range(29900, 30000)}
R.REGISTRY.update(RANGES)
R.ONE_USE -= {("mi3", "dev"), ("mi3", "screen_calibration"), ("mi3", "discovery"), ("mi3", "selection")}
R.ONE_USE |= {("mi3", "accept_audit"), ("mi3", "winner_eval")}
R._check_disjoint()
