# FileForge

Full-featured Flask application for document text extraction, image conversion, document format conversion, audio/video conversion, and OCR. Powered by Tesseract, ImageMagick, Pandoc, FFmpeg, and optional Apache Tika. Deployable locally or in production on a VPS behind Traefik with automatic HTTPS.

## Features

### OCR & Document Processing
- Upload PDFs and images via a modern web interface
- **Multiple file upload** support with individual progress tracking
- Three distinct processing modes:
  - **Text extraction only**: Extract embedded text (no OCR, no PDF output)
  - **OCRd PDF**: Create searchable PDFs with original document appearance
  - **OCR + Text extraction**: Create searchable PDFs AND extract plain text
- Job queue with status polling and downloadable results
- Download results as TXT, JSON, or PDF

### Image Converter
- **200+ format support** via ImageMagick
- Format conversion between PNG, JPG, WebP, GIF, TIFF, BMP, ICO, PDF, and more
- **RAW camera format support**: NEF, CR2, CR3, ARW, DNG, RAF, ORF, RW2, PEF, SRW
- **Modern formats**: HEIC, HEIF, AVIF, JXL (JPEG XL)
- **Special formats**: SVG, EPS, PSD, XCF, HDR, EXR
- Image optimization with quality control
- Resize by dimensions, percentage, or DPI
- Rotation (90°, 180°, 270°)
- Brightness and contrast adjustment
- Grayscale conversion

### Document Converter
- **Universal document conversion** via Pandoc
- **Input formats**: DOCX, DOC, MD, HTML, RTF, CSV, TSV, JSON, RST, EPUB, ODT, DocBook
- **Output formats**: PDF, DOCX, HTML, TXT, Markdown
- Multiple file upload with individual download links
- Preserves formatting during conversion

### Audio Converter
- **50+ audio/video format support** via FFmpeg
- **Audio formats**: MP3, WAV, FLAC, OGG, AAC, M4A, WMA, AIFF, OPUS, and more
- **Video to audio extraction**: MP4, MKV, AVI, MOV, WebM, and more
- **Output formats**: MP3, WAV, FLAC, AAC, OGG, M4A, OPUS
- **Bitrate control**: 128, 192, 256, 320 kbps for lossy formats
- Multiple file upload with individual download links

### Video Converter
- **30+ video format support** via FFmpeg
- **Input formats**: MKV, MP4, WebM, AVI, WMV, MOV, GIF, MTS, FLV, and more
- **Output formats**: MP4, WebM, AVI, MKV, MOV, GIF, WMV, FLV
- **Quality control**: Low, Medium, High presets
- Multiple file upload with individual download links

## Quick Start with Docker

All dependencies are bundled in the Docker image — no local installs needed.

### Choose a compose file

| File | Use when |
|------|----------|
| `docker-compose.yml` | Local dev / quick test — app on `http://localhost:5001` |
| `docker-compose.full.yml` | Local dev **with** Apache Tika for richer text extraction |
| `docker-compose.traefik.yml` | **VPS / production** — Traefik reverse proxy, automatic HTTPS, Tika included |

---

### Local development

```bash
# 1. Clone the repo
git clone <repository-url> && cd FileForge

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY

# 3a. Start without Tika
docker compose up -d

# 3b. OR start with Apache Tika (enhanced text extraction)
docker compose -f docker-compose.full.yml up -d

# View live logs
docker compose logs -f

# Stop
docker compose down
```

App is available at **http://localhost:5001**.

---

### Production on a VPS (Traefik + HTTPS)

Requirements:
- A domain pointed at your VPS via a DNS **A record**
- Ports **80** and **443** open in your firewall
- Docker and `apache2-utils` installed on the server

