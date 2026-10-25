# QuixBugs (vendored subset)

Source: https://github.com/jkoppel/QuixBugs (commit in `UPSTREAM_COMMIT`), MIT
license (`LICENSE`, Copyright 2017-2019 James Koppel). Lin, Koppel, Chen and
Solar-Lezama, "QuixBugs: a multi-lingual program repair benchmark set based on
the Quixey Challenge", SPLASH Companion 2017.

Vendored: the 31 buggy Python programs that have JSON test cases, and those
test cases. The fixed reference programs are deliberately NOT vendored; the
NEXUS repair arena grades candidate repairs only on the benchmark's own
held-out test cases.
