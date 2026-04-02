<p align="center">
  <h1 align="center">🩺 MedSOAP AI</h1>
  <p align="center">
    <strong>AI-Powered Clinical Dictation &amp; Auto-Charting Engine</strong>
  </p>
  <p align="center">
    Record a patient encounter → Transcribe with Whisper → Categorize into SOAP with Llama-3 → Export a professional PDF
  </p>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [File Documentation](#file-documentation)
  - [Root Configuration Files](#root-configuration-files)
  - [Application Entry Point](#application-entry-point)
  - [Database Layer](#database-layer)
  - [Routes](#routes)
  - [Services (Business Logic)](#services-business-logic)
  - [Frontend](#frontend)
- [Getting Started](#getting-started)
- [API Endpoints](#api-endpoints)
- [Tech Stack](#tech-stack)

---

## Overview

**MedSOAP AI** is a full-stack clinical dictation application that allows healthcare professionals to:

1. **Speak** a patient encounter into a microphone via the browser.
2. **Transcribe** the audio to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper, optimised for CPU).
3. **Categorize** the transcript into structured **S.O.A.P.** notes (Subjective, Objective, Assessment, Plan) using the **Llama-3.3 70B** model through [Groq](https://groq.com).
4. **Review & Edit** the generated note directly in the browser with drag-and-drop and inline editing.
5. **Export** a professional PDF report for the patient's medical record.

All encounters are persisted to a database (SQLite by default, PostgreSQL optional) for historical access.

---

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   Browser    │──────▶│   FastAPI App     │──────▶│  Groq Cloud API  │
│  (HTML/JS)   │◀──────│  (main.py)       │◀──────│  (Llama-3.3 70B) │
└──────────────┘       └────────┬─────────┘       └──────────────────┘
                                │
                     ┌──────────┼──────────┐
                     ▼          ▼          ▼
              ┌──────────┐ ┌────────┐ ┌──────────┐
              │ Whisper   │ │ SQLite │ │ ReportLab│
              │ (STT)    │ │  / PG  │ │  (PDF)   │
              └──────────┘ └────────┘ └──────────┘
```

---

## Project Structure

```
app/
├── .dockerignore          # Files excluded from Docker build context
├── .env                   # Environment variables (SECRET — never commit)
├── .env.example           # Template showing required env vars
├── .gitignore             # Git ignore rules
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Single-command container orchestration
├── requirements.txt       # Python dependency list (pip)
├── README.md              # This file
│
├── main.py                # ★ Application entry point — FastAPI bootstrap
├── database.py            # SQLAlchemy engine, models & session factory
├── pdf_generator.py       # ReportLab-based SOAP PDF renderer
│
├── routes/                # HTTP endpoint definitions
│   ├── __init__.py        # Package marker
│   └── api.py             # All REST + HTML endpoints
│
├── services/              # Core business-logic modules
│   ├── __init__.py        # Package marker
│   ├── ai_engine.py       # Groq / Llama-3 SOAP classification engine
│   ├── record_and_transcribe.py  # Local mic recording + Whisper STT (CLI tool)
│   └── soap_formatter.py  # Offline ML-based SOAP classifier (sklearn)
│
├── static/                # Browser-served static assets
│   ├── style.css          # Clinical EHR-themed stylesheet
│   └── script.js          # Frontend recording, rendering & drag-drop logic
│
└── templates/             # Jinja2 HTML templates
    └── index.html         # Single-page clinical dictation UI
```

---

## File Documentation

### Root Configuration Files

| File | Purpose |
|------|---------|
| **`.env`** | Stores secret environment variables (`GROQ_API_KEY`, optional `DATABASE_URL`). **Must never be committed to version control.** |
| **`.env.example`** | Sanitised template of `.env` — shows which variables are required and their expected format. Copy to `.env` and fill in real values. |
| **`.gitignore`** | Defines patterns for files Git should ignore: Python bytecode, virtual environments, `.env`, SQLite databases, IDE configs, OS files, and temporary audio recordings. |
| **`.dockerignore`** | Prevents `venv/`, `__pycache__/`, `.env`, `clinical_notes.db`, compiled `.pyc` files, and `.git` from being sent to the Docker daemon during builds — keeps images lean. |
| **`Dockerfile`** | Multi-step container build: uses `python:3.11-slim`, installs `ffmpeg` (required by Whisper for audio decoding) and `build-essential`, installs pip packages, copies source, exposes port `8000`, and runs uvicorn. |
| **`docker-compose.yml`** | Orchestration config that builds the Dockerfile, maps port `8000`, injects `.env`, mounts the local `clinical_notes.db` for persistence, and sets the container to auto-restart. |
| **`requirements.txt`** | Pinned-free dependency list: `fastapi`, `uvicorn`, `python-multipart`, `sqlalchemy`, `psycopg2-binary`, `faster-whisper`, `groq`, `jinja2`, `pdfkit`, `python-dotenv`, `reportlab`. |

---

### Application Entry Point

#### `main.py`

The central FastAPI application bootstrap. Responsibilities:

- **Loads environment variables** from `.env` via `python-dotenv`.
- **Creates the FastAPI app** instance with title *"Clinical SOAP AI API"* and version `3.0`.
- **Mounts static files** from the `static/` directory at the `/static` URL path.
- **Configures CORS middleware** (fully open `*` origins for development).
- **Includes the API router** defined in `routes/api.py`.
- **Defines the lifespan** context manager that logs startup/shutdown events.
- **Starts uvicorn** when executed directly (`__main__`), listening on `127.0.0.1:8000` with hot-reload.

---

### Database Layer

#### `database.py`

Database configuration and ORM model definitions using SQLAlchemy.

| Component | Description |
|-----------|-------------|
| **Engine creation** | Reads `DATABASE_URL` from the environment. Defaults to a local `sqlite:///./clinical_notes.db` if unset. Configures `check_same_thread=False` for SQLite. |
| **`SessionLocal`** | Scoped session factory bound to the engine (`autocommit=False`, `autoflush=False`). |
| **`SoapNoteRecord` model** | Table `soap_notes` — stores each encounter with columns: `id` (PK), `raw_transcript` (Text), `structured_data` (JSON), `created_at` (DateTime, auto-set to UTC now). |
| **`FeedbackRecord` model** | Table `feedback_logs` — stores doctor corrections with columns: `id` (PK), `note_id` (Integer), `sentence` (Text), `correct_label` (String, S/O/A/P), `created_at`. |
| **`get_db()` generator** | Dependency-injection helper that yields a database session and ensures it is closed after use. |
| **Auto-migration** | `Base.metadata.create_all()` is called at import time, creating tables if they don't exist. |

---

### Routes

#### `routes/__init__.py`

Package marker file. Identifies the `routes/` directory as a Python package.

#### `routes/api.py`

All HTTP endpoints in a single `APIRouter`. This is the main API surface of the application.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | `GET` | Serves the frontend SPA (`index.html`) via Jinja2. |
| `/generate-soap` | `POST` | Accepts a JSON body with `text` (transcript string) and optional `return_pdf` flag. Sends the text through `ai_engine.process_text_to_soap()`, saves to DB, and returns structured SOAP JSON or a streamed PDF. |
| `/upload-audio` | `POST` | Accepts a multipart audio file (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.webm`). Saves to a temp file, transcribes with the locally-loaded Whisper `base.en` model, and pipes the transcript to the SOAP engine. Cleans up the temp file in a `finally` block. |
| `/notes` | `GET` | Returns the `limit` (default 10) most recent SOAP notes from the database, ordered by `created_at DESC`. |
| `/notes/{note_id}/pdf` | `GET` | Looks up a saved note by ID and streams back a professionally formatted PDF via `pdf_generator`. |
| `/notes/{note_id}` | `PUT` | Accepts an updated `structured_data` JSON body from the doctor's manual edits and overwrites the stored note. |
| `/submit-feedback` | `POST` | Accepts a correction (`note_id`, `sentence`, `correct_label`). Validates the label is S/O/A/P and persists to the `feedback_logs` table for future model improvement. |

**Key internals:**
- Loads the Whisper model (`base.en`, CPU, int8) once at module import for fast inference.
- Uses Pydantic models (`TranscriptRequest`, `FeedbackRequest`, `UpdateNoteRequest`) for request validation.
- Resolves the `templates/` directory via `os.path` relative to the project root.

---

### Services (Business Logic)

#### `services/__init__.py`

Package marker file. Identifies the `services/` directory as a Python package.

#### `services/ai_engine.py`

The core AI classification engine. Connects to **Groq Cloud** to run **Llama-3.3 70B Versatile**.

| Function | Signature | Description |
|----------|-----------|-------------|
| `process_text_to_soap` | `(raw_text: str, db: Session) → dict` | Sends the transcript to Llama-3 with a strict clinical system prompt. Forces JSON output via `response_format`. Parses the response into Subjective / Objective / Assessment / Plan sections (each item has `text` and `confidence`). Saves the result to the `soap_notes` table and returns a dict with `status`, `note_id`, `transcript`, and `data`. Rolls back the DB on any failure. |

**System prompt rules enforced:**
- Fixes common speech-to-text misspellings (e.g., *"lysin proled"* → *"lisinopril"*).
- Requires patient demographics, vitals, exact dosages, and follow-up timelines.
- Temperature set to `0.1` for strict factual output.

---

#### `services/record_and_transcribe.py`

A **standalone CLI tool** for recording audio from the local microphone and transcribing it with Whisper. Not used by the web API — designed for local testing.

| Function | Description |
|----------|-------------|
| `audio_callback(indata, frames, time, status)` | Sounddevice callback that queues each audio chunk as it arrives. |
| `record_until_enter(filename, samplerate)` | Opens the microphone stream and records until the user presses Enter. Concatenates chunks, saves as a `.wav` file, and returns the file path. |
| `transcribe_audio(audio_file_path, model)` | Runs `faster-whisper` transcription on the saved audio file with `beam_size=5`. Returns the full transcript string. |
| `save_transcript_to_file(transcript, folder_path)` | Saves the transcript as a timestamped `.txt` file under `data/raw_dictations/` for test-case archival. |
| `__main__` block | Loads Whisper, records audio, transcribes, prints the result, and saves to file. |

---

#### `services/soap_formatter.py`

An **offline, ML-based** SOAP classifier using a pre-trained scikit-learn model.

| Class | Method | Description |
|-------|--------|-------------|
| `SOAPFormatter` | `__init__()` | Loads a pickled classifier from `app/ml/soap_classifier.pkl` via joblib. |
| | `format(transcript) → str` | Splits the transcript into sentences, classifies each into S/O/A/P using the loaded model, and returns a formatted text block. |
| | `_split_sentences(text)` | Regex-based sentence splitter on `.?!` delimiters. |
| | `_build_output(sections)` | Renders the classified sections as a labelled bullet-point string. |

> **Note:** This module requires a trained `soap_classifier.pkl` model file that is not included in the repository.

---

#### `pdf_generator.py`

Generates a professional medical PDF report from SOAP data using **ReportLab**.

| Function | Signature | Description |
|----------|-----------|-------------|
| `create_soap_pdf` | `(soap_data: dict, transcript: str) → BytesIO` | Builds a letter-sized PDF with custom paragraph styles. Includes a branded header (*"MedSOAP AI — Clinical Encounter Note"*), date of service, all four SOAP sections as bulleted lists, and the raw audio transcript at the bottom for legal/auditing purposes. Returns an in-memory buffer ready for streaming. |

**PDF styling:**
- Title: centered, dark slate colour (`#1e293b`).
- Section headings: blue (`#2563eb`).
- Body text: 11pt with 16pt leading for readability.
- Horizontal rules between sections.
- Transcript rendered in muted grey italic for visual separation.

---

### Frontend

#### `templates/index.html`

The single-page application served at `/`. Built with semantic HTML5 and Jinja2 templating.

**Key UI sections:**
- **Header** — App title, system-online indicator, and *"Past Cases"* sidebar toggle button.
- **Dictation controls** — Large *"Start Dictation"* (red) and *"Stop & Process"* (grey) buttons.
- **Status bar** — Real-time feedback messages during recording, processing, and result display.
- **SOAP Grid** — Four colour-coded sections (Subjective, Objective, Assessment, Plan) plus a conditional *"Needs Review"* section. Each item is inline-editable and draggable between sections.
- **Sidebar** — Slide-in panel listing archived cases; clicking a card loads that note into the grid.
- **Save & Export** — Saves doctor edits via PUT, then triggers a PDF download.

Includes embedded `<style>` for sidebar-specific CSS (positioning, transitions, history cards).

---

#### `static/style.css`

The complete clinical EHR-themed stylesheet.

| Section | Description |
|---------|-------------|
| **CSS Custom Properties** | Design tokens: `--primary-blue`, `--dark-blue`, `--danger-red`, `--neutral-gray`, `--success-green`, plus surface, text, and border colours. |
| **Layout** | Centered `max-width: 1000px` container with white surface and soft box-shadow. |
| **Header** | Dark blue background with a 4px blue accent border, green pulsing status dot. |
| **Buttons** | Oversized *"massive"* dictation buttons with press/hover/disabled states. Green download button. |
| **SOAP Grid** | Vertical flex layout; each box has a coloured left border (sky blue for S, purple for O, amber for A, emerald for P, red for review). |
| **Drag & Drop** | Grab cursor on items, hover highlight, active grab state, dashed-border drop target feedback (`drag-active` class). |
| **Badges** | 30×30px colour-coded section labels. |
| **Animations** | `recording-pulse` keyframe: pulsing red glow on the record button while active. |

---

#### `static/script.js`

All client-side logic in vanilla JavaScript (no frameworks).

| Section | Functionality |
|---------|---------------|
| **1. Core UI** | `renderSoapNoteToGrid(noteId, soapData)` — populates the four SOAP `<ul>` lists with editable, draggable `<li>` items. Handles empty sections with placeholder text. |
| **2. Drag & Drop Engine** | `setupDragAndDrop()` — attaches `dragover`, `dragenter`, `dragleave`, `drop` listeners to each `.soap-box`. `createEditableItem(text)` — creates a `<li>` with `draggable=true`, `contenteditable=true`, and change-tracking events. |
| **3. Recording & API** | Uses `navigator.mediaDevices.getUserMedia` to capture audio, wraps in a `MediaRecorder`, sends the resulting `.webm` blob to `/upload-audio` via `FormData`, and renders the AI response. |
| **4. Save & Export** | Scrapes the current DOM state of all SOAP lists, PUTs the edited data to `/notes/{id}`, and triggers a PDF download via redirect. |
| **5. Sidebar & Past Cases** | Fetches `/notes?limit=15`, renders history cards with date and transcript preview, and loads a past note into the grid on click. |

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **ffmpeg** installed and on `PATH` (required by faster-whisper)
- A **Groq API key** ([console.groq.com](https://console.groq.com))

### Local Development

```bash
# 1. Clone and navigate
cd app/

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate       # Linux / macOS
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your real GROQ_API_KEY

# 5. Run the development server
python main.py
# or
uvicorn main:app --reload --port 8000
```

Open **http://127.0.0.1:8000** in your browser.

### Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# The app will be available at http://localhost:8000
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the frontend UI |
| `POST` | `/generate-soap` | Convert a text transcript to SOAP JSON/PDF |
| `POST` | `/upload-audio` | Upload an audio file for transcription + SOAP |
| `GET` | `/notes?limit=N` | List recent saved notes |
| `GET` | `/notes/{id}/pdf` | Download a past note as PDF |
| `PUT` | `/notes/{id}` | Update a note with manual edits |
| `POST` | `/submit-feedback` | Submit a label correction for AI improvement |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend Framework** | FastAPI + Uvicorn |
| **Speech-to-Text** | faster-whisper (base.en, CPU, int8) |
| **AI Classification** | Groq Cloud — Llama-3.3 70B Versatile |
| **Database ORM** | SQLAlchemy (SQLite / PostgreSQL) |
| **PDF Generation** | ReportLab |
| **Frontend** | Vanilla HTML / CSS / JavaScript |
| **Templating** | Jinja2 |
| **Containerisation** | Docker + Docker Compose |

---

<p align="center">
  <sub>Built with ❤️ for clinical efficiency.</sub>
</p>
