"""Document classifier using keyword + regex rules with TF-IDF fallback."""

import re
from typing import Tuple


class DocumentClassifier:
    TYPE_PATTERNS = {
        "referral_letter": {
            "keywords": [
                "referral", "referred", "referring physician",
                "refer to", "specialist", "consultation",
                "referral letter", "kindly assist", "dear dr",
                "kind regards", "clinic", "hospital",
            ],
            "required_fields": [
                r"(dear\s+dr|dear\s+doctor)",
                r"(kindly\s+assist|please\s+see|refer(?:red)?\s+for)",
                r"(dr\.?\s+[A-Z]+|doctor)",
            ],
            "exclude_keywords": [
                "medical certificate",
                "tax invoice",
                "subtotal",
                "gst @",
            ],
        },
        "medical_certificate": {
            "keywords": [
                "medical certificate", "certification", "diagnosis",
                "ICD", "discharge", "MC", "medical leave",
                "fit for work", "medical officer", "digital medical certificate",
                "electronically generated", "hospital/clinic",
            ],
            "required_fields": [
                r"medical\s+certificate",
                r"(admitted\s+on|discharged\s+on|date\s+of\s+mc)",
                r"(\d+)\s+days?",
            ],
            "exclude_keywords": ["tax invoice", "subtotal", "kind regards"],
        },
        "receipt": {
            "keywords": [
                "receipt", "invoice", "tax invoice", "payment",
                "total", "subtotal", "GST", "amount due",
                "cash", "credit card", "total amount paid",
                "total balance due", "visit date/time", "bill date",
            ],
            "required_fields": [
                r"tax\s+invoice",
                r"gst\s*@\s*\d+%",
                r"total\s+(amount\s+paid|charges\s+after\s+gst|balance\s+due)",
            ],
            "exclude_keywords": ["medical certificate", "diagnosis", "referral"],
        },
    }

    HARD_CONFLICTS = {"tax invoice", "medical certificate"}

    def classify(self, ocr_text: str) -> Tuple[str, float]:
        scores: dict[str, float] = {}
        for doc_type, patterns in self.TYPE_PATTERNS.items():
            scores[doc_type] = self._calculate_score(ocr_text, patterns)

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        if confidence < 0.3:
            return "unknown", 0.0

        return best_type, min(confidence, 1.0)

    def _calculate_score(self, text: str, patterns: dict) -> float:
        text_lower = text.lower()

        # Hard conflict check: if text contains a strong indicator of another type,
        # return 0 to prevent misclassification.
        if any(kw.lower() in text_lower for kw in patterns["exclude_keywords"]):
            if any(conflict in text_lower for conflict in self.HARD_CONFLICTS):
                return 0.0

        keyword_score = (
            sum(1 for kw in patterns["keywords"] if kw.lower() in text_lower)
            / max(len(patterns["keywords"]), 1)
        )

        field_score = (
            sum(1 for pat in patterns["required_fields"] if re.search(pat, text_lower))
            / max(len(patterns["required_fields"]), 1)
        )

        exclude_penalty = any(
            kw.lower() in text_lower for kw in patterns["exclude_keywords"]
        )

        score = 0.6 * keyword_score + 0.4 * field_score
        if exclude_penalty:
            score *= 0.5

        return score