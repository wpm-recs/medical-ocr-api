# Medical OCR API

A microservice that performs OCR, automatically detects document types (Referral Letters, Medical Certificates, Receipts), and extracts structured data for healthcare claim adjudication.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Reference](#api-reference)
3. [Sample cURL Commands](#sample-curl-commands)
4. [How to Extend](#how-to-extend)
5. [Project Structure](#project-structure)
6. [Testing](#testing)

---

## Quick Start

### Prerequisites

- **Python**: 3.10+
- **System dependencies**:
  - Poppler (for `pdf2image`) — [Windows binaries](http://blog.alivate.com.au/poppler-windows/)
  - Tesseract OCR (optional, only if using `OCR_ENGINE=tesseract`)

### Install & Run

```bash
# 1. Clone the project
git clone <repo-url>
cd medical-ocr-api

# 2. Create & activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Configure environment
cp .env.example .env

# 5. Start the server
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
{"status":"ok","ocr_engine":"paddleocr","version":"1.0.0"}
```

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

Adding a new document type requires only three steps:

### Step 1 — Add the type to the enum

```python
# app/models/response.py
class DocumentType(str, Enum):
    REFERRAL_LETTER = "referral_letter"
    MEDICAL_CERTIFICATE = "medical_certificate"
    RECEIPT = "receipt"
    PRESCRIPTION = "prescription"   # <-- new
```

### Step 2 — Add classification patterns

```python
# app/classification/classifier.py → TYPE_PATTERNS
"prescription": {
    "keywords": ["prescription", "Rx", "dispense", "dosage"],
    "required_fields": [
        r"medication|drug|medicine",
        r"dosage|dose",
    ],
    "exclude_keywords": ["receipt", "invoice"]
}
```

### Step 3 — Implement a new extractor and register it

```python
# app/extraction/prescription.py
from .base import BaseExtractor

class PrescriptionExtractor(BaseExtractor):
    def extract(self, ocr_text, ocr_blocks):
        return {
            "medication_name": self._extract_medication(ocr_text),
            "dosage": self._extract_dosage(ocr_text),
            "prescribing_doctor": self._extract_name(ocr_text),
        }

# app/extraction/factory.py — register
EXTRACTOR_MAP["prescription"] = PrescriptionExtractor
```

### Switch OCR engine

```bash
# Environment variable
OCR_ENGINE=tesseract   # switch to Tesseract
OCR_ENGINE=paddleocr   # switch to PaddleOCR (default)
```

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
│   │   ├── preprocessor.py        # PDF → image, deskew, denoise
│   │   ├── ocr_engine.py          # PaddleOCR / Tesseract abstraction
│   │   └── normalizer.py          # Text cleaning & normalization
│   ├── classification/
│   │   └── classifier.py          # Keyword + regex rule engine
│   └── extraction/
│       ├── base.py                # BaseExtractor (name/date/amount/address)
│       ├── referral_letter.py     # Referral letter extractor
│       ├── medical_certificate.py # Medical certificate extractor
│       ├── receipt.py             # Receipt extractor
│       ├── signature.py           # Handwritten signature detector
│       └── factory.py             # Extractor factory
├── tests/
│   ├── conftest.py
│   ├── test_classifier.py         # 5 classifier tests
│   ├── test_extractors.py         # 10 extractor tests
│   └── test_api.py                # 5 API endpoint tests
├── Example/                       # Sample documents
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

# Specific test files
pytest tests/test_classifier.py -v
pytest tests/test_extractors.py -v
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

> **Author**: Shou Yichen &nbsp;|&nbsp; **Contact**: syc1240831356@icloud.com
