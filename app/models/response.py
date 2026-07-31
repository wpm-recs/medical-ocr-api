"""Pydantic response models for the OCR API."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class DocumentType(str, Enum):
    REFERRAL_LETTER = "referral_letter"
    MEDICAL_CERTIFICATE = "medical_certificate"
    RECEIPT = "receipt"


class OcrResult(BaseModel):
    document_type: DocumentType
    total_time: float
    ocr_time: Optional[float] = None
    classification_time: Optional[float] = None
    extraction_time: Optional[float] = None
    finalJson: Dict[str, Any]


class OcrResponse(BaseModel):
    message: str
    result: OcrResult


class ErrorResponse(BaseModel):
    error: str