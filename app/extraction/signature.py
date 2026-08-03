"""Signature detection using OCR text + OpenCV contour analysis.

Multi-feature approach:
  1. Regex word-boundary keyword matching (avoids "design"/"assigned" false hits)
  2. Stamp/seal exclusion via Hough Circle detection
  3. Barcode/QR exclusion via edge projection analysis
  4. Multi-feature handwriting scoring (area dispersion, stroke thinness,
     curvature, ink density) instead of simplistic variance threshold
"""

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
    """Detect handwritten signatures in medical documents.

    Uses OCR text labels as primary signal, then validates with
    multi-feature image analysis that explicitly excludes stamps,
    barcodes, and printed text regions.
    """

    # ── keyword patterns ────────────────────────────────────────────
    # Word-boundary match: catches "Signature", "Signed by" but NOT
    # "design", "assigned", "significant", "resign", "signal"
    SIG_LABEL_RE = re.compile(
        r"\b(signature|signed|signatory|signer)\b", re.IGNORECASE
    )
    # False-positive guard: words that contain "sign" incidentally
    SIG_FALSE_POSITIVE_RE = re.compile(
        r"\b(design|assigned?|significant(?:ly)?|signal|resign|consign|"
        r"clinical\s+signs?|vital\s+signs?|signs?\s+and\s+symptoms)\b",
        re.IGNORECASE,
    )
    # Documents that explicitly state no physical signature is needed
    ELECTRONIC_MC_RE = re.compile(
        r"electronically\s+generated|no\s+signature\s+is\s+required|"
        r"digitally\s+signed|electronic\s+signature",
        re.IGNORECASE,
    )
    # Footer hints that a signature *might* be nearby even without label
    FOOTER_HINT_RE = re.compile(
        r"\b(name|date|doctor|physician|provider|printed\s+name)\b",
        re.IGNORECASE,
    )

    # ── handwriting scoring thresholds ──────────────────────────────
    MIN_CONTOURS = 8          # fewer than this → definitely not handwriting
    MIN_AREAS = 5             # need enough meaningful connected components
    SCORE_THRESHOLD = 0.70    # weighted average must reach this to return True

    def detect(self, image: Image.Image, ocr_blocks: List[OcrBlock]) -> bool:
        """Return True if a handwritten signature is detected."""
        full_text = " ".join(block.text for block in ocr_blocks).lower()

        # Explicit electronic / no-signature-needed statement
        if self.ELECTRONIC_MC_RE.search(full_text):
            return False

        # ── Strategy 1: signature label present ─────────────────────
        if self._has_signature_label(ocr_blocks):
            sig_regions = self._get_signature_regions(ocr_blocks)
            return any(
                self._has_handwriting(image, r) for r in sig_regions
            )

        # ── Strategy 2: no label, but footer hints exist ────────────
        if self._has_potential_signature_area(image, ocr_blocks):
            candidates = self._get_footer_candidate_regions(image, ocr_blocks)
            return any(
                self._has_handwriting(image, r) for r in candidates
            )

        return False

    # ── text-level helpers ──────────────────────────────────────────

    def _has_signature_label(self, blocks: List[OcrBlock]) -> bool:
        """True if any OCR block contains a genuine signature label."""
        for block in blocks:
            text = block.text
            if self.SIG_LABEL_RE.search(text):
                if not self.SIG_FALSE_POSITIVE_RE.search(text):
                    return True
        return False

    def _has_potential_signature_area(
        self, image: Image.Image, blocks: List[OcrBlock]
    ) -> bool:
        """Check for footer hints (name/date/doctor) that suggest a
        signature might be present without an explicit label."""
        h = image.size[1]
        footer_y = int(h * 0.65)
        for block in blocks:
            yc = (block.bbox[0][1] + block.bbox[2][1]) / 2
            if yc >= footer_y and self.FOOTER_HINT_RE.search(block.text):
                return True
        return False

    # ── region extraction ───────────────────────────────────────────

    def _get_signature_regions(self, blocks: List[OcrBlock]) -> List[Rect]:
        """Build search regions to the right of each signature label."""
        regions: List[Rect] = []
        for block in blocks:
            if self.SIG_LABEL_RE.search(block.text):
                x, y = int(block.bbox[0][0]), int(block.bbox[0][1])
                w = int(block.bbox[2][0] - block.bbox[0][0])
                h = int(block.bbox[2][1] - block.bbox[0][1])
                # Search beside and slightly below the label
                regions.append(
                    Rect(x=x + w, y=y - h // 2, width=w * 3, height=h * 3)
                )
        return regions

    def _get_footer_candidate_regions(
        self, image: Image.Image, blocks: List[OcrBlock]
    ) -> List[Rect]:
        """Create targeted regions around footer-hint blocks instead of
        one giant footer rectangle."""
        w_img, h_img = image.size
        footer_y = int(h_img * 0.65)

        footer_blocks = [
            b for b in blocks
            if (b.bbox[0][1] + b.bbox[2][1]) / 2 >= footer_y
            and self.FOOTER_HINT_RE.search(b.text)
        ]
        if footer_blocks:
            regions: List[Rect] = []
            for block in footer_blocks:
                bx, by = int(block.bbox[0][0]), int(block.bbox[0][1])
                bw = int(block.bbox[2][0] - block.bbox[0][0])
                bh = int(block.bbox[2][1] - block.bbox[0][1])
                # Look to the right of footer hints
                regions.append(
                    Rect(x=bx + bw, y=by - bh // 2, width=bw * 3, height=bh * 3)
                )
            return regions

        # Fallback: narrow footer strip
        return [
            Rect(x=0, y=footer_y, width=w_img, height=int(h_img * 0.18))
        ]

    # ── image-level handwriting detection ───────────────────────────

    def _has_handwriting(self, image: Image.Image, region: Rect) -> bool:
        """Multi-feature handwriting classifier.

        Steps:
          1. Exclude stamps / seals (Hough circles)
          2. Exclude barcodes / QR codes (edge projection)
          3. Score on: area dispersion, stroke thinness, curvature, density
          4. Return True only when weighted score ≥ threshold.
        """
        try:
            x1 = max(0, region.x)
            y1 = max(0, region.y)
            x2 = min(image.size[0], region.x + region.width)
            y2 = min(image.size[1], region.y + region.height)
            if x2 <= x1 or y2 <= y1:
                return False

            cropped = image.crop((x1, y1, x2, y2))
            gray = cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2GRAY)

            # ── exclusion checks (fail-fast) ────────────────────
            if self._is_stamp_or_seal(gray):
                return False
            if self._is_barcode_like(gray):
                return False

            # ── binarization ────────────────────────────────────
            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )

            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if len(contours) < self.MIN_CONTOURS:
                return False

            # ── feature extraction ──────────────────────────────
            areas = np.array([
                cv2.contourArea(c) for c in contours
                if cv2.contourArea(c) > 2
            ])
            if len(areas) < self.MIN_AREAS:
                return False

            avg_area = float(np.mean(areas))
            if avg_area <= 0:
                return False

            region_area = (x2 - x1) * (y2 - y1)
            scores = [
                self._score_area_dispersion(areas, avg_area),
                self._score_stroke_thinness(contours, avg_area),
                self._score_curvature(contours),
                self._score_density(areas, region_area),
            ]

            final_score = sum(scores) / len(scores)
            return final_score >= self.SCORE_THRESHOLD

        except Exception:
            return False

    # ── feature scorers (each returns 0.0 – 1.0) ────────────────────

    @staticmethod
    def _score_area_dispersion(areas: np.ndarray, avg: float) -> float:
        """Higher CV → more varied stroke sizes → more likely handwriting."""
        cv_val = float(np.std(areas) / avg)
        if cv_val > 1.0:
            return 1.0
        if cv_val > 0.7:
            return 0.5
        return 0.0

    @staticmethod
    def _score_stroke_thinness(
        contours: list, avg_area: float
    ) -> float:
        """Handwriting strokes are long and thin (high aspect ratio)."""
        thin = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area < 1:
                continue
            rx, ry, rw, rh = cv2.boundingRect(c)
            aspect = max(rw, rh) / (min(rw, rh) + 1)
            if aspect > 3 and area < avg_area * 3:
                thin += 1
        ratio = thin / max(len(contours), 1)
        if ratio > 0.15:
            return 1.0
        if ratio > 0.05:
            return 0.5
        return 0.0

    @staticmethod
    def _score_curvature(contours: list) -> float:
        """Handwriting has curved, concave strokes (low circularity & solidity)."""
        curved = 0
        for c in contours:
            if len(c) < 5:
                continue
            area = cv2.contourArea(c)
            perimeter = cv2.arcLength(c, True)
            if perimeter < 1 or area < 1:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            if hull_area < 1:
                continue
            solidity = area / hull_area
            if circularity < 0.5 and solidity < 0.85:
                curved += 1
        ratio = curved / max(len(contours), 1)
        if ratio > 0.10:
            return 1.0
        if ratio > 0.03:
            return 0.5
        return 0.0

    @staticmethod
    def _score_density(areas: np.ndarray, region_area: int) -> float:
        """Handwriting fills 2%–30% of the region.  Stamps >40%; noise <0.5%."""
        total_ink = float(np.sum(areas))
        density = total_ink / max(region_area, 1)
        if 0.02 < density < 0.30:
            return 1.0
        if 0.005 < density < 0.40:
            return 0.5
        return 0.0

    # ── exclusion detectors ─────────────────────────────────────────

    @staticmethod
    def _is_stamp_or_seal(gray: np.ndarray) -> bool:
        """Detect circular stamps / seals via Hough Circle Transform."""
        try:
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=30,
                param1=50,
                param2=30,
                minRadius=15,
                maxRadius=max(gray.shape) // 2,
            )
            return circles is not None and len(circles[0]) >= 1
        except Exception:
            return False

    @staticmethod
    def _is_barcode_like(gray: np.ndarray) -> bool:
        """Detect barcode / QR patterns via edge projection variance."""
        try:
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.count_nonzero(edges) / max(edges.size, 1)

            # Barcodes have dense, alternating edge patterns
            if edge_density > 0.15:
                h_proj = np.mean(edges, axis=1)
                v_proj = np.mean(edges, axis=0)
                h_cv = float(np.std(h_proj) / (np.mean(h_proj) + 1))
                v_cv = float(np.std(v_proj) / (np.mean(v_proj) + 1))
                if max(h_cv, v_cv) > 1.0:
                    return True
            return False
        except Exception:
            return False
            return False
