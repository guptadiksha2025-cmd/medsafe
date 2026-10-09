"""
MedSafe OCR & Document Extraction Service
=========================================
Extracts text from medicine packaging images, photos, and PDF documents
(such as electronic or scanned hospital discharge prescriptions).

Supports:
- Image formats: PNG, JPG, JPEG, WEBP (via Pillow + Tesseract OCR)
- PDF documents: Digital PDF text extraction & scanned PDF page OCR (via PyMuPDF / pypdf)

OCR output is treated as UNTRUSTED input — the user must always review
and correct the extracted information before proceeding.
"""

import os
import re
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tesseract setup — auto-detect common Windows install path
# ---------------------------------------------------------------------------
try:
    import pytesseract

    _win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(_win_path):
        pytesseract.pytesseract.tesseract_cmd = _win_path

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# ---------------------------------------------------------------------------
# PyMuPDF / pypdf setup for PDF document support
# ---------------------------------------------------------------------------
try:
    import pymupdf  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# Confidence threshold (0-100). Below this we flag the result as low-confidence.
CONFIDENCE_THRESHOLD = 40

# Common strength patterns found on medicine labels
_STRENGTH_RE = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%|iu|units?)(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%))?)\b',
    re.IGNORECASE,
)

# Common dosage cues
_DOSAGE_KEYWORDS = [
    'once daily', 'twice daily', 'three times', 'every', 'after food',
    'before food', 'at bedtime', 'as needed', 'tablet', 'capsule',
    'per day', 'morning', 'evening', 'night', 'hours',
]


@dataclass
class OCRResult:
    """Container for OCR and PDF extraction output."""
    raw_text: str = ""
    medicine_name: str = ""
    strength: str = ""
    dosage_info: str = ""
    confidence: float = 0.0
    is_low_confidence: bool = True
    is_pdf: bool = False
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Image pre-processing — improve OCR accuracy on photos / scans
# ---------------------------------------------------------------------------

def _preprocess_image(image: Image.Image) -> Image.Image:
    """Convert to greyscale, sharpen, and boost contrast for better OCR."""
    img = image.convert("L")  # greyscale
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    return img


# ---------------------------------------------------------------------------
# PDF Extraction Handlers
# ---------------------------------------------------------------------------

