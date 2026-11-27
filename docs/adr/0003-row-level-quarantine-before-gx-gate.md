# Single-Contract DuckDB SQL Quality Gate with Row-Level Quarantine

Status: accepted

Great Expectations (GX Core) validates datasets at the table level rather than splitting individual corrupt rows, and adding `great-expectations` pulls heavy runtime dependencies (`pandas`, `numpy`, `scipy`, `sqlalchemy`) while duplicating SQL row-splitting logic. Instead, `src/ducklake/` defines validation rules once behind a narrow `QualityGate` interface executed in DuckDB SQL: failing rows are routed to `lakehouse/quarantine/<entity>/` with `_failure_reason`, `rule_id`, and `_batch_id`, and dataset-level circuit-breaker checks emit `PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED` before Gold promotion. On `BLOCKED`, the previous verified Gold snapshot remains live (`stale-while-revalidate`), while GX Core remains an optional future adapter behind the same `QualityGate` interface.
