"""Text normalizer for cleaning OCR output."""

import re


class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        replacements = {
            "\t": " ", "\r": "",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def normalize_all_caps(text: str) -> str:
        """Helper: normalize to uppercase for pattern matching."""
        return re.sub(r"\s+", " ", text or "").strip().upper()
