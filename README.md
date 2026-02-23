# OCR Engine

Full-featured Flask app for document text extraction, image conversion, document format conversion, audio conversion, and video conversion. Supports OCR via Tesseract, image processing via ImageMagick, document conversion via Pandoc, and audio/video conversion via FFmpeg.

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

The easiest way to run OCR Engine is with Docker - all dependencies are included.

### Using Docker Compose (Recommended)
```bash
# Clone and start (basic - without Tika)
git clone <repository-url>
cd ocr-engine
docker-compose up -d

# OR start with Apache Tika for enhanced text extraction
docker-compose -f docker-compose.full.yml up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Using Docker directly
```bash
# Build the image
docker build -t ocr-engine .

# Run the container
docker run -d \
  --name ocr-engine \
  -p 5001:5001 \
  -v ocr-data:/app/data \
  -e MAX_FILE_MB=25 \
  ocr-engine

# Stop and remove
docker stop ocr-engine && docker rm ocr-engine
```

The app will be available at `http://localhost:5001`

### Docker Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_MB` | `25` | Maximum upload file size in MB |
| `TIKA_SERVER_URL` | `http://localhost:9998` | Apache Tika server URL (optional) |

### Data Persistence
The Docker setup uses a named volume `ocr-data` to persist:
- Uploaded files (`/app/data/uploads`)
- Conversion results (`/app/data/results`)
- SQLite database (`/app/data/jobs.db`)

### Apache Tika (Optional)
Apache Tika enhances text extraction from PDFs and documents. Two deployment options:

| Setup | Command | Use Case |
|-------|---------|----------|
| Basic | `docker-compose up -d` | OCR, image/audio/video conversion |
| Full (with Tika) | `docker-compose -f docker-compose.full.yml up -d` | Enhanced text extraction from PDFs |

Tika provides better extraction of embedded text from PDFs without OCR, useful for digital PDFs with selectable text.

---

## Manual Setup (Without Docker)

### 1. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
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
python app.py
```
The app will run on `http://localhost:5001`

---

## Configuration

Environment variables:
- `TIKA_SERVER_URL` (default `http://localhost:9998`)
- `MAX_FILE_MB` (default `25`)

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
