"""
MedSafe — Medicine Service Test Suite
======================================
Tests for services/medicine_service.py against the demo dataset.
Run with:  python tests/test_medicine_service.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.medicine_service import (
    normalize_medicine_name,
    find_medicine,
    get_active_ingredient,
    compare_medicines,
    is_current_medicine,
    lookup_medicine,
)

PASS = "[PASS]"
FAIL = "[FAIL]"

def test(description, condition):
    status = PASS if condition else FAIL
    print(f"  {status} {description}")
    return condition

results = []

print("\n--- Normalisation ---")
results.append(test("Strips whitespace",          normalize_medicine_name("  Amoxicillin  ") == "amoxicillin"))
results.append(test("Lowercases input",           normalize_medicine_name("PARACETAMOL") == "paracetamol"))
results.append(test("Collapses spaces",           normalize_medicine_name("Amoxicillin  500mg") == "amoxicillin 500mg"))
results.append(test("Handles empty string",       normalize_medicine_name("") == ""))

print("\n--- Exact medicine name match ---")
matches = find_medicine("Amoxicillin")
results.append(test("Finds Amoxicillin",          len(matches) > 0))
results.append(test("Correct category",           any(m['category'] == 'Antibiotic' for m in matches)))

print("\n--- Case-insensitive match ---")
results.append(test("Lowercase name",             len(find_medicine("amoxicillin")) > 0))
results.append(test("Uppercase name",             len(find_medicine("PARACETAMOL")) > 0))
results.append(test("Mixed case",                 len(find_medicine("pAnToPrAzOlE")) > 0))

print("\n--- Alias / common identifier match ---")
results.append(test("Brand name 'Augmentin'",     len(find_medicine("Augmentin")) > 0))
results.append(test("Brand name 'Brufen'",        len(find_medicine("Brufen")) > 0))
results.append(test("Brand name 'Dolo 650'",      len(find_medicine("Dolo 650")) > 0))
results.append(test("Brand name 'Glucophage'",    len(find_medicine("Glucophage")) > 0))

print("\n--- Active ingredient retrieval ---")
results.append(test("Amoxicillin ingredient",     get_active_ingredient("Amoxicillin") == "Amoxicillin"))
results.append(test("Augmentin ingredient",       get_active_ingredient("Augmentin") == "Amoxicillin"))
results.append(test("Unknown returns None",       get_active_ingredient("UnknownXYZ123") is None))

print("\n--- Same active ingredient comparison ---")
comp = compare_medicines("Amoxicillin", "Augmentin")
results.append(test("Amoxicillin vs Augmentin — same ingredient", comp['same_active_ingredient'] is True))
results.append(test("Amoxicillin vs Augmentin — not same name",   comp['same_name'] is False))
results.append(test("Note mentions active ingredient",             "active ingredient" in comp['note']))

comp2 = compare_medicines("Amoxicillin", "Metformin")
results.append(test("Amoxicillin vs Metformin — different ingredient", comp2['same_active_ingredient'] is False))

print("\n--- Unknown medicine ---")
unknown = lookup_medicine("DragonRoot 200mg")
results.append(test("Unknown not identified",      unknown['identified'] is False))
results.append(test("Returns guidance message",    "Unable to confidently identify" in unknown['message']))
results.append(test("No ingredient returned",      unknown['active_ingredient'] is None))

print("\n--- is_current_medicine: medicine IS in prescription ---")
current_rx = ["Amoxicillin 500mg", "Pantoprazole 40mg"]
result_a = is_current_medicine("Amoxicillin", current_rx)
results.append(test("Exact match found",           result_a['found_exact'] is True))
results.append(test("Matched medicine identified", result_a['matched_current_medicine'] is not None))

print("\n--- is_current_medicine: same active ingredient ---")
result_b = is_current_medicine("Augmentin", ["Amoxicillin 500mg"])
results.append(test("Same ingredient flagged",     result_b['found_same_ingredient'] is True))
results.append(test("Not marked as exact match",   result_b['found_exact'] is False))

print("\n--- is_current_medicine: NOT in current prescription ---")
result_c = is_current_medicine("Metformin", ["Amoxicillin 500mg", "Pantoprazole 40mg"])
results.append(test("Not found in prescription",   result_c['found_exact'] is False))
results.append(test("No ingredient overlap",       result_c['found_same_ingredient'] is False))
results.append(test("Medicine is in dataset",      result_c['in_dataset'] is True))

print("\n--- is_current_medicine: completely unknown medicine ---")
result_d = is_current_medicine("DragonRoot 200mg", ["Amoxicillin 500mg"])
results.append(test("Not found in prescription",   result_d['found_exact'] is False))
results.append(test("Not in dataset",              result_d['in_dataset'] is False))

print("\n--- lookup_medicine: identified ---")
lk = lookup_medicine("Paracetamol")
results.append(test("Identified True",             lk['identified'] is True))
results.append(test("Name correct",                lk['medicine_name'] == "Paracetamol"))
results.append(test("Ingredient correct",          lk['active_ingredient'] == "Paracetamol"))

# Summary
total  = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*45}")
print(f"  Results: {passed}/{total} passed  |  {failed} failed")
print(f"{'='*45}\n")
if failed:
    sys.exit(1)
