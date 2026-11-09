# AI Services Hub: OCR, Telegram, Database & YouTube Converter

A modular multi-service platform featuring:
1. **Gemini Myanmar-English OCR**: Component-based Myanmar (Burmese) and English Optical Character Recognition powered by Google Gemini (`gemini-3.5-flash-lite`).
2. **Telegram HTML Chat Parser**: Complete parser for Telegram Desktop export files (`messages.html`), converting them into clean, structured JSON with full preservation of replies, media paths, message types, and emoji reactions with user metrics and reaction counts.
3. **Database to JSON Converter**: Universal parser for database exports (`.sql` dumps, `.db`/`.sqlite` SQLite databases, `.csv`/`.tsv` tables, and multi-sheet `.xlsx` Excel workbooks) converting schemas and records into structured JSON.
4. **YouTube Channel Data to JSON**: Ingests public YouTube channel URLs, handles (`@handle`), or exported HTML/JSON, extracting complete channel metadata (banner, avatar, verified badge, subscribers) and video catalog (durations, view counts, thumbnails, titles) into structured JSON.

This project features a strictly decoupled architecture with **100% untouched backend packages** and a **modern Single-Page Web Frontend (SPA)** featuring a top-level service switcher allowing effortless switching between services within one web app.

---

## Folder Architecture

The project maintains a crystal-clear separation between Frontend and Backend services:

```
Gemini_ocr/
├── src/                          # === BACKENDS (100% Core Logic - Untouched) ===
│   ├── gemini_ocr/               # Service 1: Myanmar-English OCR
│   │   ├── config.py             # Configs (model, batch size, default prompt)
│   │   ├── models.py             # GeminiRespond, OCRResultItem, BatchOCRResult
│   │   ├── system.py             # OCRSystem (ORCSystem) orchestrator
│   │   └── components/
│   │       ├── base_gemini.py    # GeminiComponent ABC, Mock & Real clients
│   │       ├── file_import.py    # FileImportComponent (file validation)
│   │       └── mmen_ocr.py       # GeminiMMENOCRComponent (batching & retries)
│   │
│   ├── telegram_parser/          # Service 2: Telegram HTML Export Parser
│   │   ├── __init__.py           # Public exports (TelegramHTMLParser, etc.)
│   │   ├── parser.py             # BeautifulSoup extractor with joined-sender tracking
│   │   ├── converter.py          # TelegramChatConverter (HTML -> JSON writer)
│   │   └── models.py             # Pydantic models (TelegramChat, ReactionItem, etc.)
│   │
│   ├── database_parser/          # Service 3: Database Export to JSON Converter
│   │   ├── __init__.py           # Public exports (DatabaseParser, DatabaseConverter)
│   │   ├── parser.py             # Multi-format detection and unified parser
│   │   ├── models.py             # Pydantic models (DatabaseExportResult, TableData, ColumnInfo)
│   │   └── parsers/
│   │       ├── sqlite_parser.py  # SQLite binary reader (.db, .sqlite)
│   │       ├── sql_dump_parser.py# SQL dump interpreter (.sql)
│   │       └── tabular_parser.py # Tabular and Excel parser (.csv, .tsv, .xlsx)
│   │
│   └── youtube_parser/           # Service 4: YouTube Channel Data to JSON
│       ├── __init__.py           # Public exports (YouTubeChannelParser, YouTubeChannelConverter)
│       ├── parser.py             # High-level parser & converter orchestrator
│       ├── models.py             # Pydantic models (YouTubeChannelExportResult, YouTubeVideo, YouTubeChannelInfo)
│       └── extractors/
│           ├── html_extractor.py # Embedded ytInitialData and DOM extractor
│           └── network_fetcher.py# Public channel page fetcher with header normalization
│
├── frontend/                     # === FRONTEND & MIDDLEWARE ===
│   ├── app.py                    # FastAPI middleware bridge (OCR, Telegram, DB, and YouTube routes)
│   ├── static/                   # Unified Single-Page Application assets
│   │   ├── index.html            # Multi-service SPA with 4-service switcher
│   │   ├── app.js                # Reactive UI, switcher tabs, drag & drop, tables, video cards
│   │   └── style.css             # Dark theme styling, Myanmar fonts, chat bubbles, tables, video cards
│   └── uploads/                  # Isolated staging directory for uploaded files
│
├── scripts/                      # === LAUNCHERS & UTILITIES ===
│   ├── start_web.py              # Launches the Unified Web App (http://localhost:8000)
│   ├── run_ocr.py                # CLI OCR runner (mock & live modes)
│   ├── convert_telegram.py       # CLI runner to convert messages.html to JSON
│   ├── convert_database.py       # CLI runner to convert database exports to JSON
│   └── convert_youtube.py        # CLI runner to convert YouTube channel data to JSON
│
├── sample_images/                # OCR test images (text.png, test_2.jpe)
├── telegram_msg_html/            # Sample Telegram Desktop export (messages.html)
├── sample_database/              # Sample database exports (sales.db, sales_database.sql, CSV, XLSX)
├── sample_youtube/               # Sample YouTube channel exports (sample_channel.html, sample_channel.json)
├── logs/                         # JSON Lines audit logs
├── tests/                        # 43 automated unit & integration tests
│   ├── test_file_import.py
│   ├── test_mmen_ocr.py
│   ├── test_models.py
│   ├── test_ocr_system.py
│   ├── test_frontend_api.py      # Tests for all middleware API routes
│   ├── test_telegram_parser.py   # Tests for HTML parsing, reactions & JSON
│   ├── test_database_parser.py   # Tests for SQL dumps, SQLite, CSV & Excel
│   └── test_youtube_parser.py    # Tests for YouTube channel metadata, videos & JSON
│
├── .env.example                  # Environment configuration template
├── .gitignore                    # Protects secrets (.env) and temporary uploads
├── pyproject.toml                # Python package & IDE configurations
├── requirements.txt              # Python dependencies
├── PROJECT_EXPLANATION.md        # Comprehensive architectural guide
└── README.md                     # Quick reference documentation
```

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

