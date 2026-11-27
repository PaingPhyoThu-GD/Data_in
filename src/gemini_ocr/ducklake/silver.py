"""
Silver layer transformations and natural-key deduplication in an ephemeral DuckDB session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from .adapters.base import hash_payload


def _load_bronze_rows(conn: duckdb.DuckDBPyConnection, bronze_files: list[Path]) -> list[dict[str, Any]]:
    if not bronze_files:
        return []
    paths_sql = ", ".join(f"'{p.as_posix().replace(chr(39), chr(39)*2)}'" for p in bronze_files)
    rows = conn.execute(
        f"""
        SELECT _batch_id, _ingested_at, _record_key, _is_test_artifact, payload_json
        FROM read_parquet([{paths_sql}])
        """
    ).fetchall()
    return [
        {
            "_batch_id": r[0],
            "_ingested_at": r[1],
            "_record_key": r[2],
            "_is_test_artifact": bool(r[3]),
            "payload": json.loads(r[4]),
        }
        for r in rows
    ]


def build_silver_tables(
    conn: duckdb.DuckDBPyConnection,
    bronze_files_by_source: dict[str, list[Path]],
) -> dict[str, str]:
    """
    Create and deduplicate all pre-commit Silver tables inside `conn`.
    Returns a mapping of entity name -> table name in `conn`.
    """
    entities: dict[str, str] = {}

    # 1. gemini_ocr -> silver_ocr_extractions
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_ocr (
            run_key VARCHAR, filename VARCHAR, image_index INTEGER,
            text VARCHAR, language VARCHAR, confidence DOUBLE, error_message VARCHAR,
            processed_at TIMESTAMPTZ, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    ocr_rows: list[tuple[Any, ...]] = []
    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("gemini_ocr", [])):
        p = rec["payload"]
        run_key = rec["_record_key"]
        processed_at = p.get("date")
        respond_items = p.get("respond") if isinstance(p.get("respond"), list) else []
        for idx, item in enumerate(respond_items):
            if not isinstance(item, dict):
                continue
            raw_fname = str(item.get("filename") or f"image_{idx}")
            fname = Path(raw_fname).name
            img_idx = int(item.get("image_index") if item.get("image_index") is not None else idx)
            conf_raw = item.get("confidence", 1.0)
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = -1.0
            err_msg = item.get("error")
            ocr_rows.append(
                (
                    run_key,
                    fname,
                    img_idx,
                    str(item.get("text") or ""),
                    str(item.get("language") or "unknown"),
                    conf,
                    str(err_msg) if err_msg is not None else None,
                    processed_at,
                    rec["_batch_id"],
                    rec["_ingested_at"],
                    rec["_is_test_artifact"],
                )
            )
    if ocr_rows:
        conn.executemany(
            "INSERT INTO _raw_ocr VALUES (?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            ocr_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_ocr_extractions AS
        SELECT run_key, filename, image_index, text, language, confidence, error_message,
               processed_at, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY run_key, filename, image_index ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_ocr
        ) WHERE _rn = 1
        """
    )
    entities["ocr_extractions"] = "silver_ocr_extractions"

    # 2. telegram_parser -> service_notices, messages, reactions
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_tg_notices (
            chat_title VARCHAR, message_id BIGINT, notice_date_text VARCHAR, notice_text VARCHAR,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_tg_messages (
            chat_title VARCHAR, message_id BIGINT, from_name VARCHAR, message_ts TIMESTAMPTZ,
            reply_to_message_id BIGINT, forwarded_from VARCHAR, text VARCHAR,
            has_media BOOLEAN, media_type VARCHAR, media_path VARCHAR, reaction_count INTEGER,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_tg_reactions (
            chat_title VARCHAR, message_id BIGINT, emoji VARCHAR, reaction_count INTEGER,
            users_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ
        )
        """
    )
    notice_rows: list[tuple[Any, ...]] = []
    msg_rows: list[tuple[Any, ...]] = []
    react_rows: list[tuple[Any, ...]] = []
    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("telegram_parser", [])):
        p = rec["payload"]
        chat_title = str(p.get("chat_title") or "Unknown Chat")
        for m in p.get("messages") or []:
            if not isinstance(m, dict):
                continue
            msg_id = int(m.get("id") or 0)
            m_type = str(m.get("type") or "message")
            if m_type == "service":
                notice_rows.append(
                    (
                        chat_title,
                        msg_id,
                        str(m.get("date") or ""),
                        str(m.get("text") or ""),
                        rec["_batch_id"],
                        rec["_ingested_at"],
                        rec["_is_test_artifact"],
                    )
                )
                continue
            media = m.get("media") if isinstance(m.get("media"), dict) else None
            msg_rows.append(
                (
                    chat_title,
                    msg_id,
                    m.get("from_name"),
                    m.get("date"),
                    m.get("reply_to_message_id"),
                    m.get("forwarded_from"),
                    str(m.get("text") or ""),
                    media is not None,
                    str(media.get("type")) if media else None,
                    str(media.get("file_path")) if media and media.get("file_path") else None,
                    int(m.get("reaction_count") if m.get("reaction_count") is not None else 0),
                    rec["_batch_id"],
                    rec["_ingested_at"],
                    rec["_is_test_artifact"],
                )
            )
            for rx in m.get("reactions") or []:
                if isinstance(rx, dict):
                    react_rows.append(
                        (
                            chat_title,
                            msg_id,
                            str(rx.get("emoji") or ""),
                            int(rx.get("count") if rx.get("count") is not None else 0),
                            json.dumps(rx.get("users") or [], ensure_ascii=False),
                            rec["_batch_id"],
                            rec["_ingested_at"],
                        )
                    )
    if notice_rows:
        conn.executemany(
            "INSERT INTO _raw_tg_notices VALUES (?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            notice_rows,
        )
    if msg_rows:
        conn.executemany(
            "INSERT INTO _raw_tg_messages VALUES (?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?, ?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            msg_rows,
        )
    if react_rows:
        conn.executemany(
            "INSERT INTO _raw_tg_reactions VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            react_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_telegram_service_notices AS
        SELECT chat_title, message_id, notice_date_text, notice_text, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY chat_title, message_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_tg_notices
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_telegram_messages AS
        SELECT chat_title, message_id, from_name, message_ts, reply_to_message_id, forwarded_from,
               text, has_media, media_type, media_path, reaction_count, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY chat_title, message_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_tg_messages
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_telegram_reactions AS
        SELECT chat_title, message_id, emoji, reaction_count, users_json, _batch_id, _ingested_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY chat_title, message_id, emoji ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_tg_reactions
        ) WHERE _rn = 1
        """
    )
    entities["telegram_service_notices"] = "silver_telegram_service_notices"
    entities["telegram_messages"] = "silver_telegram_messages"
    entities["telegram_reactions"] = "silver_telegram_reactions"

    # 3. database_parser -> generic tables/rows + conditional sales_customers / sales_orders
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_db_tables (
            database_name VARCHAR, table_name VARCHAR, format VARCHAR, row_count INTEGER,
            columns_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_db_rows (
            database_name VARCHAR, table_name VARCHAR, _row_hash VARCHAR, row_payload_json VARCHAR,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_sales_customers (
            customer_id VARCHAR, customer_name VARCHAR, segment VARCHAR, email VARCHAR, city VARCHAR,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_sales_orders (
            order_id VARCHAR, customer_id VARCHAR, order_date DATE, total_amount DOUBLE,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    db_table_rows: list[tuple[Any, ...]] = []
    db_data_rows: list[tuple[Any, ...]] = []
    cust_rows: list[tuple[Any, ...]] = []
    order_rows: list[tuple[Any, ...]] = []

    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("database_parser", [])):
        p = rec["payload"]
        db_name = str(p.get("database_name") or "unknown")
        fmt = str(p.get("format") or "unknown")
        tables = p.get("tables") if isinstance(p.get("tables"), dict) else {}
        for t_key, t_obj in tables.items():
            if not isinstance(t_obj, dict):
                continue
            t_name = str(t_obj.get("table_name") or t_key)
            cols = t_obj.get("columns") or []
            rows_list = t_obj.get("rows") or []
            db_table_rows.append(
                (
                    db_name,
                    t_name,
                    fmt,
                    int(t_obj.get("row_count") if t_obj.get("row_count") is not None else len(rows_list)),
                    json.dumps(cols, ensure_ascii=False),
                    rec["_batch_id"],
                    rec["_ingested_at"],
                    rec["_is_test_artifact"],
                )
            )
            t_lower = t_name.lower()
            for r in rows_list:
                if not isinstance(r, dict):
                    continue
                r_hash = hash_payload(r)
                r_json = json.dumps(r, ensure_ascii=False, sort_keys=True, default=str)
                db_data_rows.append(
                    (
                        db_name,
                        t_name,
                        r_hash,
                        r_json,
                        rec["_batch_id"],
                        rec["_ingested_at"],
                        rec["_is_test_artifact"],
                    )
                )
                if t_lower == "customers" and ("customer_id" in r):
                    cust_rows.append(
                        (
                            str(r.get("customer_id")),
                            str(r.get("name") or r.get("customer_name") or "Unknown"),
                            str(r.get("segment") or "unknown"),
                            r.get("email"),
                            r.get("city"),
                            rec["_batch_id"],
                            rec["_ingested_at"],
                            rec["_is_test_artifact"],
                        )
                    )
                elif t_lower in {"sales_table", "sales", "orders"} and (
                    "order_id" in r or "total_amount" in r or "order_amount" in r
                ):
                    raw_amt = r.get("total_amount") if "total_amount" in r else r.get("order_amount")
                    try:
                        amt_val = float(raw_amt) if raw_amt is not None else None
                    except (TypeError, ValueError):
                        amt_val = None
                    order_rows.append(
                        (
                            str(r["order_id"]) if r.get("order_id") is not None else None,
                            str(r["customer_id"]) if r.get("customer_id") is not None else None,
                            r.get("order_date"),
                            amt_val,
                            rec["_batch_id"],
                            rec["_ingested_at"],
                            rec["_is_test_artifact"],
                        )
                    )
    if db_table_rows:
        conn.executemany(
            "INSERT INTO _raw_db_tables VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            db_table_rows,
        )
    if db_data_rows:
        conn.executemany(
            "INSERT INTO _raw_db_rows VALUES (?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            db_data_rows,
        )
    if cust_rows:
        conn.executemany(
            "INSERT INTO _raw_sales_customers VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            cust_rows,
        )
    if order_rows:
        conn.executemany(
            "INSERT INTO _raw_sales_orders VALUES (?, ?, TRY_CAST(? AS DATE), ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            order_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_database_tables AS
        SELECT database_name, table_name, format, row_count, columns_json, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY database_name, table_name ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_db_tables
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_database_rows AS
        SELECT database_name, table_name, _row_hash, row_payload_json, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY database_name, table_name, _row_hash ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_db_rows
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_sales_customers AS
        SELECT customer_id, customer_name, segment, email, city, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_sales_customers
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_sales_orders AS
        SELECT order_id, customer_id, order_date, total_amount, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY COALESCE(order_id, '__null__' || CAST(rowid AS VARCHAR)) ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_sales_orders
        ) WHERE _rn = 1
        """
    )
    entities["database_tables"] = "silver_database_tables"
    entities["database_rows"] = "silver_database_rows"
    entities["sales_customers"] = "silver_sales_customers"
    entities["sales_orders"] = "silver_sales_orders"

    # 4. youtube_parser -> channels & videos
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_yt_channels (
            channel_key VARCHAR, channel_id VARCHAR, channel_name VARCHAR, handle VARCHAR,
            subscriber_count BIGINT, total_videos_count INTEGER, is_verified BOOLEAN, custom_url VARCHAR,
            scraped_at TIMESTAMPTZ, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_yt_videos (
            video_id VARCHAR, channel_key VARCHAR, title VARCHAR, url VARCHAR,
            duration_seconds INTEGER, view_count BIGINT, published_time_text VARCHAR,
            is_short BOOLEAN, thumbnail_url VARCHAR,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    yt_ch_rows: list[tuple[Any, ...]] = []
    yt_vid_rows: list[tuple[Any, ...]] = []
    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("youtube_parser", [])):
        p = rec["payload"]
        ch = p.get("channel_info") if isinstance(p.get("channel_info"), dict) else {}
        ch_name = str(ch.get("channel_name") or "Unknown")
        ch_key = str(ch.get("channel_id") or ch.get("handle") or ch_name)
        yt_ch_rows.append(
            (
                ch_key,
                ch.get("channel_id"),
                ch_name,
                ch.get("handle"),
                ch.get("subscriber_count"),
                ch.get("total_videos_count"),
                bool(ch.get("is_verified", False)),
                ch.get("custom_url"),
                p.get("scraped_at"),
                rec["_batch_id"],
                rec["_ingested_at"],
                rec["_is_test_artifact"],
            )
        )
        for v in p.get("videos") or []:
            if not isinstance(v, dict) or not v.get("video_id"):
                continue
            yt_vid_rows.append(
                (
                    str(v["video_id"]),
                    ch_key,
                    str(v.get("title") or ""),
                    str(v.get("url") or ""),
                    v.get("duration_seconds"),
                    v.get("view_count"),
                    v.get("published_time_text"),
                    bool(v.get("is_short", False)),
                    v.get("thumbnail_url"),
                    rec["_batch_id"],
                    rec["_ingested_at"],
                    rec["_is_test_artifact"],
                )
            )
    if yt_ch_rows:
        conn.executemany(
            "INSERT INTO _raw_yt_channels VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            yt_ch_rows,
        )
    if yt_vid_rows:
        conn.executemany(
            "INSERT INTO _raw_yt_videos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            yt_vid_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_youtube_channels AS
        SELECT channel_key, channel_id, channel_name, handle, subscriber_count, total_videos_count,
               is_verified, custom_url, scraped_at, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY channel_key ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_yt_channels
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_youtube_videos AS
        SELECT video_id, channel_key, title, url, duration_seconds, view_count, published_time_text,
               is_short, thumbnail_url, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_yt_videos
        ) WHERE _rn = 1
        """
    )
    entities["youtube_channels"] = "silver_youtube_channels"
    entities["youtube_videos"] = "silver_youtube_videos"

    # 5. survey_extractor -> surveys, questions, responses, answers + survey_runs audit
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_surveys (
            survey_id VARCHAR, title VARCHAR, file_name VARCHAR, created_at TIMESTAMPTZ,
            total_questions INTEGER, total_responses INTEGER, valid_responses INTEGER, invalid_responses INTEGER,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_survey_questions (
            survey_id VARCHAR, question_id VARCHAR, column_index INTEGER, question_text VARCHAR,
            field_type VARCHAR, detected_options_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_survey_responses (
            survey_id VARCHAR, response_id VARCHAR, row_number INTEGER, submitted_at VARCHAR,
            email VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_survey_answers (
            survey_id VARCHAR, response_id VARCHAR, question_id VARCHAR,
            answer_text VARCHAR, answer_list_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_survey_runs (
            survey_id VARCHAR, title VARCHAR, valid_responses INTEGER, captured_responses INTEGER,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ
        )
        """
    )
    srv_rows: list[tuple[Any, ...]] = []
    srv_q_rows: list[tuple[Any, ...]] = []
    srv_r_rows: list[tuple[Any, ...]] = []
    srv_a_rows: list[tuple[Any, ...]] = []
    srv_run_rows: list[tuple[Any, ...]] = []
    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("survey_extractor", [])):
        p = rec["payload"]
        meta = p.get("metadata") if isinstance(p.get("metadata"), dict) else {}
        s_id = str(p.get("survey_id") or meta.get("survey_id") or "unknown")
        valid_cnt = int(meta.get("valid_responses") or 0)
        responses = p.get("responses") if isinstance(p.get("responses"), list) else (p.get("sample_responses") or [])
        srv_run_rows.append(
            (s_id, str(meta.get("title") or ""), valid_cnt, len(responses), rec["_batch_id"], rec["_ingested_at"])
        )
        srv_rows.append(
            (
                s_id,
                str(meta.get("title") or ""),
                str(meta.get("file_name") or ""),
                meta.get("created_at"),
                int(meta.get("total_questions") or 0),
                int(meta.get("total_responses") or 0),
                valid_cnt,
                int(meta.get("invalid_responses") or 0),
                rec["_batch_id"],
                rec["_ingested_at"],
                rec["_is_test_artifact"],
            )
        )
        for q in p.get("questions") or []:
            if isinstance(q, dict):
                srv_q_rows.append(
                    (
                        s_id,
                        str(q.get("question_id") or ""),
                        int(q.get("column_index") or 0),
                        str(q.get("question_text") or ""),
                        str(q.get("field_type") or "text"),
                        json.dumps(q.get("detected_options") or [], ensure_ascii=False),
                        rec["_batch_id"],
                        rec["_ingested_at"],
                    )
                )
        for r in responses:
            if not isinstance(r, dict):
                continue
            r_id = str(r.get("response_id") or "")
            srv_r_rows.append(
                (
                    s_id,
                    r_id,
                    int(r.get("row_number") or 0),
                    r.get("submitted_at"),
                    r.get("email"),
                    rec["_batch_id"],
                    rec["_ingested_at"],
                )
            )
            answers = r.get("answers") if isinstance(r.get("answers"), dict) else {}
            for q_id, val in answers.items():
                if isinstance(val, list):
                    ans_text = ", ".join(str(x) for x in val)
                    ans_list = json.dumps(val, ensure_ascii=False)
                else:
                    ans_text = str(val) if val is not None else None
                    ans_list = None
                srv_a_rows.append(
                    (s_id, r_id, str(q_id), ans_text, ans_list, rec["_batch_id"], rec["_ingested_at"])
                )
    if srv_rows:
        conn.executemany(
            "INSERT INTO _raw_surveys VALUES (?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            srv_rows,
        )
    if srv_q_rows:
        conn.executemany(
            "INSERT INTO _raw_survey_questions VALUES (?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            srv_q_rows,
        )
    if srv_r_rows:
        conn.executemany(
            "INSERT INTO _raw_survey_responses VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            srv_r_rows,
        )
    if srv_a_rows:
        conn.executemany(
            "INSERT INTO _raw_survey_answers VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            srv_a_rows,
        )
    if srv_run_rows:
        conn.executemany(
            "INSERT INTO _raw_survey_runs VALUES (?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            srv_run_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_surveys AS
        SELECT survey_id, title, file_name, created_at, total_questions, total_responses,
               valid_responses, invalid_responses, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY survey_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_surveys
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_survey_questions AS
        SELECT survey_id, question_id, column_index, question_text, field_type, detected_options_json, _batch_id, _ingested_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY survey_id, question_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_survey_questions
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_survey_responses AS
        SELECT survey_id, response_id, row_number, submitted_at, email, _batch_id, _ingested_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY survey_id, response_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_survey_responses
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_survey_answers AS
        SELECT survey_id, response_id, question_id, answer_text, answer_list_json, _batch_id, _ingested_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY survey_id, response_id, question_id ORDER BY _ingested_at DESC) AS _rn
            FROM _raw_survey_answers
        ) WHERE _rn = 1
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_survey_runs AS
        SELECT survey_id, title, valid_responses, captured_responses, _batch_id, _ingested_at
        FROM _raw_survey_runs
        """
    )
    entities["surveys"] = "silver_surveys"
    entities["survey_questions"] = "silver_survey_questions"
    entities["survey_responses"] = "silver_survey_responses"
    entities["survey_answers"] = "silver_survey_answers"
    entities["survey_runs"] = "silver_survey_runs"

    # 6. telemetry -> silver_telemetry_events
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE _raw_telemetry (
            event_id VARCHAR, site_id VARCHAR, source_mode VARCHAR, event_ts TIMESTAMPTZ,
            timestamp_ms BIGINT, visitor_hash VARCHAR, session_id VARCHAR, path VARCHAR, method VARCHAR,
            status_code INTEGER, latency_ms DOUBLE, duration_seconds DOUBLE, referrer_domain VARCHAR,
            country_code VARCHAR, browser VARCHAR, os VARCHAR, device_type VARCHAR,
            _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN
        )
        """
    )
    tel_rows: list[tuple[Any, ...]] = []
    for rec in _load_bronze_rows(conn, bronze_files_by_source.get("telemetry", [])):
        p = rec["payload"]
        tel_rows.append(
            (
                str(p.get("id") or rec["_record_key"]),
                str(p.get("site_id") or "default"),
                str(p.get("source_mode") or "file_upload"),
                p.get("datetime_utc"),
                p.get("timestamp"),
                str(p.get("visitor_hash") or "anonymous"),
                str(p.get("session_id") or "session_default"),
                str(p.get("path") or "/"),
                str(p.get("method") or "GET"),
                p.get("status_code"),
                p.get("latency_ms"),
                float(p.get("duration_seconds") or 0.0),
                str(p.get("referrer_domain") or "direct"),
                str(p.get("country_code") or "UNKNOWN"),
                str(p.get("browser") or "Unknown"),
                str(p.get("os") or "Unknown"),
                str(p.get("device_type") or "desktop"),
                rec["_batch_id"],
                rec["_ingested_at"],
                rec["_is_test_artifact"],
            )
        )
    if tel_rows:
        conn.executemany(
            "INSERT INTO _raw_telemetry VALUES (?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ), ?)",
            tel_rows,
        )
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE silver_telemetry_events AS
        SELECT event_id, site_id, source_mode, event_ts, timestamp_ms, visitor_hash, session_id,
               path, method, status_code, latency_ms, duration_seconds, referrer_domain,
               country_code, browser, os, device_type, _batch_id, _ingested_at, _is_test_artifact
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY site_id, timestamp_ms, path, method, visitor_hash, session_id, status_code, latency_ms
                ORDER BY _ingested_at DESC
            ) AS _rn
            FROM _raw_telemetry
        ) WHERE _rn = 1
        """
    )
    entities["telemetry_events"] = "silver_telemetry_events"

    return entities
