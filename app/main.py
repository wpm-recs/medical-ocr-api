"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import config
from app.api.ocr import router as ocr_router, UnsupportedDocumentError, FileValidationError


def _setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


app = FastAPI(
    title="Medical OCR API",
    version=config.app_version,
    description="OCR microservice for medical documents (referral letters, medical certificates, receipts).",
)

_setup_logging()

app.include_router(ocr_router)


@app.exception_handler(UnsupportedDocumentError)
async def unsupported_document_handler(request: Request, exc: UnsupportedDocumentError):
    return JSONResponse(status_code=422, content={"error": "unsupported_document_type"})


@app.exception_handler(FileValidationError)
async def file_validation_handler(request: Request, exc: FileValidationError):
    return JSONResponse(status_code=400, content={"error": "file_missing"})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "internal_server_error"})

