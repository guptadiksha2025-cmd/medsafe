"""
MedSafe Comprehensive Test Suite
=================================
Runs all automated unit, integration, and scenario tests.
Usage:
    python -X utf8 tests/test_all.py
"""

import sys
import os

# Set path to root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.medicine_service import (
    normalize_medicine_name,
    find_medicine,
    get_active_ingredient,
    compare_medicines,
    is_current_medicine,
    lookup_medicine
)
from services.safety_engine import (
    run_safety_check,
    STATUS_GREEN,
    STATUS_YELLOW,
    STATUS_RED,
    STATUS_GRAY
)
from services.ai_service import (
    explain_safety_result,
    parse_ocr_text_with_ai,
    _deterministic_explanation
)
from app import create_app

PASS = "[PASS]"
FAIL = "[FAIL]"

def test(description, condition):
    status = PASS if condition else FAIL
    print(f"  {status} {description}")
    return condition

all_results = []

print("\n" + "="*60)
print("1. MEDICINE NORMALIZATION & MATCHING TESTS")
print("="*60)

all_results.append(test("Normalization - lowercases & strips spaces", normalize_medicine_name("  AmOxIcIlLiN  500  ") == "amoxicillin 500"))
all_results.append(test("Exact match - Amoxicillin found in DB", len(find_medicine("Amoxicillin")) > 0))
all_results.append(test("Case-insensitive match - PARACETAMOL found", len(find_medicine("PARACETAMOL")) > 0))
all_results.append(test("Brand name alias match - Augmentin resolves", len(find_medicine("Augmentin")) > 0))
all_results.append(test("Brand name alias match - Dolo 650 resolves", len(find_medicine("Dolo 650")) > 0))
all_results.append(test("Active ingredient lookup - Augmentin has Amoxicillin", get_active_ingredient("Augmentin") == "Amoxicillin"))
all_results.append(test("Same active ingredient comparison - Amoxicillin vs Augmentin", compare_medicines("Amoxicillin", "Augmentin")['same_active_ingredient'] is True))
all_results.append(test("Different active ingredient comparison - Amoxicillin vs Metformin", compare_medicines("Amoxicillin", "Metformin")['same_active_ingredient'] is False))
all_results.append(test("Unknown medicine handling - CardioX100 returns unidentified", lookup_medicine("CardioX100")['identified'] is False))

print("\n" + "="*60)
print("2. SAFETY DECISION ENGINE — FOUR STATUS SCENARIOS")
print("="*60)

# SCENARIO 1: GREEN — Current Plan Match
res_green = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500 mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg", "Pantoprazole 40mg"]
)
all_results.append(test("Scenario 1: GREEN status for current prescription match", res_green.status == STATUS_GREEN))
all_results.append(test("Scenario 1: Confidence is High (> 0.8)", res_green.confidence >= 0.8))
all_results.append(test("Scenario 1: Safety rule language strictly preserved", "safe to take" not in res_green.reason.lower()))

# SCENARIO 2: YELLOW — Old Medicine Not in Current Plan
res_yellow = run_safety_check(
    medicine_name="Metformin",
    strength="500 mg",
    patient_reason="I have similar symptoms again",
    current_medications=["Amoxicillin 500mg", "Pantoprazole 40mg"]
)
all_results.append(test("Scenario 2: YELLOW status for old medicine not in current plan", res_yellow.status == STATUS_YELLOW))
all_results.append(test("Scenario 2: Recommends professional verification before taking", "doctor" in res_yellow.recommended_next_step.lower() or "pharmacist" in res_yellow.recommended_next_step.lower()))

# SCENARIO 3: RED — Potential Duplicate / Active Ingredient Overlap
res_red = run_safety_check(
    medicine_name="Augmentin",
    strength="625 mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg", "Pantoprazole 40mg"]
)
all_results.append(test("Scenario 3: RED status for duplicate active ingredient risk", res_red.status == STATUS_RED))
all_results.append(test("Scenario 3: Evidence identifies shared active ingredient", "amoxicillin" in res_red.evidence.lower()))

# SCENARIO 4: GRAY — Unknown Medicine
res_gray = run_safety_check(
    medicine_name="CardioPlus",
    strength="25 mg",
    patient_reason="I don't remember why I have it",
    current_medications=["Amoxicillin 500mg"]
)
all_results.append(test("Scenario 4: GRAY status for unidentifiable medicine", res_gray.status == STATUS_GRAY))
all_results.append(test("Scenario 4: Confidence is 0.0 (Low)", res_gray.confidence == 0.0))