### 2. Configure Gemini API Key (Optional for Live Mode)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey):
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```
*(If no API key is set, the system automatically falls back to Mock Mode for offline development).*

---

## Running the Web Frontend

Start the single-page web application:
```powershell
python scripts/start_web.py
```
Open **`http://localhost:8000`** in your browser.

### Web Frontend Features:
- **Service Switcher (Segmented Control)**:
  - Toggle between **Gemini OCR**, **Telegram Parser**, and **Database to JSON** in one seamless SPA.
  - Dynamic header history button adapting to active service tab (`OCR History` / `Telegram History` / `Database History`) with active glow state.
- **Service 1: Gemini OCR (Image to JSON)**:
  - Drag and drop single files, multiple files, or select an entire folder (`webkitdirectory`).
  - Interactive parameter controls: `file_per_batch` slider (range: **1 to 10**) and customizable prompt instructions (`content`).
  - Live Gemini API or offline Mock Simulation mode.
  - Side-by-side cards with image preview and zoom modal.
  - 1-click "Copy Text", "Download .txt", and toggleable formatted Raw JSON view.
  - Interactive History inspecting past OCR jobs from `logs/gemini_ocr_log.jsonl`.
- **Service 2: Telegram HTML Chat Parser (HTML to JSON)**:
  - Drag & drop or select Telegram Desktop `messages.html` or choose the entire export folder.
  - Optional inclusion of Service Messages (date headers, event notifications).
  - Real-time chat metrics: total messages, media items, reply counts, and total reactions.
  - Interactive chat timeline with styled user/peer bubbles, reply quotes, media cards with click-to-zoom modal, and emoji reaction pills showing reaction counts and user lists on hover.
  - Real-time client-side search filtering by sender, message text, or media filename.
  - 1-click "Copy JSON" and "Download messages.json".
  - Persistent history logging in `logs/telegram_parser_log.jsonl` with 1-click "Load in Viewer".
- **Service 3: Database to JSON Converter (Database to JSON)**:
  - Drag & drop or select database export files: SQL dumps (`.sql`), SQLite databases (`.db`, `.sqlite`, `.sqlite3`), CSV/TSV tables, and multi-sheet Excel (`.xlsx`).
  - Database overview banner with format badges, total table count, and total row count.
  - Interactive horizontal table tabs to switch between tables instantly.
  - Responsive data table preview with column names, data type pills, primary key (`PK`) indicators, and zebra striping.
  - Real-time row search filter across all columns.
  - Smart table pagination (25, 50, 100, or All rows per page).
  - 1-click "Copy Table JSON", "Download Table", "Copy Full DB JSON", and "Download Full DB".
  - Persistent history logging in `logs/database_parser_log.jsonl` with 1-click "Load in Viewer".

---

## Running the Backend CLI

Process images directly from the terminal:
```powershell
# Single image (PNG):
python scripts/run_ocr.py --input sample_images/text.png

# Single image (JPE):
python scripts/run_ocr.py --input sample_images/test_2.jpe

# Entire directory:
python scripts/run_ocr.py --input sample_images/ --batch-size 2

# Offline mock simulation:
python scripts/run_ocr.py --mock --input sample_images/
```

Convert Telegram HTML chat exports directly via Python:
```python
from telegram_parser import TelegramChatConverter

converter = TelegramChatConverter(include_service_messages=True)
converter.convert_file("telegram_msg_html/messages.html", "telegram_msg_html/messages.json")
```

Convert Database exports directly via Python:
```python
from database_parser import DatabaseConverter

converter = DatabaseConverter()
converter.convert_file("sample_database/sales_database.sql", "sample_database/sales.json")
```

---

## Running Automated Tests

Run the full pytest suite (all 33 tests):
```powershell
python -m pytest -v
```
