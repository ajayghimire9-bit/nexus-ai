# val-7924 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "offsets_first", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "iso_only", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
