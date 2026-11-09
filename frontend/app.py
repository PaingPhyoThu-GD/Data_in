"""
Frontend Middleware Server for Gemini OCR.
Connects the web frontend to the untouched gemini_ocr backend.
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Import existing backend directly (UNCHANGED BACKEND)
from gemini_ocr import OCRSystem, GeminiMMENOCRComponent, FileImportComponent, MockGeminiClient
from gemini_ocr.config import DEFAULT_BATCH_SIZE, DEFAULT_OCR_PROMPT, DEFAULT_LOG_DIR, GEMINI_API_KEY, DEFAULT_MODEL_NAME
from telegram_parser import TelegramHTMLParser, TelegramChatConverter
from database_parser import DatabaseParser
from youtube_parser import YouTubeChannelParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini_ocr_frontend")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Gemini Myanmar-English OCR",
    description="Clean Single-Page Web Frontend and Middleware for Gemini OCR",
    version="1.0.0",
)

# Enable CORS for flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and uploaded files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the single-page application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_file))


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Return runtime configuration information for the frontend UI."""
    return {
        "default_prompt": DEFAULT_OCR_PROMPT,
        "default_batch_size": DEFAULT_BATCH_SIZE,
        "model_name": DEFAULT_MODEL_NAME,
        "has_api_key": bool(GEMINI_API_KEY and GEMINI_API_KEY.strip()),
    }


