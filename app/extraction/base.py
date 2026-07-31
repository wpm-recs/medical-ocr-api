"""Base extractor with common field extraction utilities."""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.pipeline.ocr_types import OcrBlock


class BaseExtractor(ABC):
    @abstractmethod
    def extract(
        self, ocr_text: str, ocr_blocks: List[OcrBlock]
    ) -> Dict[str, Any]:
        pass

    # ── name ──────────────────────────────────────────────────────────

    def _extract_name(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:Patient|Claimant|Name|Insured)[\s:]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"(?:Patient|Claimant|Name|Insured)[\s:]*([A-Z][A-Z\s]+)",
            r"(?:PAY\s*BY|BILL\s*TO)[\s:]*([A-Z][A-Z\s]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()
        return None

    def _extract_claimant_name(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:NAME|PATIENT|CLAIMANT)[\s:]*([A-Z][A-Z\s]+?)(?:\n|$)",
            r"(?:PAY\s*BY)[\s:]*([A-Z][A-Z\s]+?)(?:\n|$)",
            # Two consecutive uppercase words as a fallback
            r"\b([A-Z]{2,}\s+[A-Z]{2,})\b",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                candidate = re.sub(r"\s+", " ", match.group(1)).strip()
                if len(candidate.split()) >= 2:
                    return candidate.title()
        return None

    # ── address ───────────────────────────────────────────────────────

    def _extract_address(self, text: str) -> Optional[str]:
        patterns = [
            r"([0-9]{1,4}\s+[A-Z][A-Z0-9\s#\-/,]+SINGAPORE\s+\d{6})",
            r"([0-9]{1,4}\s+[A-Z][A-Z0-9\s#\-/,]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip().title()
        return None

    # ── amount ────────────────────────────────────────────────────────

    def _extract_amount(self, text: str, label: str) -> Optional[int]:
        patterns = [
            rf"{label}[\s:$]*([\d,]+\.?\d*)",
            rf"{label}[\s:]*\$?([\d,]+\.?\d*)",
            rf"{label}[\s:._-]*\(?([\d,]+\.?\d*)\)?",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                raw = match.group(1)
                cleaned = re.sub(r"[,\s]", "", raw)
                if "." in cleaned:
                    cleaned = cleaned.split(".")[0]
                return int(cleaned)
        return None

    # ── date ──────────────────────────────────────────────────────────

    def _extract_date(self, text: str, label: str) -> Optional[str]:
        patterns = [
            rf"{label}[\s:]*(\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}})",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return self._normalize_date(match.group(1))
        return None

    def _normalize_date(self, raw: str) -> str:
        raw = raw.replace("-", "/").replace(".", "/")
        parts = raw.split("/")
        if len(parts[2]) == 2:
            parts[2] = "20" + parts[2]
        return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"

    # ── provider ──────────────────────────────────────────────────────

    def _extract_provider(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:HOSPITAL/CLINIC|Provider|Clinic|Hospital)[\s:]*([A-Z][\w\s&.,@-]+)",
            r"^([A-Z][A-Za-z\s@&]+(?:Medical|Clinic|Screening|Hospital)[A-Za-z\s@&]*)$",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip()
        return None

    def _clean_provider_name(self, name: Optional[str]) -> Optional[str]:
        if name and "fullerton health" in name.lower():
            name = re.sub(r"\s*[Ff]ullerton\s*[Hh]ealth\s*", "", name).strip()
        return name