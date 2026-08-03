"""LLM-based document extraction — replaces classifier + regex extractors."""

import json
import logging
import re
import time
from typing import Any, Dict

from openai import OpenAI

from app.config import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a medical document parser. Classify the OCR text as referral_letter, medical_certificate, receipt, or unknown. Extract fields.

Return ONLY valid JSON. You MUST include EVERY field listed below for the document type, in the exact order shown. Use null for missing values.

TEMPLATES (copy-paste the correct one and fill):

referral_letter:
{"document_type":"referral_letter","fields":{"claimant_name":"...","provider_name":"...","signature_presence":false,"total_amount_paid":null,"total_approved_amount":null,"total_requested_amount":null}}

medical_certificate:
{"document_type":"medical_certificate","fields":{"claimant_name":"...","claimant_address":"...","claimant_date_of_birth":"...","diagnosis_name":"...","discharge_date_time":"...","icd_code":"...","provider_name":"...","submission_date_time":"...","date_of_mc":"...","mc_days":null}}

receipt:
{"document_type":"receipt","fields":{"claimant_name":"...","claimant_address":"...","claimant_date_of_birth":"...","provider_name":"...","tax_amount":null,"total_amount":null}}

RULES:
- submission_date_time = HOSPITAL ADMISSION DATE (e.g. "admitted on"). Do NOT confuse with date_of_mc (MC issue date) or discharge_date_time. null if no admission date.
- discharge_date_time = HOSPITAL DISCHARGE DATE. null if no discharge date.
- date_of_mc = MC ISSUE / CONSULTATION DATE. null if no MC date.
- provider_name: extract the clinic/hospital/medical center name from the letterhead or header. Must NOT contain "Fullerton Health". If the name contains "@" (e.g. "Healthway Screening @ Centrepoint"), preserve it — OCR often misreads "@" as "o", "0", "a", or "at", so fix those: "Healthway Screening 0 Centrepoint" → "Healthway Screening @ Centrepoint", "Healthway Screening at Centrepoint" → "Healthway Screening @ Centrepoint".
- Amounts: output as integer. Remove currency symbols ($/USD/SGD/etc.) and thousand-separator commas. Truncate the decimal part (e.g. "49.28" → 49, "$1,234.56" → 1234). null if absent.
- Dates: DD/MM/YYYY format.
- Booleans: true or false.
- Fix OCR errors: "JOHN DOE D." → "JOHN DOE", "#01-0]" → "#01-01", "#01-0" → "#01-00", "0rchard" → "Orchard", "Slngapore" → "Singapore"."""


class LlmExtractor:
    """Uses an LLM (OpenAI-compatible API) to classify and extract document fields."""

    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not config.llm_api_key:
                raise RuntimeError(
                    "LLM_API_KEY is not set. Please configure it in .env "
                    "or disable LLM extraction."
                )
            self._client = OpenAI(
                api_key=config.llm_api_key,
                base_url=config.llm_base_url or None,
            )
        return self._client

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        """
        Send OCR text to LLM and return {document_type, fields}.
        """
        if not ocr_text.strip():
            return {"document_type": "unknown", "fields": {}}

        max_chars = config.llm_max_input_chars
        if len(ocr_text) > max_chars:
            ocr_text = ocr_text[:max_chars]

        try:
            response = self.client.chat.completions.create(
                model=config.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": ocr_text},
                ],
                temperature=0,
                max_tokens=config.llm_max_tokens,
            )
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise RuntimeError(f"LLM extraction failed: {e}") from e

        raw = response.choices[0].message.content
        if not raw:
            # Some proxies occasionally return empty responses; retry once
            logger.warning("LLM returned empty response, retrying...")
            time.sleep(0.5)
            try:
                response = self.client.chat.completions.create(
                    model=config.llm_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": ocr_text},
                    ],
                    temperature=0,
                    max_tokens=config.llm_max_tokens,
                )
                raw = response.choices[0].message.content
            except Exception as e:
                logger.error(f"LLM retry also failed: {e}")
                return {"document_type": "unknown", "fields": {}}

        if not raw:
            logger.error("LLM returned empty response after retry")
            return {"document_type": "unknown", "fields": {}}

        result = self._parse_json(raw)
        doc_type = result.get("document_type", "unknown")
        fields = result.get("fields", {})

        valid_types = {"referral_letter", "medical_certificate", "receipt", "unknown"}
        if doc_type not in valid_types:
            doc_type = "unknown"
            fields = {}

        # Only coerce values — LLM already outputs complete schema with nulls
        fields = {k: self._coerce_value(k, v) for k, v in fields.items()}

        return {"document_type": doc_type, "fields": fields}

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        # Try extracting any JSON object from the text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        logger.error(f"LLM returned invalid JSON: {raw[:500]}")
        raise RuntimeError("LLM returned invalid JSON")

    @staticmethod
    def _coerce_value(field: str, value: Any) -> Any:
        """Coerce value to the expected type for a field."""
        if value is None:
            return None

        # Amount fields: ensure integer
        if field in (
            "total_amount", "total_amount_paid", "total_approved_amount",
            "total_requested_amount", "tax_amount",
        ):
            if isinstance(value, str):
                # Remove $, commas, decimal part
                value = re.sub(r"[^\d]", "", value.split(".")[0])
                return int(value) if value else None
            if isinstance(value, (int, float)):
                return int(value)
            return None

        # Numeric fields
        if field == "mc_days":
            if isinstance(value, str):
                value = re.sub(r"[^\d]", "", value)
                return int(value) if value else None
            if isinstance(value, (int, float)):
                return int(value)
            return None

        # Boolean fields
        if field == "signature_presence":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1")
            return None

        # Name field: strip trailing garbage like "D.", "P.", "T."
        if field == "claimant_name":
            if isinstance(value, str):
                value = re.sub(r"\s+[A-Z]\.\s*$", "", value.strip())
            return str(value).strip() if value else None

        # Address field: fix Singapore unit number OCR errors
        if field == "claimant_address":
            if isinstance(value, str):
                # "#01-0]" → "#01-01"  (OCR confuses "1" with "]")
                value = re.sub(r"#(\d{1,2})-(\d)\]", r"#\g<1>-\g<2>1", value)
                # "#01-0" with truncated last digit → "#01-00"
                value = re.sub(r"#(\d{1,2})-(\d)(?!\d)", r"#\g<1>-\g<2>\g<2>", value)
            return str(value).strip() if value else None

        # String fields
        if isinstance(value, (int, float)):
            return str(value)
        return str(value) if value else None