```bash
# 1. Install Docker (Debian/Ubuntu)
apt update && apt install -y docker.io docker-compose apache2-utils

# 2. Clone the repo
git clone <repository-url> && cd FileForge

# 3. Configure environment
cp .env.example .env
# Required edits in .env:
#   SECRET_KEY   – generate with: python -c "import secrets; print(secrets.token_hex(32))"
#   DOMAIN       – your domain, e.g. fileforge.example.com
#   ACME_EMAIL   – email for Let's Encrypt expiry warnings
#   TRAEFIK_DASHBOARD_AUTH – generate with: htpasswd -nb admin <password>
#                            then escape every $ → $$ before pasting

# 4. Create the certificate store (must exist and be 600)
touch traefik/acme.json && chmod 600 traefik/acme.json

# 5. Start the full stack (Traefik + FileForge + Tika)
docker compose -f docker-compose.traefik.yml up -d

# View logs
docker compose -f docker-compose.traefik.yml logs -f

# Stop
docker compose -f docker-compose.traefik.yml down
```

After startup:
- App is available at **https://your-domain.com** (HTTP → HTTPS redirect is automatic)
- Traefik dashboard at **https://your-domain.com/dashboard/** (basic-auth protected)
- Port 5001 and 9998 are **never exposed** to the internet — only Traefik talks to the app internally
- TLS certificates are obtained and renewed automatically via Let's Encrypt

---

### Using Docker directly (no compose)

```bash
# Build the image
docker build -t fileforge .

# Run
docker run -d \
  --name fileforge \
  -p 5001:5001 \
  -v fileforge-data:/app/data \
  -e SECRET_KEY=change-me \
  -e MAX_FILE_MB=25 \
  fileforge

# Stop and remove
docker stop fileforge && docker rm fileforge
```

---

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required in production)* | Flask session secret — generate with `secrets.token_hex(32)` |
| `DOMAIN` | — | Public domain name (Traefik deployment only) |
| `ACME_EMAIL` | — | Email for Let's Encrypt notifications (Traefik deployment only) |
| `TRAEFIK_DASHBOARD_AUTH` | — | `htpasswd`-format credentials for the Traefik dashboard |
| `MAX_FILE_MB` | `25` | Maximum upload size in MB |
| `TIKA_SERVER_URL` | `http://localhost:9998` | Apache Tika URL (set automatically in compose) |
| `CLEANUP_TTL_HOURS` | `24` | How long to keep completed job files |
| `CLEANUP_INTERVAL_MINUTES` | `30` | How often the cleanup routine runs |
| `WORKER_COUNT` | `2` | Concurrent job workers |
| `GUNICORN_WORKERS` | `1` | Gunicorn worker processes (keep at 1 with internal queue) |
| `GUNICORN_THREADS` | `8` | Threads per Gunicorn worker |
| `OCR_DPI` | `300` | DPI for PDF→image conversion (higher = better quality, more RAM) |
| `OCR_PAGE_WORKERS` | `2` | Pages OCR'd in parallel within a single job |
| `OCR_BATCH_SIZE` | `10` | PDF pages converted per batch |
| `OCR_CACHE_ENABLED` | `1` | Set to `0` to disable the OCR result cache |
| `OCR_CACHE_MAX_FILE_ENTRIES` | `500` | Max cached Tika file results |
| `OCR_CACHE_MAX_PAGE_ENTRIES` | `10000` | Max cached per-page OCR results |

### Data persistence

All compose files use a named volume to persist:
- Uploaded files — `/app/data/uploads`
- Conversion results — `/app/data/results`
- SQLite job database — `/app/data/jobs.db`
- OCR result cache — `/app/data/ocr_cache.db`

---

## Manual Setup (Without Docker)

