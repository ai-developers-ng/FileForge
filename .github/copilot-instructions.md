# OCR Engine - AI Agent Instructions

## Project Overview
This is a Python Flask web application for extracting text from PDFs and images using Apache Tika (for document parsing) and OCR engines (Tesseract/PaddleOCR). The system provides **three distinct processing modes** with explicit workflows for different use cases.

## Architecture Principles

### Service Boundaries
- **Flask App**: Handles HTTP routing, file uploads, job orchestration
- **Tika Server**: External Java service (`tika-server.jar`) called over HTTP - isolates JVM from Python
- **OCR Backends**: Pluggable engines (Tesseract first, PaddleOCR optional) behind a common interface
- **Task Queue**: RQ or Celery for long-running jobs (to be implemented)

### Processing Modes

The system offers three explicit modes (NO automatic fallback logic):

#### Mode 1: Text Extraction Only (`mode="text"`)
- **Use case**: Documents with embedded text layers
- **Workflow**: Tika extraction only → no OCR, no PDF generation
- **Output**: JSON + TXT files only
- **PDF generation**: Disabled

#### Mode 2: OCR Only (`mode="ocr"`)
- **Use case**: Create searchable PDFs without extracting text separately
- **Workflow**: Render to images → OCR → Create PDF with images + OCR text layer
- **Output**: JSON + PDF with embedded OCR text (no separate .txt file with content)
- **PDF generation**: Always uses original images/pages to preserve document appearance
- **Text extraction**: NOT performed (final_text remains empty)

#### Mode 3: OCR + Text Extraction (`mode="both"`)
- **Use case**: Extract both searchable PDF and plain text from scanned documents
- **Workflow**: Render to images → OCR → Create PDF with images + OCR text layer → Extract text
- **Output**: JSON + TXT + PDF (all three)
- **PDF generation**: Uses original images/pages with OCR overlay
- **Text extraction**: Performed from OCR results (populates final_text)

### Processing Pipeline

The core workflow follows this sequence:

1. **Validate** file type (PDF/PNG/JPG/TIFF/BMP) and size (max 25MB)
2. **Mode selection** determines processing path (no automatic decision):
   - `text`: Tika extraction only
   - `ocr`: Always render to images → OCR → PDF with images
   - `both`: Same as OCR + also extract text for .txt file
3. **Render PDFs**: For OCR modes, ALWAYS use Poppler (`pdftoppm`/`pdf2image`) to convert PDF pages → images
4. **OCR Processing**: Run selected engine on all images
5. **Output Generation**: Create files based on mode (PDF always preserves original appearance)

### Key Design Decisions

- **No threshold-based logic**: Mode selection is explicit, no automatic fallback
- **PDF preservation**: OCR modes ALWAYS create PDFs from original images (never plain text PDFs)
- **Text extraction separation**: OCR and text extraction are independent operations
- **Image handling**: Single images are treated like single-page PDFs in OCR workflow

### Extensibility Pattern
Use a **plugin registry** for extractors and OCR engines:
- Each backend implements a common interface (e.g., `extract(file_path) -> dict`)
- Config flags (`config.py`) enable/disable specific backends
- Adapters wrap external tools to standardize their outputs

## API Conventions

### Endpoints (Planned)
- `POST /extract`: Upload file → returns `job_id` (async) or direct result (small files)
- `GET /jobs/<id>`: Check job status (`pending`, `processing`, `completed`, `failed`)
- `GET /jobs/<id>/result`: Retrieve extracted text + metadata

### Response Format
Return JSON with:
```json
{
  "text": "...",
  "metadata": {"pages": 5, "file_type": "pdf"},
  "ocr_applied": true,
  "per_page": [{"page": 1, "text": "...", "confidence": 0.95}]
}
```

## Development Workflow

