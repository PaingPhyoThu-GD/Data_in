# Context Map

## Contexts

- [Ingestion Services](./src/CONTEXT.md) — extracts structured data from raw documents, chat exports, databases, YouTube channels, Google Forms surveys, and web traffic telemetry
- [DuckLake Lakehouse](./src/ducklake/CONTEXT.md) — curates, validates, and aggregates extracted datasets through Bronze, Silver, Quality Gate, and Gold stages

## Relationships

- **Ingestion Services → DuckLake Lakehouse**: Ingestion Services emit completed **Extraction Runs** (and persisted **Telemetry Events** / **Survey Submissions**); DuckLake Lakehouse consumes them into **Bronze** without altering upstream service internals.
