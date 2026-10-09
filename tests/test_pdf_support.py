"""
MedSafe PDF Support Test Suite
==============================
Tests PDF text extraction (digital text & scanned PDF OCR) and
Flask upload route handling for PDF discharge summaries.
Usage:
    python -X utf8 tests/test_pdf_support.py
"""

import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf
from services.ocr_service import extract_prescription_text, extract_text_from_file, _extract_from_pdf
from app import create_app

PASS = "[PASS]"
FAIL = "[FAIL]"

def test(description, condition):
    status = PASS if condition else FAIL
    print(f"  {status} {description}")
    return condition

results = []

print("\n" + "="*60)
print("PDF DOCUMENT EXTRACTION TESTS")
print("="*60)

# 1. Create a synthetic test PDF
test_pdf_path = os.path.join(os.path.dirname(__file__), "test_discharge.pdf")
doc = pymupdf.open()
page = doc.new_page()
page.insert_text((50, 72), "Hospital Discharge Summary\nPatient Discharge Medications:\n1. Amoxicillin 500mg - 1 capsule 3 times daily\n2. Pantoprazole 40mg - 1 tablet before breakfast")
doc.save(test_pdf_path)
doc.close()

results.append(test("Test PDF created successfully", os.path.isfile(test_pdf_path)))

# 2. Test extract_prescription_text on PDF
rx_res = extract_prescription_text(test_pdf_path)
results.append(test("extract_prescription_text extracts text from PDF", bool(rx_res.raw_text)))
results.append(test("Prescription text contains 'Amoxicillin 500mg'", "Amoxicillin 500mg" in rx_res.raw_text))
results.append(test("Prescription text contains 'Pantoprazole 40mg'", "Pantoprazole 40mg" in rx_res.raw_text))
results.append(test("PDF marked as high confidence for digital text", rx_res.confidence >= 90.0))
results.append(test("Result marked as is_pdf = True", rx_res.is_pdf is True))

# 3. Test extract_text_from_file on single-medicine PDF
med_pdf_path = os.path.join(os.path.dirname(__file__), "test_medicine.pdf")
doc_med = pymupdf.open()
page_med = doc_med.new_page()
page_med.insert_text((50, 72), "Metformin Hydrochloride 500mg Tablets\nTake 1 tablet twice daily with meals")
doc_med.save(med_pdf_path)
doc_med.close()

med_res = extract_text_from_file(med_pdf_path)
results.append(test("extract_text_from_file parses medicine name from PDF", "Metformin" in med_res.medicine_name))
results.append(test("extract_text_from_file extracts strength from PDF", "500mg" in med_res.strength or "500" in med_res.strength))

# 4. Test Flask prescription upload endpoint with PDF
print("\n" + "="*60)
print("FLASK ROUTE PDF UPLOAD TESTS")
print("="*60)

flask_app = create_app()
flask_app.config['TESTING'] = True
client = flask_app.test_client()

with open(test_pdf_path, 'rb') as f:
    pdf_bytes = f.read()

resp_upload = client.post(
    '/prescription/upload',
    data={'prescription_image': (io.BytesIO(pdf_bytes), 'discharge_summary.pdf')},
    content_type='multipart/form-data',
    follow_redirects=True
)

results.append(test("POST /prescription/upload accepts PDF file (status 200)", resp_upload.status_code == 200))
results.append(test("Flash message indicates PDF extraction success", b"PDF document" in resp_upload.data or b"extracted" in resp_upload.data))
results.append(test("Extracted prescription text rendered on review form", b"Amoxicillin 500mg" in resp_upload.data))

# 5. Clean up temporary test PDFs
for path in [test_pdf_path, med_pdf_path]:
    if os.path.isfile(path):
        os.remove(path)

# Summary
total = len(results)
passed = sum(results)
failed = total - passed

print("\n" + "="*60)
print(f"TOTAL PDF TESTS: {passed}/{total} PASSED  |  {failed} FAILED")
print("="*60 + "\n")

if failed > 0:
    sys.exit(1)
