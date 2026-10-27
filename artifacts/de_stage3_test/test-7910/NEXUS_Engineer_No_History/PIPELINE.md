# Pipeline for project test-7910 (NEXUS_Engineer_No_History)

Outcome: **COMPLETED_VERIFIED**

Run: `python pipeline.py --landing <batch dir> --state <state dir> --config config.json` once per batch, in order.
Outputs (state/lake.db): gold_carrier_volume, gold_inventory, gold_sla, gold_status_counts, gold_warehouse_revenue, late_events, quarantine, silver_manifest, silver_orders

## Implementation decisions
* `ts_parse` = `utc`
* `cdc_apply` = `event_time`
* `cdc_incremental` = `rebuild`
* `deletes` = `soft_and_hard`
* `fx` = `table`
* `weight_parse` = `quarantine`
* `units` = `table`
* `drift` = `alias`
* `bronze_dedup` = `dedup`
* `dims_load` = `replace`
* `revenue_join` = `semi_join`
* `sla_window` = `apply`
* `carrier_uncovered` = `include`
* `bucket_uncovered` = `other`

## Clarifications
* carrier_volume:CANCELLED -> include

## Verification
* PASS schema_and_primary_keys: missing [] duplicate keys []
* PASS idempotent_rerun: tables changed []
* PASS duplicate_delivery_invariance: differs []
* PASS crash_restart_equivalence: differs []
* PASS seq_relabel_invariance: differs []
* PASS utc_offset_invariance: differs []
* PASS incremental_equals_full_refresh: differs []
* PASS currency_representation_invariance: differs []
* PASS unit_representation_invariance: differs []
* PASS quarantine_conservation: lost 0 malformed-in-silver 0 wrong-reason 0
* PASS deletion_contract: deleted-but-live 0 inventory_ok True
* PASS shipment_split_invariance: differs []
* PASS late_event_removal_invariance: late set ok True; differs []

## Limits
* Checks cover the visible batches only; batch semantics are taken from docs/spec.json.
