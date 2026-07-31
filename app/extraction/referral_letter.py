"""Referral Letter field extractor."""

import re
from typing import Any, Dict, List, Optional

from app.pipeline.ocr_types import OcrBlock

from .base import BaseExtractor


class ReferralLetterExtractor(BaseExtractor):
    def extract(
        self, ocr_text: str, ocr_blocks: List[OcrBlock]
    ) -> Dict[str, Any]:
        return {
            "claimant_name": self._extract_claimant_name(ocr_text),
            "provider_name": self._clean_provider_name(
                self._extract_provider(ocr_text)
            ),
            "signature_presence": None,  # filled by SignatureDetector
            "total_amount_paid": self._extract_amount(
                ocr_text, r"total\s*amount\s*paid"
            ),
            "total_approved_amount": self._extract_amount(
                ocr_text, r"total\s*approved\s*amount"
            ),
            "total_requested_amount": self._extract_amount(
                ocr_text, r"total\s*requested\s*amount"
            ),
        }

    def _extract_provider(self, text: str) -> Optional[str]:
        patterns = [
            r"^\s*([A-Z][A-Za-z\s@&]+(?:Screening|Clinic|Hospital)[A-Za-z\s@&]*)$",
            r"(?:From|Provider|Clinic|Hospital|Referred\s+to)[\s:]*([A-Z][\w\s&.,]+?)(?:\n|$)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None