@app.post("/api/ocr")
async def process_ocr(
    files: list[UploadFile] = File(...),
    content: Optional[str] = Form(None),
    file_per_batch: int = Form(DEFAULT_BATCH_SIZE),
    mock: bool = Form(False),
) -> JSONResponse:
    """
    Handle uploaded files, invoke the backend OCRSystem, and return the response.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    # Bound batch size between 1 and 10 as specified by client
    batch_size = max(1, min(10, file_per_batch))

    # Create an isolated staging directory for this run
    session_id = uuid.uuid4().hex[:10]
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    file_metadata: list[dict[str, str]] = []

    try:
        for file in files:
            # Preserve original filename
            safe_filename = Path(file.filename or f"image_{len(saved_paths)}.png").name
            dest_path = session_dir / safe_filename

            # Save uploaded content to disk
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_paths.append(str(dest_path.resolve()))
            file_metadata.append({
                "filename": safe_filename,
                "url": f"/uploads/{session_id}/{safe_filename}",
            })

        # Configure OCR Component with user-selected prompt and batch size
        effective_client = MockGeminiClient() if mock else None
        mmen_component = GeminiMMENOCRComponent(
            file_per_batch=batch_size,
            content=content if content and content.strip() else None,
            client=effective_client,
        )

        # Coordinate via existing backend OCRSystem
        system = OCRSystem(mmen_ocr_component=mmen_component)
        gemini_respond = system.operate(saved_paths)

        # Pair results with public URLs
        url_map = {meta["filename"]: meta["url"] for meta in file_metadata}
        enriched_results = []
        for item in gemini_respond.respond:
            item_copy = dict(item)
            fname = Path(item_copy.get("filename", "")).name
            item_copy["url"] = url_map.get(fname, "")
            item_copy["basename"] = fname
            enriched_results.append(item_copy)

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "date": gemini_respond.date.isoformat(),
            "content": gemini_respond.content,
            "batch_size": batch_size,
            "total_files": len(gemini_respond.files),
            "results": enriched_results,
            "files": file_metadata,
        })

    except Exception as exc:
        logger.error(f"Error during OCR processing: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(exc),
            },
        )


@app.get("/api/history")
async def get_history(limit: int = 30) -> list[dict[str, Any]]:
    """
    Read and return past OCR runs from logs/gemini_ocr_log.jsonl in reverse order.
    """
    log_file = DEFAULT_LOG_DIR / "gemini_ocr_log.jsonl"
    if not log_file.exists():
        return []

    records = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        logger.error(f"Failed to read history logs: {exc}")
        return []

    # Return latest first, capped at limit
    records.reverse()
    return records[:limit]


TELEGRAM_LOG_FILE = DEFAULT_LOG_DIR / "telegram_parser_log.jsonl"


def _stage_telegram_photos(session_id: str, photos: list[UploadFile]) -> dict[str, str]:
    """
    Saves uploaded photos into uploads/telegram_sessions/{session_id}/photos/
    Returns a mapping: basename -> public url
    """
    if not photos:
        return {}
    session_photos_dir = UPLOADS_DIR / "telegram_sessions" / session_id / "photos"
    session_photos_dir.mkdir(parents=True, exist_ok=True)

    url_map = {}
    for p in photos:
        if not p.filename:
            continue
        base_name = Path(p.filename).name
        dest_path = session_photos_dir / base_name
        try:
            with open(dest_path, "wb") as out_f:
                shutil.copyfileobj(p.file, out_f)
            url_map[base_name] = f"/uploads/telegram_sessions/{session_id}/photos/{base_name}"
        except Exception as exc:
            logger.warning(f"Could not stage photo {base_name}: {exc}")
    return url_map


@app.post("/api/telegram/convert")
async def convert_telegram_chat(
    file: UploadFile = File(...),
    photos: list[UploadFile] = File(default=[]),
    include_service: bool = Form(True),
) -> JSONResponse:
    """
    Parse uploaded Telegram messages.html file, stage any attached photos,
    log the run to telegram_parser_log.jsonl, and return structured JSON.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    try:
        session_id = uuid.uuid4().hex[:12]
        content_bytes = await file.read()
        html_content = content_bytes.decode("utf-8", errors="replace")

        # Stage any photos uploaded alongside messages.html
        photo_url_map = _stage_telegram_photos(session_id, photos)

        html_parser = TelegramHTMLParser(include_service_messages=include_service)
        chat = html_parser.parse_html(html_content)
        chat.export_source = file.filename

        # Enrich messages with photo urls if available
        enriched_messages = []
        for m in chat.messages:
            m_dict = m.model_dump()
            if m.media and m.media.file_path:
                media_base = Path(m.media.file_path).name
                thumb_base = Path(m.media.thumbnail_path).name if m.media.thumbnail_path else None
                if media_base in photo_url_map:
                    m_dict["media"]["url"] = photo_url_map[media_base]
                if thumb_base and thumb_base in photo_url_map:
                    m_dict["media"]["thumb_url"] = photo_url_map[thumb_base]
                elif media_base in photo_url_map:
                    m_dict["media"]["thumb_url"] = photo_url_map[media_base]
            enriched_messages.append(m_dict)

        # Log to telegram_parser_log.jsonl
        log_entry = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "chat_title": chat.chat_title,
            "export_source": file.filename,
            "total_messages": chat.total_messages,
            "media_count": len([m for m in chat.messages if m.media]),
            "reply_count": len([m for m in chat.messages if m.reply_to_message_id]),
            "reaction_count": sum(m.reaction_count for m in chat.messages),
            "uploaded_photos_count": len(photo_url_map),
            "messages": enriched_messages,
        }

        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(TELEGRAM_LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.warning(f"Could not write to telegram_parser_log.jsonl: {log_err}")

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "chat_title": chat.chat_title,
            "export_source": chat.export_source,
            "total_messages": chat.total_messages,
            "uploaded_photos_count": len(photo_url_map),
            "messages": enriched_messages,
        })
    except Exception as exc:
        logger.error(f"Error parsing Telegram HTML: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )


@app.get("/api/telegram/history")
async def get_telegram_history(limit: int = 30) -> list[dict[str, Any]]:
    """
    Read and return past Telegram conversion runs from logs/telegram_parser_log.jsonl.
    """
    if not TELEGRAM_LOG_FILE.exists():
        return []
    records = []
    try:
        with open(TELEGRAM_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        logger.error(f"Failed to read telegram history logs: {exc}")
        return []

    records.reverse()
    return records[:limit]


@app.post("/api/telegram/attach-photos")
async def attach_telegram_photos(
    session_id: str = Form(...),
    photos: list[UploadFile] = File(...),
) -> JSONResponse:
    """
    Attach photos to an already converted Telegram session and update stored URLs.
    """
    if not photos:
        raise HTTPException(status_code=400, detail="No photos provided.")

    photo_url_map = _stage_telegram_photos(session_id, photos)

    # Update log entry if it exists
    updated_messages = []
    if TELEGRAM_LOG_FILE.exists():
        try:
            records = []
            with open(TELEGRAM_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))

            for rec in records:
                if rec.get("session_id") == session_id:
                    for m in rec.get("messages", []):
                        if m.get("media") and m["media"].get("file_path"):
                            media_base = Path(m["media"]["file_path"]).name
                            thumb_base = Path(m["media"]["thumbnail_path"]).name if m["media"].get("thumbnail_path") else None
                            if media_base in photo_url_map:
                                m["media"]["url"] = photo_url_map[media_base]
                            if thumb_base and thumb_base in photo_url_map:
                                m["media"]["thumb_url"] = photo_url_map[thumb_base]
                            elif media_base in photo_url_map:
                                m["media"]["thumb_url"] = photo_url_map[media_base]
                    rec["uploaded_photos_count"] = rec.get("uploaded_photos_count", 0) + len(photo_url_map)
                    updated_messages = rec.get("messages", [])

            with open(TELEGRAM_LOG_FILE, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning(f"Failed to update telegram log for attached photos: {exc}")

    return JSONResponse({
        "status": "success",
        "session_id": session_id,
        "attached_count": len(photo_url_map),
        "url_map": photo_url_map,
        "messages": updated_messages,
    })


# =============================================================================
# Database Export to JSON Endpoints
# =============================================================================
DATABASE_LOG_FILE = DEFAULT_LOG_DIR / "database_parser_log.jsonl"


@app.post("/api/database/convert")
async def convert_database_export(
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Parse uploaded database export (.sql, .db, .sqlite, .csv, .tsv, .xlsx)
    and return structured JSON with table names, column schema, and rows.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    try:
        content_bytes = await file.read()
        db_parser = DatabaseParser()
        result = db_parser.parse_bytes(content_bytes, file.filename)

        session_id = uuid.uuid4().hex[:12]
        result_dict = result.model_dump()
        result_dict["session_id"] = session_id

        # Log to database_parser_log.jsonl
        log_entry = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "database_name": result.database_name,
            "export_source": result.export_source,
            "format": result.format,
            "total_tables": result.total_tables,
            "total_rows": result.total_rows,
            "tables_summary": [
                {"table_name": t.table_name, "row_count": t.row_count, "columns_count": len(t.columns)}
                for t in result.tables.values()
            ],
            "data": result_dict,
        }

        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATABASE_LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.warning(f"Could not write to database_parser_log.jsonl: {log_err}")

        return JSONResponse(result_dict)
    except Exception as exc:
        logger.error(f"Error parsing database export: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )


@app.get("/api/database/history")
async def get_database_history(limit: int = 30) -> list[dict[str, Any]]:
    """
    Read and return past database conversion runs from logs/database_parser_log.jsonl.
    """
    if not DATABASE_LOG_FILE.exists():
        return []
    records = []
    try:
        with open(DATABASE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        logger.error(f"Failed to read database history logs: {exc}")
        return []

    records.reverse()
    return records[:limit]


# =============================================================================
# YouTube Channel Data to JSON Endpoints
# =============================================================================
YOUTUBE_LOG_FILE = DEFAULT_LOG_DIR / "youtube_parser_log.jsonl"
SAMPLE_YOUTUBE_JSON = BASE_DIR.parent / "sample_youtube" / "sample_channel.json"


@app.post("/api/youtube/fetch")
async def fetch_youtube_channel(
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> JSONResponse:
    """
    Extract YouTube channel data from a live channel handle/URL or uploaded HTML/JSON file.
    """
    yt_parser = YouTubeChannelParser()
    session_id = uuid.uuid4().hex[:12]

    try:
        if file and file.filename:
            content_bytes = await file.read()
            text_content = content_bytes.decode("utf-8", errors="replace")
            result = yt_parser.parse_html(text_content)
            source_label = file.filename
        elif query and query.strip():
            result = yt_parser.fetch_and_parse(query.strip())
            source_label = query.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail="Either a YouTube channel handle/URL or an uploaded file is required.",
            )

        result_dict = result.model_dump()
        result_dict["session_id"] = session_id

        # Log to youtube_parser_log.jsonl
        log_entry = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "channel_name": result.channel_info.channel_name,
            "handle": result.channel_info.handle,
            "subscriber_count_text": result.channel_info.subscriber_count_text,
            "total_videos": result.total_videos,
            "source": source_label,
            "data": result_dict,
        }

        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(YOUTUBE_LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.warning(f"Could not write to youtube_parser_log.jsonl: {log_err}")

        return JSONResponse(result_dict)

    except ValueError as val_err:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(val_err)})
    except ConnectionError as conn_err:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Network error reaching YouTube: {conn_err}"},
        )
    except Exception as exc:
        logger.error(f"Error extracting YouTube channel: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )


@app.post("/api/youtube/sample")
async def get_youtube_sample() -> JSONResponse:
    """
    Returns the bundled sample YouTube channel data for immediate offline testing.
    """
    if not SAMPLE_YOUTUBE_JSON.exists():
        raise HTTPException(status_code=404, detail="sample_channel.json not found.")

    try:
        with open(SAMPLE_YOUTUBE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["session_id"] = "sample-" + uuid.uuid4().hex[:8]
        return JSONResponse(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/youtube/history")
async def get_youtube_history(limit: int = 30) -> list[dict[str, Any]]:
    """
    Read and return past YouTube channel conversion runs from logs/youtube_parser_log.jsonl.
    """
    if not YOUTUBE_LOG_FILE.exists():
        return []
    records = []
    try:
        with open(YOUTUBE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        logger.error(f"Failed to read YouTube history logs: {exc}")
        return []

    records.reverse()
    return records[:limit]





