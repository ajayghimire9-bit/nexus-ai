# de4-dev-977 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "offsets_first", "dedup": "by_msg_id", "deletes": "hard_only", "discount_unit": "percent_only", "fx": "none", "fx_unknown": "quarantine", "gap_handling": "wait_contiguous", "gold_maintenance": "delta_no_retract", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
