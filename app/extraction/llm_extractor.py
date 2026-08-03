"""LLM-based document extraction — replaces classifier + regex extractors."""

import json
import logging
import re
import time
from typing import Any, Dict

from openai import OpenAI

from app.config import config

logger = logging.getLogger(__name__)

# Maps LLM-returned fields to the canonical schema field names
_FIELD_ALIASES: Dict[str, str] = {
    # medical_certificate aliases
    "name": "claimant_name",
    "nric": "claimant_address",
    "nric_fin_passport": "claimant_address",
    "address": "claimant_address",
    "dob": "claimant_date_of_birth",
    "date_of_birth": "claimant_date_of_birth",
    "birth_date": "claimant_date_of_birth",
    "diagnosis": "diagnosis_name",
    "discharge_date": "discharge_date_time",
    "discharged": "discharge_date_time",
    "admission_date": "submission_date_time",
    "admitted_on": "submission_date_time",
    "admitted": "submission_date_time",
    "submission_date": "submission_date_time",
    "mc_date": "date_of_mc",
    "date": "date_of_mc",
    "issued_date": "date_of_mc",
    "days": "mc_days",
    "duration_days": "mc_days",
    "period_days": "mc_days",
    "clinic": "provider_name",
    "clinic_name": "provider_name",
    "hospital": "provider_name",
    "hospital_clinic": "provider_name",
    "icd": "icd_code",
    "icd10": "icd_code",
    # receipt aliases
    "patient_name": "claimant_name",
    "patient": "claimant_name",
    "pay_by": "claimant_name",
    "total": "total_amount",
    "total_amount_paid": "total_amount",
    "total_charges": "total_amount",
    "grand_total": "total_amount",
    "amount_due": "total_amount",
    "tax": "tax_amount",
    "gst": "tax_amount",
    "vat": "tax_amount",
    "merchant": "provider_name",
    "store": "provider_name",
    # referral_letter aliases
    "patient": "claimant_name",
    "doctor": "provider_name",
    "referring_doctor": "provider_name",
    "signature": "signature_presence",
    "signed": "signature_presence",
}

# Canonical fields per document type
_CANONICAL_FIELDS: Dict[str, set] = {
    "referral_letter": {
        "claimant_name", "provider_name", "signature_presence",
        "total_amount_paid", "total_approved_amount", "total_requested_amount",
    },
    "medical_certificate": {
        "claimant_name", "claimant_address", "claimant_date_of_birth",
        "diagnosis_name", "discharge_date_time", "icd_code",
        "provider_name", "submission_date_time", "date_of_mc", "mc_days",
    },
    "receipt": {
        "claimant_name", "claimant_address", "claimant_date_of_birth",
        "provider_name", "tax_amount", "total_amount",
    },
}

SYSTEM_PROMPT = """You are a medical document parser. Classify the OCR text as referral_letter, medical_certificate, receipt, or unknown. Extract fields.
Return ONLY valid JSON:
{"document_type":"<type>","fields":{...}}
Fields per type:
referral_letter: claimant_name, provider_name, signature_presence(bool), total_amount_paid(int), total_approved_amount(int), total_requested_amount(int)
medical_certificate: claimant_name, claimant_address, claimant_date_of_birth, diagnosis_name, discharge_date_time, icd_code, provider_name, submission_date_time, date_of_mc, mc_days(int)
receipt: claimant_name, claimant_address, claimant_date_of_birth, provider_name, tax_amount(int), total_amount(int)
Rules: missing=null. Amounts to int (rm $/commas/decimals). Dates to DD/MM/YYYY."""


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
        fields = self._normalize_fields(doc_type, result.get("fields", {}))

        valid_types = {"referral_letter", "medical_certificate", "receipt", "unknown"}
        if doc_type not in valid_types:
            doc_type = "unknown"
            fields = {}

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

    def _normalize_fields(
        self, doc_type: str, fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize LLM-returned fields to canonical schema."""
        canonical = _CANONICAL_FIELDS.get(doc_type)
        if not canonical:
            return fields

        normalized: Dict[str, Any] = {}
        for key in canonical:
            if key in fields:
                normalized[key] = self._coerce_value(key, fields[key])
            elif key in _FIELD_ALIASES:
                # Already aliased
                normalized[key] = self._coerce_value(key, fields[key])
            else:
                normalized[key] = None

        # Map aliased fields
        for src, dst in _FIELD_ALIASES.items():
            if dst in canonical and src in fields and dst not in normalized:
                normalized[dst] = self._coerce_value(dst, fields[src])

        return normalized

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

        # String fields
        if isinstance(value, (int, float)):
            return str(value)
        return str(value) if value else None

        return {"document_type": doc_type, "fields": fields}