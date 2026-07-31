"""Signature detection using OCR text + OpenCV contour analysis."""

import re
from typing import List

import cv2
import numpy as np
from PIL import Image

from app.pipeline.ocr_types import OcrBlock


class Rect:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class SignatureDetector:
    def detect(self, image: Image.Image, ocr_blocks: List[OcrBlock]) -> bool:
        full_text = " ".join(block.text for block in ocr_blocks).lower()

        # Electronic MC: explicitly states no signature needed
        if (
            "electronically generated" in full_text
            or "no signature is required" in full_text
        ):
            return False

        # Strategy 1: text keywords
        sig_keywords = ["signature", "signed", "signed by", "sign"]
        has_sig_label = any(
            any(kw in block.text.lower() for kw in sig_keywords)
            for block in ocr_blocks
        )

        # Strategy 2: image analysis
        if not has_sig_label:
            fallback_regions = self._get_footer_candidate_regions(image, ocr_blocks)
            return any(
                self._has_handwriting(image, region) for region in fallback_regions
            )

        sig_regions = self._get_signature_regions(ocr_blocks)
        for region in sig_regions:
            if self._has_handwriting(image, region):
                return True

        return False

    def _get_footer_candidate_regions(
        self, image: Image.Image, blocks: List[OcrBlock]
    ) -> List[Rect]:
        width, height = image.size
        footer_y = int(height * 0.60)
        footer_h = int(height * 0.22)
        return [Rect(x=0, y=footer_y, width=width, height=footer_h)]

    def _get_signature_regions(self, blocks: List[OcrBlock]) -> List[Rect]:
        regions: list[Rect] = []
        sig_keywords = ["signature", "signed", "signed by"]
        for block in blocks:
            if any(kw in block.text.lower() for kw in sig_keywords):
                x, y = int(block.bbox[0][0]), int(block.bbox[0][1])
                w = int(block.bbox[2][0] - block.bbox[0][0])
                h = int(block.bbox[2][1] - block.bbox[0][1])
                regions.append(Rect(x=x, y=y + h, width=w * 3, height=h * 2))
        return regions

    def _has_handwriting(self, image: Image.Image, region: Rect) -> bool:
        try:
            x1 = max(0, region.x)
            y1 = max(0, region.y)
            x2 = min(image.size[0], region.x + region.width)
            y2 = min(image.size[1], region.y + region.height)
            if x2 <= x1 or y2 <= y1:
                return False

            cropped = image.crop((x1, y1, x2, y2))
            gray = cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if len(contours) < 5:
                return False

            areas = [cv2.contourArea(c) for c in contours]
            if len(areas) < 3:
                return False

            avg_area = np.mean(areas)
            if avg_area <= 0:
                return False

            std_area = np.std(areas)
            return (std_area / avg_area) > 0.5
        except Exception:
            return False
