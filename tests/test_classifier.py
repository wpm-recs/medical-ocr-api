"""Unit tests for the document classifier."""

import pytest
from app.classification.classifier import DocumentClassifier


@pytest.fixture
def classifier():
    return DocumentClassifier()


class TestClassifier:
    def test_classify_referral_letter(self, classifier):
        text = """
        Healthway Screening @ Centrepoint
        176 Orchard Road #06-01
        Singapore 218843

        Dear Dr. Athlete's Foot,
        Kindly assist to do evaluation of this patient's mole check. I am referring
        this patient for your review.

        Kind regards,
        Dr. Mark Andersen
        """
        doc_type, confidence = classifier.classify(text)
        assert doc_type == "referral_letter", f"Expected referral_letter, got {doc_type}"
        assert confidence > 0.3

    def test_classify_medical_certificate(self, classifier):
        text = """
        DIGITAL MEDICAL CERTIFICATE

        NAME: JOHN DOE
        NRIC: S1234567A

        This is to certify that the above named patient was examined
        and is unfit for duty for a period of 1 days
        from 30/11/2022 to 30/11/2022.

        HOSPITAL/CLINIC: Minmed Health Screeners

        This medical certificate is electronically generated. No signature is required.
        """
        doc_type, confidence = classifier.classify(text)
        assert doc_type == "medical_certificate", f"Expected medical_certificate, got {doc_type}"
        assert confidence > 0.3

    def test_classify_receipt(self, classifier):
        text = """
        RafflesMedical
        TAX INVOICE

        PAY BY: SELF JOHN DOE
        GST @ 8%
        TOTAL AMOUNT PAID $4,925.00
        TOTAL BALANCE DUE $0.00
        """
        doc_type, confidence = classifier.classify(text)
        assert doc_type == "receipt", f"Expected receipt, got {doc_type}"
        assert confidence > 0.3

    def test_classify_unknown(self, classifier):
        text = "This is just some random text about nothing in particular."
        doc_type, _ = classifier.classify(text)
        assert doc_type == "unknown"

    def test_receipt_not_confused_with_fee_in_referral(self, classifier):
        """Referral letter mentioning a fee should still be classified correctly."""
        text = """
        Dear Dr. Kim,
        Kindly assist to see this patient with chronic back pain.
        The total cost of previous treatment was $300.

        Kind regards,
        Dr. Lee
        """
        doc_type, _ = classifier.classify(text)
        assert doc_type == "referral_letter"
