"""Unit tests for field extractors."""

import pytest
from app.extraction.referral_letter import ReferralLetterExtractor
from app.extraction.medical_certificate import MedicalCertificateExtractor
from app.extraction.receipt import ReceiptExtractor


class TestReferralLetterExtractor:
    def test_extract_referral_fields(self):
        text = """
        Healthway Screening @ Centrepoint
        176 Orchard Road #06-01
        Singapore 218843

        Dear Dr. Athlete's Foot,
        Kindly assist to do evaluation of this patient's mole check.
        Patient: John Doe

        Kind regards,
        Dr. Mark Andersen
        """
        ext = ReferralLetterExtractor()
        fields = ext.extract(text, [])
        assert fields["claimant_name"] == "John Doe"
        assert "Healthway Screening" in (fields["provider_name"] or "")
        assert fields["signature_presence"] is None  # set by SignatureDetector
        # referral sample doesn't have payment fields
        assert fields["total_amount_paid"] is None

    def test_provider_name_fullerton_cleaned(self):
        text = "Provider: Fullerton Health Medical Centre"
        ext = ReferralLetterExtractor()
        fields = ext.extract(text, [])
        assert "Fullerton" not in (fields["provider_name"] or "")


class TestMedicalCertificateExtractor:
    def test_extract_mc_fields(self):
        text = """
        DIGITAL MEDICAL CERTIFICATE
        NAME: JOHN DOE
        NRIC: S1234567A
        This is to certify that the above named patient was examined
        and is unfit for duty for a period of 1 days
        from 30/11/2022 to 30/11/2022.
        HOSPITAL/CLINIC: Minmed Health Screeners
        This medical certificate is electronically generated.
        """
        ext = MedicalCertificateExtractor()
        fields = ext.extract(text, [])
        assert fields["claimant_name"] == "John Doe"
        assert "Minmed Health Screeners" in (fields["provider_name"] or "")
        assert fields["mc_days"] == 1
        assert fields["date_of_mc"] == "30/11/2022"

    def test_missing_fields_return_null(self):
        text = "Some random MC text without details"
        ext = MedicalCertificateExtractor()
        fields = ext.extract(text, [])
        assert fields["diagnosis_name"] is None
        assert fields["icd_code"] is None
        assert fields["claimant_date_of_birth"] is None


class TestReceiptExtractor:
    def test_extract_receipt_fields(self):
        text = """
        RafflesMedical
        TAX INVOICE
        PAY BY: SELF JOHN DOE
        GST @ 8%      $365.36
        TOTAL AMOUNT PAID $4,925.00
        TOTAL BALANCE DUE $0.00
        """
        ext = ReceiptExtractor()
        fields = ext.extract(text, [])
        assert "John Doe" in (fields["claimant_name"] or "")
        assert "Raffles" in (fields["provider_name"] or "")
        assert fields["tax_amount"] == 365
        assert fields["total_amount"] == 4925

    def test_amount_parsing_strips_commas(self):
        text = "TOTAL AMOUNT PAID: 12,345.67"
        ext = ReceiptExtractor()
        fields = ext.extract(text, [])
        assert fields["total_amount"] == 12345


class TestAmountParsing:
    def test_strips_dollar_sign_and_commas(self):
        text = "Total: $1,234.56"
        from app.extraction.base import BaseExtractor
        class Dummy(BaseExtractor):
            def extract(self, ocr_text, ocr_blocks):
                return {}
        d = Dummy()
        assert d._extract_amount(text, r"Total") == 1234

    def test_returns_none_on_missing(self):
        from app.extraction.base import BaseExtractor
        class Dummy(BaseExtractor):
            def extract(self, ocr_text, ocr_blocks):
                return {}
        d = Dummy()
        assert d._extract_amount("No amount here", r"Total") is None


class TestDateParsing:
    def test_normalizes_dates(self):
        from app.extraction.base import BaseExtractor
        class Dummy(BaseExtractor):
            def extract(self, ocr_text, ocr_blocks):
                return {}
        d = Dummy()
        assert d._normalize_date("30/11/22") == "30/11/2022"
        assert d._normalize_date("01-05-2023") == "01/05/2023"
        assert d._normalize_date("1/2/2024") == "01/02/2024"


class TestProviderNameFilter:
    def test_fullerton_health_removed(self):
        from app.extraction.base import BaseExtractor
        class Dummy(BaseExtractor):
            def extract(self, ocr_text, ocr_blocks):
                return {}
        d = Dummy()
        assert d._clean_provider_name("Fullerton Health Clinic") == "Clinic"
        assert d._clean_provider_name("XYZ Medical") == "XYZ Medical"
