"""Document preprocessor: PDF → images, image enhancement, skew correction."""

import re
import io
from typing import List, Optional

import cv2
import fitz
import numpy as np
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
        self.embedded_text = None

        if file.content_type == "application/pdf":
            pdf_bytes = file.file.read()
            extracted_text = self._extract_text_from_pdf(pdf_bytes)

            if self._is_text_layer_usable(extracted_text):
                self.embedded_text = extracted_text

            images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
        else:
            images = [Image.open(io.BytesIO(file.file.read()))]

        return [self.enhance(img) for img in images]

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    def _is_text_layer_usable(self, text: str) -> bool:
        normalized = re.sub(r"\s+", "", text or "")
        return len(normalized) >= 40

    def enhance(self, image: Image.Image) -> Image.Image:
        img_array = np.array(image)
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()

        # PaddleOCR has its own preprocessing pipeline;
        # only apply mild denoising and deskewing — don't binarize.
        denoised = cv2.fastNlMeansDenoising(gray)
        deskewed = self._correct_skew(denoised)
        return Image.fromarray(deskewed)

    def _correct_skew(self, image: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(image < 250))
        if len(coords) == 0:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
