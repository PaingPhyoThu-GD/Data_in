# DuckLake Lakehouse

Analytical lakehouse context that preserves raw extraction outputs, conforms and validates domain entities, and publishes business-ready marts.

## Language

### Storage Layers

**Bronze**:
The immutable, append-only landing layer preserving unmodified extracted payloads wrapped with ingestion provenance metadata.
_Avoid_: Raw bucket, staging

**Silver**:
The conformed, typed, and deduplicated layer representing clean business entities across all upstream sources.
_Avoid_: Clean table, warehouse layer

**Gold**:
The curated, aggregated analytics layer organized into business marts for executive reporting and BI tools.
_Avoid_: Reporting DB, summary cache

### Ingestion & Deduplication

**Ingestion Batch**:
A tracked lakehouse load operation that reads new upstream payloads into Bronze and advances them through downstream stages.
_Avoid_: Sync job, run

**Entity Record**:
A unique real-world subject (such as a YouTube video, Telegram message, survey response, or customer) identified by its natural business key in Silver, where newer observations supersede older ones.
_Avoid_: Row, item, log entry

### Data Quality & Analytics

**Quality Gate**:
The mandatory validation checkpoint between Silver and Gold that blocks unverified or corrupted datasets from entering business marts.
_Avoid_: Sanity check, linter

**Quarantine**:
The isolated holding area for records that fail validation rules, recorded alongside the reason for rejection so valid records in the same batch are not blocked.
_Avoid_: Error log, dead-letter queue, trash

**Gold Mart**:
A purpose-built analytical dataset tailored to a specific business domain or cross-source view.
_Avoid_: View, report, dashboard table

**Daily Activity Spine**:
A calendar-aligned cross-channel Gold Mart summarizing daily activity volumes and key outcomes across all upstream sources on a shared date axis.
_Avoid_: Unified join, master table
