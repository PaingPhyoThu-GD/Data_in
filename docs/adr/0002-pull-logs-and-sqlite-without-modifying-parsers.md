# Pull Logs and Telemetry SQLite Without Modifying Upstream Parsers

Status: accepted

Rather than altering the 6 existing ingestion packages in `src/` to emit lakehouse events directly, DuckLake Bronze pulls read-only from `logs/*_log.jsonl` (including `logs/survey_extractor_log.jsonl`, since `logs/surveys.db` is orphaned by `frontend/app.py`), `logs/telemetry.db` via SQLite's online backup API (`sqlite3.Connection.backup()`) to avoid `SQLITE_BUSY` with WAL writes, and a `lakehouse/landing/<source>/` dropzone for standalone CLI exports. Because `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place and telemetry adapters generate fresh UUIDs on re-uploads, Bronze tracks `(record_key, payload_sha256)` watermarks instead of byte offsets and Silver deduplicates telemetry by natural composite key.