### Running Services
1. Start Tika Server: `java -jar tika-server.jar` (port 9998 by default)
2. Start Flask: `python app.py` or `flask run` (port 5001)
3. For queues: Start Redis + worker (RQ: `rq worker`, Celery: `celery -A app worker`)

### Testing Strategy
- **Unit tests**: Routing logic, pipeline orchestration (mock external services)
- **Fixtures**: Store test files in `tests/fixtures/` - include known PDFs (text + scanned) and images
- **Smoke tests**: Verify Tika server connectivity before running extraction tests

### PDF Output
- **With images**: Creates PDF with original page images + text overlay
- **Text-only**: Generates simple text PDF when no images available
- **Image uploads in OCR mode**: Properly adds single image to pages array for consistent PDF generation
- **Validation**: Checks PDF file size and logs warnings for suspiciously small files

## File Organization (Future)
```
app.py                  # Flask app entry point
config.py               # Feature flags, Tika URL, max file size
ocr_engine/
  __init__.py
  config.py             # Settings class with environment variables
  jobs.py               # Job storage and management
  storage.py            # File storage utilities
  tika_client.py        # HTTP client for Tika server
  ocr.py                # OCR interface and engine implementations
  pipeline.py           # Orchestrates Tika + OCR + output
  pdf_output.py         # PDF generation for results
tests/
  fixtures/             # Test PDFs and images
```

## Key Dependencies
- **Flask**: Web framework
- **requests**: HTTP client for Tika server
- **pytesseract**: Python wrapper for Tesseract
- **pdf2image**: Renders PDF pages (requires Poppler system install)
- **Pillow**: Image manipulation
- **paddlepaddle>=3.0.0**: Required core dependency for PaddleOCR
- **paddleocr>=3.0.0**: Advanced OCR engine with better accuracy
- **RQ** or **Celery**: Task queue for background jobs (to be implemented)

## OCR Engine Implementation

### PaddleOCR Specifics (v3.0+)
- **Correct initialization**: Use `PaddleOCR(use_textline_orientation=True, lang="en")` 
  - ⚠️ `use_angle_cls` is deprecated → use `use_textline_orientation` instead
  - ⚠️ `show_log` parameter was removed in v3.0+
  - ⚠️ `cls` parameter for `.ocr()` is not supported → just call `ocr.ocr(image)`
- **Result structure (v3.0+)**: Returns `[OCRResult]` where OCRResult is a dict-like object:
  - Access results as `page['rec_texts']` (list of strings) and `page['rec_scores']` (list of confidences)
  - **Do NOT use** `.rec_texts` attribute access - use dict-style `['rec_texts']` instead
- **Always check for None**: Results can be empty - check `if results and len(results) > 0` before accessing
- **Dependencies**: Requires **both** `paddlepaddle>=3.0.0` and `paddleocr>=3.0.0` packages

### Tesseract Specifics
- Returns plain text via `image_to_string()`
- Use `image_to_data()` to get confidence scores per word
- Handle exceptions when getting confidence data (may fail on some images)

## Deployment Notes
- Use **Docker Compose** with services: `flask-app`, `tika-server`, `redis` (optional)
- Set **resource limits**: Tika JVM heap (-Xmx2g), OCR memory constraints
- Mount volumes for file uploads (`/uploads`) and results (`/results`)
- Environment variables: `TIKA_SERVER_URL`, `MAX_FILE_SIZE_MB`, `ENABLE_PADDLE_OCR`

## Code Style Conventions
- Follow **PEP 8** for Python code
- Use **type hints** for function signatures (e.g., `def extract(file_path: str) -> dict:`)
- Isolate external tool calls behind **adapters** - never call `subprocess` or HTTP directly in routes
- Log pipeline steps with structured logging (JSON format for production)

## When Adding New Features
1. Check if feature needs a new backend → implement interface + adapter
2. Add config flag in `config.py` to enable/disable feature
3. Update API response format in this file if output schema changes
4. Add fixture files and tests before merging