### 1. Create virtual environment
```bash
git clone <repository-url> && cd FileForge
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install External Tools

**Tesseract OCR:**
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- Windows: Download from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)

**ImageMagick (required for Image Converter):**
- macOS: `brew install imagemagick`
- Ubuntu/Debian: `sudo apt-get install imagemagick libmagickwand-dev`
- Windows: Download from [ImageMagick website](https://imagemagick.org/script/download.php)

**Pandoc (required for Document Converter):**
- macOS: `brew install pandoc`
- Ubuntu/Debian: `sudo apt-get install pandoc`
- Windows: Download from [Pandoc website](https://pandoc.org/installing.html)

**FFmpeg (required for Audio/Video Converter):**
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH

**Poppler (required for PDF to image conversion):**
- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt-get install poppler-utils`
- Windows: Download from [poppler releases](http://blog.alivate.com.au/poppler-windows/) and add to PATH

**Apache Tika Server (optional, for text extraction mode):**
- Download from [Apache Tika](https://tika.apache.org/download.html)
- Run: `java -jar tika-server.jar --port 9998`

### 3. Start the Application
```bash
cp .env.example .env   # set SECRET_KEY at minimum
python app.py
```
The app will run on `http://localhost:5001`.

---

## Configuration

All configuration is done via environment variables. Copy `.env.example` to `.env` and edit as needed. See the [Environment variables](#environment-variables) table in the Docker section above for the full reference.

## Usage

### OCR Tab
1. Click "OCR" tab (default)
2. Upload one or more files (PDF, PNG, JPG, TIFF, BMP)
3. Select processing mode:
   - **Text extraction only**: Fast extraction of embedded text
   - **OCRd PDF**: Create searchable PDF
   - **OCR + Text extraction**: Both searchable PDF and text file
4. Click "RUN"
5. Download results individually or view combined text

### Image Converter Tab
1. Click "Image" tab
2. Upload one or more images (200+ formats supported)
3. Select output format (PNG, JPG, WebP, GIF, TIFF, BMP, ICO, PDF)
4. Adjust settings:
   - **Quality**: 1-100% for lossy formats (JPG, WebP)
   - **Resize**: Width, height, percentage, or DPI
   - **Rotation**: 90° CW, 180°, or 90° CCW
   - **Brightness/Contrast**: 0-200%
   - **Grayscale**: Convert to black and white
5. Click "CONVERT"
6. Download converted images

### Document Converter Tab
1. Click "Document" tab
2. Upload one or more documents (DOCX, MD, HTML, RTF, EPUB, etc.)
3. Select output format (PDF, DOCX, HTML, TXT, Markdown)
4. Click "CONVERT"
5. Download converted documents

### Audio Converter Tab
1. Click "Audio" tab
2. Upload one or more audio/video files (MP3, WAV, FLAC, MP4, MKV, etc.)
3. Select output format (MP3, WAV, FLAC, AAC, OGG, M4A, OPUS)
4. Select bitrate for lossy formats (128, 192, 256, 320 kbps)
5. Click "CONVERT"
6. Download converted audio files

### Video Converter Tab
1. Click "Video" tab
2. Upload one or more video files (MP4, MKV, WebM, AVI, MOV, etc.)
3. Select output format (MP4, WebM, AVI, MKV, MOV, GIF, WMV, FLV)
4. Select quality (Low, Medium, High)
5. Click "CONVERT"
6. Download converted video files

## Supported Formats

### Image Formats

### Input Formats
| Category | Formats |
|----------|---------|
| Common | PNG, JPG, JPEG, WebP, GIF, BMP, TIFF |
| Modern | HEIC, HEIF, AVIF, JXL |
| Vector | SVG, EPS, PDF |
| RAW | NEF, CR2, CR3, ARW, DNG, RAF, ORF, RW2, PEF, SRW |
| Special | PSD, XCF, HDR, EXR, TGA, ICO |

### Image Output Formats
PNG, JPG, WebP, GIF, TIFF, BMP, ICO, PDF

### Document Formats

| Input Formats | Output Formats |
|---------------|----------------|
| DOCX, DOC | PDF |
| Markdown (.md) | DOCX |
| HTML | HTML |
| RTF | TXT |
| CSV, TSV | Markdown |
| JSON | |
| RST | |
| EPUB | |
| ODT | |
| DocBook | |

### Audio Formats

| Input Formats | Output Formats |
|---------------|----------------|
| MP3, WAV, FLAC, OGG, AAC, M4A | MP3 |
| WMA, AMR, AC3, AIFF, OPUS | WAV |
| AU, VOC, WEBA, ALAC, CAF | FLAC |
| **Video formats (extract audio):** | AAC |
| MP4, MKV, AVI, MOV, WebM | OGG |
| TS, MTS, M2TS, WMV, MPG | M4A |
| MPEG, FLV, F4V, VOB, M4V | OPUS |
| 3GP, 3G2, MXF, OGV, RM | |

### Video Formats

| Input Formats | Output Formats |
|---------------|----------------|
| MKV, MP4, WebM, AVI, WMV | MP4 |
| MOV, GIF, MTS, TS, M2TS | WebM |
| MPG, MPEG, FLV, F4V, VOB | AVI |
| M4V, 3GP, 3G2, MXF, OGV | MKV |
| RM, RMVB, H264, DIVX | MOV |
| SWF, AMV, ASF, NUT | GIF, WMV, FLV |

## API Reference

### Create Job
```
POST /api/jobs
Content-Type: multipart/form-data
```

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | The file to process (required) |
| `job_type` | String | `ocr`, `image`, `document`, `audio`, or `video` (default: `ocr`) |

**OCR Options (`job_type=ocr`):**
| Field | Type | Description |
|-------|------|-------------|
| `mode` | String | `text`, `ocr`, or `both` (default: `text`) |

**Image Options (`job_type=image`):**
| Field | Type | Description |
|-------|------|-------------|
| `output_format` | String | `png`, `jpg`, `webp`, `gif`, `tiff`, `bmp`, `ico`, `pdf` |
| `quality` | Integer | 1-100 (default: 85) |
| `resize_width` | Integer | Target width in pixels |
| `resize_height` | Integer | Target height in pixels |
| `resize_percent` | Integer | Scale percentage (1-500) |
| `dpi` | Integer | Output DPI |
| `rotation` | Integer | 0, 90, 180, or 270 |
| `brightness` | Float | 0.0-2.0 (default: 1.0) |
| `contrast` | Float | 0.0-2.0 (default: 1.0) |
| `grayscale` | Boolean | `true` or `false` |

**Document Options (`job_type=document`):**
| Field | Type | Description |
|-------|------|-------------|
| `output_format` | String | `pdf`, `docx`, `html`, `txt`, or `md` (default: `pdf`) |

**Audio Options (`job_type=audio`):**
| Field | Type | Description |
|-------|------|-------------|
| `output_format` | String | `mp3`, `wav`, `flac`, `aac`, `ogg`, `m4a`, or `opus` (default: `mp3`) |
| `bitrate` | String | `128`, `192`, `256`, or `320` (default: `192`) |

**Video Options (`job_type=video`):**
| Field | Type | Description |
|-------|------|-------------|
| `output_format` | String | `mp4`, `webm`, `avi`, `mkv`, `mov`, `gif`, `wmv`, or `flv` (default: `mp4`) |
| `quality` | String | `low`, `medium`, or `high` (default: `medium`) |

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "result_url": "/api/jobs/<id>/result"
}
```

### Get Job Status
```
GET /api/jobs/<job_id>
```

**Response:**
```json
{
  "id": "uuid",
  "status": "completed",
  "progress": 100,
  "filename": "document.pdf",
  "result_path": "/path/to/result.json",
  "text_path": "/path/to/result.txt",
  "pdf_path": "/path/to/result.pdf",
  "image_path": "/path/to/converted.png",
  "document_path": "/path/to/converted.pdf",
  "audio_path": "/path/to/converted.mp3",
  "video_path": "/path/to/converted.mp4"
}
```

### Get Job Result
```
GET /api/jobs/<job_id>/result
```

### Download Files
```
GET /api/jobs/<job_id>/download/txt      # OCR text output
GET /api/jobs/<job_id>/download/json     # Full result JSON
GET /api/jobs/<job_id>/download/pdf      # OCR'd PDF
GET /api/jobs/<job_id>/download/image    # Converted image
GET /api/jobs/<job_id>/download/document # Converted document
GET /api/jobs/<job_id>/download/audio    # Converted audio
GET /api/jobs/<job_id>/download/video    # Converted video
```

## Dependencies

- **Flask**: Web framework
- **Pillow**: Image processing utilities
- **pytesseract**: Tesseract OCR wrapper
- **pdf2image**: PDF to image conversion
- **reportlab**: PDF generation
- **pypdf**: PDF manipulation
- **Wand**: ImageMagick Python bindings
- **pypandoc**: Pandoc Python bindings for document conversion
- **pydub**: FFmpeg Python bindings for audio conversion

## License

MIT
