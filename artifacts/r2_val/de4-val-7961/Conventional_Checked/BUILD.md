# de4-val-7961 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "offsets_first", "dedup": "by_msg_id", "deletes": "soft_and_hard", "discount_unit": "percent_only", "fx": "none", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "delta_no_retract", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
