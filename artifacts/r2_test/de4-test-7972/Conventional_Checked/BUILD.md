# de4-test-7972 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "transactional", "dedup": "none", "deletes": "hard_only", "discount_unit": "percent_only", "fx": "table", "fx_unknown": "error", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
