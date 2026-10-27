# dev-934 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "lww_tombstones", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "hard_only", "fx": "table", "gold_maintenance": "delta_no_retract", "lateness": "none", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "iso_only", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
