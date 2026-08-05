"""OCR endpoint handler with full processing pipeline."""

import time
import logging
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Request
from fastapi.responses import JSONResponse

from app.config import config
from app.models.response import OcrResponse, OcrResult, DocumentType
from app.pipeline.preprocessor import DocumentPreprocessor
from app.pipeline.ocr_engine import OcrEngine
from app.pipeline.normalizer import TextNormalizer
from app.extraction.llm_extractor import LlmExtractor
from app.extraction.signature import SignatureDetector

logger = logging.getLogger(__name__)
router = APIRouter()


class UnsupportedDocumentError(Exception):
    pass


class FileValidationError(Exception):
    pass


SUPPORTED_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
}


def _validate_file(file: Optional[UploadFile]) -> None:
    if file is None or not file.filename:
        raise FileValidationError("file_missing")

    mime = file.content_type or ""
    if mime not in SUPPORTED_MIMES:
        raise FileValidationError("file_missing")


def process_document(file: UploadFile) -> OcrResponse:
    t_start = time.time()

    # ---- preprocess ----
    preprocessor = DocumentPreprocessor(dpi=config.ocr_dpi)
    images = preprocessor.preprocess(file)
    embedded_text = preprocessor.embedded_text

    # ---- OCR ----
    t_ocr_start = time.time()
    engine = OcrEngine(engine_type=config.ocr_engine)
    ocr_result = engine.recognize(images, embedded_text=embedded_text)
    normalized_text = TextNormalizer.normalize(ocr_result.full_text)
    ocr_time = round(time.time() - t_ocr_start, 4)

    # ---- LLM: classify + extract in one call ----
    t_llm_start = time.time()
    extractor = LlmExtractor()
    llm_result = extractor.extract(normalized_text)
    doc_type = llm_result["document_type"]
    fields = llm_result["fields"]
    llm_time = round(time.time() - t_llm_start, 4)

    if doc_type == "unknown":
        raise UnsupportedDocumentError("unsupported_document_type")

    # ---- signature (referral_letter only, image-based) ----
    if doc_type == "referral_letter":
        sig_detector = SignatureDetector()
        fields["signature_presence"] = sig_detector.detect(
            images[0], ocr_result.blocks
        )

    total_time = round(time.time() - t_start, 4)

    return OcrResponse(
        message="Processing completed.",
        result=OcrResult(
            document_type=DocumentType(doc_type),
            total_time=total_time,
            ocr_time=ocr_time,
            classification_time=llm_time,
            extraction_time=llm_time,
            finalJson=fields,
        ),
    )


@router.post("/ocr")
async def ocr_endpoint(file: Optional[UploadFile] = File(None)):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    _validate_file(file)

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=config.max_ocr_workers)
    try:
        result = await loop.run_in_executor(executor, process_document, file)
        return result
    finally:
        executor.shutdown(wait=False)


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "ocr_engine": config.ocr_engine,
        "version": config.app_version,
    }