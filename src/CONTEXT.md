# Ingestion Services

Upstream extraction context (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`, `telemetry`) that parses unstructured and semi-structured inputs into standardized domain payloads.

## Language

**Extraction Run**:
A single execution of an ingestion service against one input file, batch of images, or remote channel/project target.
_Avoid_: Job, import session, task

**Source Artifact**:
The raw user-supplied input submitted for extraction, such as an image batch, HTML chat export, database dump, survey CSV, or traffic log.
_Avoid_: Raw blob, attachment, upload

**Service Notice**:
A system-generated timeline or status marker inside a chat export (such as a date divider) rather than a participant-authored message.
_Avoid_: System log, empty message

**Survey Submission**:
A single respondent's completed row of answers mapped against a survey's inferred questions.
_Avoid_: Form entry, survey row

**Telemetry Event**:
A privacy-sanitized record of a single web request or client page interaction.
_Avoid_: Hit, access log, ping

**Log Drain**:
A webhook stream delivering batched server-side HTTP access logs from Vercel into telemetry storage.
_Avoid_: Webhook dump, stream log

**Beacon**:
A lightweight client-side browser ping recording page view path, referrer, and dwell duration.
_Avoid_: Tracker pixel, analytics ping
