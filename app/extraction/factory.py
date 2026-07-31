"""Extractor factory: maps document_type → extractor class."""

from .base import BaseExtractor
from .medical_certificate import MedicalCertificateExtractor
from .receipt import ReceiptExtractor
from .referral_letter import ReferralLetterExtractor

EXTRACTOR_MAP: dict[str, type[BaseExtractor]] = {
    "referral_letter": ReferralLetterExtractor,
    "medical_certificate": MedicalCertificateExtractor,
    "receipt": ReceiptExtractor,
}


def get_extractor(document_type: str) -> BaseExtractor:
    cls = EXTRACTOR_MAP.get(document_type)
    if cls is None:
        raise ValueError(f"No extractor registered for type: {document_type}")
    return cls()
