"""Receipt field extractor."""

import re
from typing import Any, Dict, List, Optional

from app.pipeline.ocr_types import OcrBlock

from .base import BaseExtractor


class ReceiptExtractor(BaseExtractor):
    def extract(
        self, ocr_text: str, ocr_blocks: List[OcrBlock]
    ) -> Dict[str, Any]:
        return {
            "claimant_name": self._extract_claimant_name(ocr_text),
            "claimant_address": self._extract_address(ocr_text),
            "claimant_date_of_birth": self._extract_date(
                ocr_text, r"(?:DOB|Date\s*of\s*Birth|Birth\s*Date)"
            ),
            "provider_name": self._clean_provider_name(
                self._extract_provider(ocr_text)
            ),
            "tax_amount": self._extract_amount(ocr_text, r"(?:Tax|GST|VAT)\s*@\s*\d+%"),
            "total_amount": self._extract_amount(
                ocr_text,
                r"(?:Total\s*Amount\s*Paid|Total\s*Charges\s*After\s*GST|Total|Amount\s*Due|Grand\s*Total)",
            ),
        }

    def _extract_provider(self, text: str) -> Optional[str]:
        patterns = [
            r"^(RafflesMedical.*)$",
            r"([A-Z][A-Za-z\s]+Medical)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None