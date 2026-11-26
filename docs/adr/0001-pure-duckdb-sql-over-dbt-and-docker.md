# Parquet-First Local DuckDB SQL Over dbt-duckdb and Docker Initially

Status: accepted

Although `ducklake_medallion_pipeline_plan.md` describes `dbt-duckdb`, Apache Airflow, and Metabase containers, we chose to implement `src/ducklake/` using local Python and pure DuckDB SQL files (Option A). To prevent Windows single-writer file-lock collisions between FastAPI readers and CLI pipeline runs, committed Bronze, Silver, Quarantine, and Gold datasets are stored as atomic Parquet partitions tracked by a manifest, read via short-lived `:memory:` DuckDB connections, and optionally exported to a disposable `lakehouse/ducklake.duckdb` snapshot at the end of a batch. This avoids container, `dbt-core`, and lock-contention overhead while keeping the SQL transforms and Parquet/DuckDB artifacts directly portable to `dbt-duckdb`, Airflow, and Metabase later.