print("\n" + "="*60)
print("3. AI SERVICE & DETERMINISTIC FALLBACK")
print("="*60)

exp_green = explain_safety_result(
    medicine="Amoxicillin 500mg",
    status="GREEN",
    reason="Matches current medication plan.",
    evidence="Found in prescription.",
    recommended_next_step="Confirm dosage."
)
all_results.append(test("AI service returns structured explanation dict", isinstance(exp_green, dict) and "explanation" in exp_green))
all_results.append(test("AI service fallback works without API key", exp_green['ai_used'] is False or bool(exp_green['explanation'])))

# Deterministic safety wording
for st in ["GREEN", "YELLOW", "RED", "GRAY"]:
    dt_exp = _deterministic_explanation(st, "Reason description.", "Next steps.")
    all_results.append(test(f"Deterministic text for {st} does not claim '100% safe'", "100% safe" not in dt_exp.lower()))

print("\n" + "="*60)
print("4. FLASK APPLICATION & ROUTE INTEGRITY")
print("="*60)

flask_app = create_app()
flask_app.config['TESTING'] = True
client = flask_app.test_client()

resp_home = client.get('/')
all_results.append(test("GET / -> 200 OK (Landing page)", resp_home.status_code == 200))

resp_rx = client.get('/prescription/')
all_results.append(test("GET /prescription/ -> 200 OK (Prescription upload)", resp_rx.status_code == 200))

resp_med = client.get('/medicine/check')
all_results.append(test("GET /medicine/check -> 200 OK (Medicine check)", resp_med.status_code == 200))

resp_demo = client.get('/demo/')
all_results.append(test("GET /demo/ -> 200 OK (Demo mode selector)", resp_demo.status_code == 200))

resp_demo_run = client.get('/demo/run/1', follow_redirects=True)
all_results.append(test("GET /demo/run/1 -> Follows redirect to /medicine/result with GREEN status", resp_demo_run.status_code == 200 and b"CURRENT PLAN MATCH" in resp_demo_run.data))

resp_404 = client.get('/nonexistent-page')
all_results.append(test("GET /nonexistent-page -> 404 with friendly error page", resp_404.status_code == 404 and b"Page Not Found" in resp_404.data))

print("\n" + "="*60)
print("5. PDF DOCUMENT EXTRACTION & UPLOAD TESTS")
print("="*60)

import io
import pymupdf
from services.ocr_service import extract_prescription_text, extract_text_from_file

# Create synthetic discharge PDF
test_pdf_path = os.path.join(os.path.dirname(__file__), "test_discharge_suite.pdf")
doc_test = pymupdf.open()
p_test = doc_test.new_page()
p_test.insert_text((50, 72), "Hospital Discharge Summary\nPatient Medications:\n1. Amoxicillin 500mg - 1 capsule 3 times daily\n2. Pantoprazole 40mg - 1 tablet before breakfast")
doc_test.save(test_pdf_path)
doc_test.close()

rx_pdf_res = extract_prescription_text(test_pdf_path)
all_results.append(test("PDF extraction - reads text from discharge summary PDF", bool(rx_pdf_res.raw_text)))
all_results.append(test("PDF extraction - contains 'Amoxicillin 500mg'", "Amoxicillin 500mg" in rx_pdf_res.raw_text))
all_results.append(test("PDF extraction - contains 'Pantoprazole 40mg'", "Pantoprazole 40mg" in rx_pdf_res.raw_text))
all_results.append(test("PDF extraction - high confidence for digital PDF text", rx_pdf_res.confidence >= 90.0))

with open(test_pdf_path, 'rb') as f_pdf:
    pdf_upload_bytes = f_pdf.read()

resp_pdf_post = client.post(
    '/prescription/upload',
    data={'prescription_image': (io.BytesIO(pdf_upload_bytes), 'discharge_summary.pdf')},
    content_type='multipart/form-data',
    follow_redirects=True
)
all_results.append(test("POST /prescription/upload accepts PDF document (status 200)", resp_pdf_post.status_code == 200))
all_results.append(test("PDF upload - extracted text rendered on confirmation form", b"Amoxicillin 500mg" in resp_pdf_post.data))

if os.path.isfile(test_pdf_path):
    os.remove(test_pdf_path)

# Final Summary
total = len(all_results)
passed = sum(all_results)
failed = total - passed

print("\n" + "="*60)
print(f"TOTAL TEST RESULTS: {passed}/{total} PASSED  |  {failed} FAILED")
print("="*60 + "\n")

if failed > 0:
    sys.exit(1)

