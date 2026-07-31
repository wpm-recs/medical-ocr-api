"""Medical Certificate field extractor."""

import re
from typing import Any, Dict, List, Optional

from app.pipeline.ocr_types import OcrBlock

from .base import BaseExtractor


class MedicalCertificateExtractor(BaseExtractor):
    def extract(
        self, ocr_text: str, ocr_blocks: List[OcrBlock]
    ) -> Dict[str, Any]:
        return {
            "claimant_name": self._extract_claimant_name(ocr_text),
            "claimant_address": self._extract_address(ocr_text),
            "claimant_date_of_birth": self._extract_date(
                ocr_text, r"(?:DOB|Date\s*of\s*Birth|Birth\s*Date)"
            ),
            "diagnosis_name": self._extract_diagnosis(ocr_text),
            "discharge_date_time": self._extract_date(
                ocr_text, r"(?:Discharge\s*Date|Discharged)"
            ),
            "icd_code": self._extract_icd_code(ocr_text),
            "provider_name": self._clean_provider_name(
                self._extract_provider(ocr_text)
            ),
            "submission_date_time": self._extract_date(
                ocr_text, r"(?:Admission|Admitted|Submission)"
            ),
            "date_of_mc": self._extract_date_of_mc(ocr_text),
            "mc_days": self._extract_mc_days(ocr_text),
        }

    def _extract_date_of_mc(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:Date\s*of\s*MC|MC\s*Date|Medical\s*Certificate\s*Date)[\s:]*"
            r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
            # "from DD/MM/YYYY to DD/MM/YYYY" — take the first date as MC date
            r"from\s+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+to",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return self._normalize_date(match.group(1))
        return None

    def _extract_icd_code(self, text: str) -> Optional[str]:
        patterns = [
            r"ICD[-\s]*10[-\s]*CM[:\s]*([A-Z]\d{2}(?:\.\d{1,3})?)",
            r"ICD[-\s]*\d{1,2}[:\s]*([A-Z]\d{2}(?:\.\d{1,3})?)",
            r"([A-Z]\d{2}\.\d{1,3})",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_diagnosis(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:Diagnosis|Diagnosed\s+with)[\s:]*([A-Z][\w\s,]+?)(?:\n|$)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_mc_days(self, text: str) -> Optional[int]:
        patterns = [
            r"(?:MC\s*Days|Days\s*of\s*MC|Medical\s*Leave)[\s:]*(\d+)",
            r"(\d+)\s*(?:days|Days)\s*(?:MC|medical\s*leave)",
            r"period\s+of\s+(\d+)\s+days",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _extract_provider(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:HOSPITAL/CLINIC)[\s:]*([A-Z][\w\s&.,-]+)",
            r"(Minmed\s+Health\s+Screeners)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None