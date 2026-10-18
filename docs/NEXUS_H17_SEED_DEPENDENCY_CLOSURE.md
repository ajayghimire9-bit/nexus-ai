# H17 historical seed dependency closure — source only

Base: `07a91522f9ba443f9fb5ac7af1bb2cb99d1a171c`.
Branch: `codex/h17-seed-dependency-closure`.

The previous review certified27 explicit historical expressions and left40
unsupported records, including duplicate collision guards. This follow-through
extends arithmetic certificates to finite products, tuple binding, helper
assignments, bounded loops and imported constants/delegates. It does not run
historical Python: no module imports, config loaders, file-reading calls or
scientific operations from the reviewed sources are allowed. Unsupported
syntax, cycles, missing dependencies and operation limits fail closed.

For an inherited `load_*config` reference, bind the module's explicit committed
YAML path/default and parse that mapping directly. The historical loader is
never invoked and its runtime validation/authorization is **not** certified.
Record the YAML hash as a dependency. An unbound or non-config path is rejected.
This distinguishes reconstructing historical registration arithmetic from
executing the historical experimental entry points.

Every source and imported dependency is read from the **same historical Git
commit** as its configuration. Record dependency hashes and compare every
resulting historical seed with the existing conservative windows. Preserve old
captures and reservations; do not infer that independently defined streams are
unique merely from their union. Collision guards are sliced to own-set
declarations, not executed; this cannot certify the historical collision
checker's runtime behavior. Imported guards are not evidence of new seed draws.

Expand the inventory to previously inherited seed-group helpers. Failures in
those older helpers and metadata outside recognized registration fields remain
explicit blockers, rather than substituting a guessed constant or claiming
global completeness. This review alone cannot lock H17 or authorize execution.

No simulator, inference, training, new physics, numerical H17 registration,
allocation change or H14–H16 rerun. Five-source/t12 design remains
62,360 real /174,080 imagined /300-second proposed cap. Actual new counts are
zero; session ledger stays305.842 used /3294.158 remaining.

After tests and implementation commit, capture metadata with:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/review_h17_seed_dependencies.py --output artifacts/h17_seed_dependency_closure.json
```

Results and exact remaining gaps will be appended after capture. No scientific
result is collected or reinterpreted by this audit.