def _extract_from_pdf(pdf_path: str) -> OCRResult:
    """
    Extract text from a PDF file.
    1. First attempts direct digital text extraction (fast and 100% accurate for digital discharge summaries).
    2. If the PDF is scanned (contains images only), renders pages to high-DPI images and runs Tesseract OCR.
    """
    result = OCRResult(is_pdf=True)

    if not os.path.isfile(pdf_path):
        result.warnings.append("Prescription PDF file not found.")
        return result

    extracted_text = ""

    # Strategy 1: PyMuPDF digital text extraction
    if PYMUPDF_AVAILABLE:
        try:
            doc = pymupdf.open(pdf_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    extracted_text += page_text + "\n"
            doc.close()
        except Exception as exc:
            logger.warning("PyMuPDF digital extraction failed on %s: %s", pdf_path, exc)

    # Strategy 2: pypdf fallback for digital text
    if not extracted_text.strip() and PYPDF_AVAILABLE:
        try:
            reader = pypdf.PdfReader(pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception as exc:
            logger.warning("pypdf text extraction failed on %s: %s", pdf_path, exc)

    extracted_text = extracted_text.strip()

    # If meaningful digital text was found (> 15 chars), return high-confidence direct extraction
    if len(extracted_text) >= 15:
        result.raw_text = extracted_text
        result.confidence = 95.0
        result.is_low_confidence = False
        result.medicine_name = _guess_medicine_name(extracted_text)
        result.strength = _extract_strength(extracted_text)
        result.dosage_info = _extract_dosage(extracted_text)
        return result

    # Strategy 3: Scanned PDF — render pages to image and run Tesseract OCR
    if PYMUPDF_AVAILABLE and TESSERACT_AVAILABLE:
        try:
            doc = pymupdf.open(pdf_path)
            ocr_pages_text = []
            page_confidences = []

            for page_idx, page in enumerate(doc):
                # Render page at 200 DPI for optimal OCR clarity
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                processed_img = _preprocess_image(img)

                try:
                    ocr_data = pytesseract.image_to_data(
                        processed_img, output_type=pytesseract.Output.DICT, config="--psm 6"
                    )
                    confs = [int(c) for c in ocr_data.get("conf", []) if int(c) > -1]
                    if confs:
                        page_confidences.extend(confs)

                    page_text = pytesseract.image_to_string(processed_img, config="--psm 6").strip()
                    if page_text:
                        ocr_pages_text.append(page_text)
                except Exception as ocr_err:
                    logger.warning("OCR failed on PDF page %d: %s", page_idx, ocr_err)

            doc.close()

            combined_ocr_text = "\n\n".join(ocr_pages_text).strip()
            if combined_ocr_text:
                result.raw_text = combined_ocr_text
                if page_confidences:
                    result.confidence = sum(page_confidences) / len(page_confidences)
                else:
                    result.confidence = 60.0

                result.is_low_confidence = result.confidence < CONFIDENCE_THRESHOLD
                result.medicine_name = _guess_medicine_name(combined_ocr_text)
                result.strength = _extract_strength(combined_ocr_text)
                result.dosage_info = _extract_dosage(combined_ocr_text)
                return result

        except Exception as render_err:
            logger.warning("Scanned PDF page rendering failed: %s", render_err)

    # Fallback if no text could be extracted from PDF
    if extracted_text:
        result.raw_text = extracted_text
        result.confidence = 50.0
        result.is_low_confidence = True
    else:
        result.warnings.append(
            "Could not extract readable text from this PDF. Please verify and enter the medicine details manually."
        )

    return result


# ---------------------------------------------------------------------------
# Core Extraction Pipeline (Images + PDFs)
# ---------------------------------------------------------------------------

def extract_text_from_file(file_path: str) -> OCRResult:
    """
    Unified extraction entry point supporting both image and PDF files.
    """
    if not os.path.isfile(file_path):
        res = OCRResult()
        res.warnings.append("Document file not found.")
        return res

    # Check for PDF extension or header
    if file_path.lower().endswith('.pdf'):
        return _extract_from_pdf(file_path)

    # Fallback to image OCR
    return extract_text_from_image(file_path)


def extract_text_from_image(image_path: str) -> OCRResult:
    """
    Run extraction on an image or PDF file and return structured OCR results.
    """
    if image_path.lower().endswith('.pdf'):
        return _extract_from_pdf(image_path)

    result = OCRResult()

    if not os.path.isfile(image_path):
        result.warnings.append("Image file not found.")
        return result

    try:
        image = Image.open(image_path)
    except Exception as exc:
        logger.warning("Failed to open image %s: %s", image_path, exc)
        result.warnings.append("Could not open the image. The file may be corrupted or unreadable.")
        return result

    if not TESSERACT_AVAILABLE:
        result.warnings.append("Tesseract OCR engine is not installed on this system.")
        return result

    processed = _preprocess_image(image)

    # --- Extract text with confidence data ---
    try:
        ocr_data = pytesseract.image_to_data(
            processed, output_type=pytesseract.Output.DICT, config="--psm 6"
        )
    except Exception as exc:
        logger.warning("Tesseract failed on %s: %s", image_path, exc)
        result.warnings.append("OCR processing failed. The image may be unreadable.")
        return result

    # Compute average confidence (ignoring -1 entries which mean "no text")
    confidences = [int(c) for c in ocr_data.get("conf", []) if int(c) > -1]
    if confidences:
        result.confidence = sum(confidences) / len(confidences)
    else:
        result.confidence = 0.0

    result.raw_text = pytesseract.image_to_string(processed, config="--psm 6").strip()

    if not result.raw_text:
        result.warnings.append("No readable text could be extracted from the image.")
        return result

    result.is_low_confidence = result.confidence < CONFIDENCE_THRESHOLD

    if result.is_low_confidence:
        result.warnings.append(
            "Medicine information could not be confidently identified. Please verify the details manually."
        )

    # --- Parse structured fields from raw text ---
    result.medicine_name = _guess_medicine_name(result.raw_text)
    result.strength = _extract_strength(result.raw_text)
    result.dosage_info = _extract_dosage(result.raw_text)

    return result


# ---------------------------------------------------------------------------
# Prescription-specific extraction (returns raw text only)
# ---------------------------------------------------------------------------

def extract_prescription_text(file_path: str) -> OCRResult:
    """
    Extract raw text from a discharge prescription image or PDF.
    """
    if file_path.lower().endswith('.pdf'):
        result = _extract_from_pdf(file_path)
    else:
        result = extract_text_from_image(file_path)

    # For prescriptions we intentionally preserve raw text for user review
    result.medicine_name = ""
    result.strength = ""
    result.dosage_info = ""
    return result


# ---------------------------------------------------------------------------
# Heuristic helpers — best-effort, never authoritative
# ---------------------------------------------------------------------------

def _guess_medicine_name(text: str) -> str:
    """
    Heuristic: take the first line that looks like a medicine name.
    Filters out very short tokens, pure numbers, and common label boilerplate.
    """
    boilerplate = {
        'mfg', 'mfd', 'exp', 'batch', 'lot', 'store', 'keep', 'warning',
        'caution', 'for', 'use', 'only', 'date', 'manufactured', 'marketed',
        'hospital', 'discharge', 'summary', 'rx', 'prescription', 'patient',
    }
    for line in text.splitlines():
        line = line.strip().lstrip('0123456789.-) ')
        if not line or len(line) < 3:
            continue
        first_word = line.split()[0].lower().rstrip(':.,')
        if first_word in boilerplate:
            continue
        # Skip lines that are purely numeric / date-like
        if re.fullmatch(r'[\d/.\-\s]+', line):
            continue
        return line
    return ""


def _extract_strength(text: str) -> str:
    """Return the first strength pattern found (e.g. '500mg')."""
    match = _STRENGTH_RE.search(text)
    return match.group(1).strip() if match else ""


def _extract_dosage(text: str) -> str:
    """Return any line fragment containing dosage-related keywords."""
    fragments = []
    for line in text.splitlines():
        if any(kw in line.lower() for kw in _DOSAGE_KEYWORDS):
            fragments.append(line.strip().lstrip('0123456789.-) '))
    return "; ".join(fragments) if fragments else ""
