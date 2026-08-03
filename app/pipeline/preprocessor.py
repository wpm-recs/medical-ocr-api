"""Document preprocessor: PDF → images."""

import io
import re
from typing import List, Optional

import fitz
from pdf2image import convert_from_bytes
from PIL import Image
from fastapi import UploadFile


class DocumentPreprocessor:
    SUPPORTED_MIMES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }

    def __init__(self, dpi: int = 300):
        self.dpi = dpi
        self.embedded_text: Optional[str] = None

    def preprocess(self, file: UploadFile) -> List[Image.Image]:
        """Convert uploaded file to a list of PIL Images.

        PDFs are rendered at the configured DPI; embedded text is extracted
        as a fallback for keyword-based classification.
        """
        self.embedded_text = None

        if file.content_type == "application/pdf":
            pdf_bytes = file.file.read()
            extracted_text = self._extract_text_from_pdf(pdf_bytes)
            if self._is_text_layer_usable(extracted_text):
                self.embedded_text = extracted_text
            images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
        else:
            images = [Image.open(io.BytesIO(file.file.read()))]

        return images

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    def _is_text_layer_usable(self, text: str) -> bool:
        normalized = re.sub(r"\s+", "", text or "")
        return len(normalized) >= 40
