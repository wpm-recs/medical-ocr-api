# Medical OCR API

A microservice that performs OCR, automatically detects document types (Referral Letters, Medical Certificates, Receipts), and extracts structured data for healthcare claim adjudication.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Reference](#api-reference)
3. [Web UI](#web-ui)
4. [Sample cURL Commands](#sample-curl-commands)
5. [How to Extend](#how-to-extend)
6. [Project Structure](#project-structure)
7. [Testing](#testing)

---

## Quick Start

### Prerequisites

- **Python**: 3.9+ (project tests were run under Python 3.9.6 in the repository `.venv`)
- **LLM API key**: Required for document classification and field extraction. Supports any OpenAI-compatible API (GPT, DeepSeek, etc.). Set `LLM_API_KEY` in `.env`.
- **System dependencies**: Poppler (for `pdf2image`) — install via `apt-get install poppler-utils` (Linux) or [Windows binaries](http://blog.alivate.com.au/poppler-windows/).
Additionally this project requires the Tesseract OCR binary (the Python package `pytesseract` is a wrapper).

Install Tesseract on common platforms:

- macOS (Homebrew):

```bash
brew install tesseract
```

- Ubuntu / Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

- Windows:

Download and install the appropriate Windows installer from the Tesseract project or use Chocolatey:

```powershell
choco install tesseract
```

After installing the Tesseract binary, ensure it's on your `PATH` so `pytesseract` can find it. On macOS/Linux the Homebrew/apt packages typically handle this automatically.

### Install & Run

```bash
# 1. Clone the project
git clone <repo-url>
cd medical-ocr-api

# 2. Install system dependencies (Linux)
sudo apt-get install -y poppler-utils   # Ubuntu / Debian
# sudo dnf install -y poppler-utils     # Fedora / RHEL
# sudo pacman -S poppler                # Arch Linux

# 3. Create & activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment (REQUIRED: set LLM_API_KEY)
cp .env.example .env
# Edit .env and set LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

# 6. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs are auto-generated at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Docker

```bash
docker-compose up -d --build
```

---

## API Reference

### `POST /ocr`

Upload a document (PDF / JPEG / PNG) and receive structured extraction results.

**Request**

```
POST /ocr
Content-Type: multipart/form-data
file=<binary document>
```

**Supported MIME types**: `application/pdf`, `image/jpeg`, `image/png`, `image/tiff`

**Response `200 OK`**

```json
{
  "message": "Processing completed.",
  "result": {
    "document_type": "referral_letter",
    "total_time": 3.04,
    "ocr_time": 1.82,
    "classification_time": 0.12,
    "extraction_time": 1.10,
    "finalJson": {
      "claimant_name": "John Smith",
      "provider_name": "City Medical Clinic",
      "signature_presence": true,
      "total_amount_paid": 3000000,
      "total_approved_amount": 3000000,
      "total_requested_amount": 3000000
    }
  }
}
```

**Document types and extracted fields**

| Type | Fields |
|------|--------|
| `referral_letter` | `claimant_name`, `provider_name`, `signature_presence`, `total_amount_paid`, `total_approved_amount`, `total_requested_amount` |
| `medical_certificate` | `claimant_name`, `claimant_address`, `claimant_date_of_birth`, `diagnosis_name`, `discharge_date_time`, `icd_code`, `provider_name`, `submission_date_time`, `date_of_mc`, `mc_days` |
| `receipt` | `claimant_name`, `claimant_address`, `claimant_date_of_birth`, `provider_name`, `tax_amount`, `total_amount` |

Missing / un-parsable fields are returned as `null`.

**Error responses**

| Status | Body | Condition |
|--------|------|-----------|
| `400` | `{"error":"file_missing"}` | No file or invalid MIME type |
| `422` | `{"error":"unsupported_document_type"}` | Document doesn't match any supported type |
| `500` | `{"error":"internal_server_error"}` | Unhandled exception |

### `GET /health`

```json
{"status":"ok","ocr_engine":"tesseract","version":"1.0.0"}
```

---

## Web UI

The service includes a built-in web interface at the root path (`/`), providing a visual way to upload documents and inspect extraction results without using the command line.

### Access

Open http://localhost:8000 in your browser after starting the server.

### Online Demo

You can also try the deployed demo directly here:

- https://medical-ocr.greensky-c0f2aeba.eastasia.azurecontainerapps.io

### Test Cases

Use the following sample files from the repository to test the online demo:

```bash
# Referral Letter
curl --fail-with-body -X POST "https://medical-ocr.greensky-c0f2aeba.eastasia.azurecontainerapps.io/ocr" \
  -F "file=@Example/referral_letter.pdf"

# Medical Certificate
curl --fail-with-body -X POST "https://medical-ocr.greensky-c0f2aeba.eastasia.azurecontainerapps.io/ocr" \
  -F "file=@Example/medical_certificate.pdf"

# Receipt
curl --fail-with-body -X POST "https://medical-ocr.greensky-c0f2aeba.eastasia.azurecontainerapps.io/ocr" \
  -F "file=@Example/receipt.pdf"
```

### Features

- **Drag & drop** or click to upload PDF / JPEG / PNG documents
- **Live preview** of the uploaded file name
- **One-click processing** — sends the file to `POST /ocr` and displays results
- **Formatted JSON output** with document type, timing breakdown, and all extracted fields
- **Error display** for unsupported file types or processing failures

### Screenshot

![Web UI Screenshot](Screenshot/WebUI.png)

---

## Sample cURL Commands

```bash
# Referral Letter
curl -X POST http://localhost:8000/ocr \
  -F "file=@Example/referral_letter.pdf"

# Medical Certificate
curl -X POST http://localhost:8000/ocr \
  -F "file=@Example/medical_certificate.pdf"

# Receipt
curl -X POST http://localhost:8000/ocr \
  -F "file=@Example/receipt.pdf"

# Image upload
curl -X POST http://localhost:8000/ocr \
  -F "file=@document.jpg"

# Health check
curl http://localhost:8000/health
```

---

## How to Extend

The service uses a single LLM prompt (`SYSTEM_PROMPT` in `app/extraction/llm_extractor.py`) to handle both classification and field extraction. Adding a new document type requires two steps:

### Step 1 — Add the type to the enum

```python
# app/models/response.py
class DocumentType(str, Enum):
    REFERRAL_LETTER = "referral_letter"
    MEDICAL_CERTIFICATE = "medical_certificate"
    RECEIPT = "receipt"
    PRESCRIPTION = "prescription"   # <-- new
```

### Step 2 — Add the JSON template to the LLM prompt

```python
# app/extraction/llm_extractor.py → SYSTEM_PROMPT
# Add a new template block for the document type:

prescription:
{"document_type":"prescription","fields":{"medication_name":"...","dosage":"...","prescribing_doctor":"..."}}
```

The LLM will automatically classify the document into the new type and return the specified fields. No separate classifier or extractor class is needed.

---

## Project Structure

```
medical-ocr-api/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment configuration
│   ├── models/
│   │   └── response.py            # Pydantic response schemas
│   ├── api/
│   │   └── ocr.py                 # POST /ocr + GET /health endpoints
│   ├── pipeline/
│   │   ├── preprocessor.py        # PDF → image, embedded text extraction
│   │   ├── ocr_engine.py          # Tesseract (pytesseract) abstraction
│   │   ├── ocr_types.py           # OcrBlock / OcrResult dataclasses
│   │   └── normalizer.py          # Text cleaning & normalization
│   ├── extraction/
│   │   ├── llm_extractor.py       # LLM-based classification + extraction
│   │   └── signature.py           # Handwritten signature detector (OpenCV)
│   ├── classification/            # (reserved for future non-LLM classifier)
│   └── static/
│       └── index.html             # Web UI
├── tests/
│   ├── conftest.py
│   └── test_api.py                # API endpoint tests
├── Example/                       # Sample documents
├── Screenshot/                    # Web UI screenshot
├── doc/
│   └── 开发文档.md                 # Full design document (Chinese)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Specific test file
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

Example test run (project `.venv`):

```bash
$ pytest tests/test_api.py -v
tests/test_api.py::TestAPI::test_health_check PASSED
tests/test_api.py::TestAPI::test_missing_file PASSED
tests/test_api.py::TestAPI::test_invalid_mime PASSED
tests/test_api.py::TestAPI::test_unsupported_document PASSED
tests/test_api.py::TestAPI::test_empty_filename PASSED
======================== 5 passed, 5 warnings in 0.09s =========================

Verification environment (used when the repository tests were run):

- OS: macOS 26.6 (arm64) on Apple M1 Pro (8 cores)
- Python: 3.9.6 (project `.venv`)
- pytest: 8.4.2
- Tesseract: 5.5.3 (`/opt/homebrew/bin/tesseract`)

If your environment differs (for example Linux CI or different Python), follow the Quick Start prerequisites above.
```

---

> **Author**: Shou Yichen &nbsp;|&nbsp; **Contact**: syc1240831356@icloud.com
