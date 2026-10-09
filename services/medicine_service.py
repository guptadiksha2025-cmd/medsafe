"""
MedSafe Medicine Service
========================
Provides lookup, normalization, and comparison functions against the
controlled demo medication dataset (data/medicines.json).

IMPORTANT DISCLAIMER
--------------------
This is a CONTROLLED DEMO DATASET only. It does not represent a complete
or authoritative medical database. A medicine not found here must NEVER be
assumed safe — it must be treated as UNKNOWN and flagged for manual review.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

_DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'medicines.json')
_dataset: Optional[list] = None


def _load_dataset() -> list:
    """Load and cache the medicines JSON dataset."""
    global _dataset
    if _dataset is None:
        with open(_DATASET_PATH, 'r', encoding='utf-8') as f:
            _dataset = json.load(f)
    return _dataset


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize_medicine_name(name: str) -> str:
    """
    Normalise a medicine name string for comparison.
    - Strips whitespace
    - Lowercases
    - Collapses multiple spaces
    - Removes common dosage suffixes for base-name matching
      e.g. 'Amoxicillin 500mg' -> 'amoxicillin 500mg'
    """
    if not name:
        return ''
    name = name.strip().lower()
    name = re.sub(r'\s+', ' ', name)          # collapse spaces
    name = re.sub(r'[^\w\s/.]', '', name)      # remove stray punctuation
    return name


def _norm_set(name: str) -> set:
    """Return a set of normalised tokens from a name — used for fuzzy matching."""
    return set(normalize_medicine_name(name).split())


# ---------------------------------------------------------------------------
# Core lookup
# ---------------------------------------------------------------------------

def find_medicine(name: str) -> list:
    """
    Search the demo dataset for records matching the supplied name.

    Matching strategy (in priority order):
      1. Exact normalised medicine_name match
      2. Exact normalised common_identifier match
      3. Partial token overlap (medicine_name starts with query or vice versa)

    Returns a list of matching records (may have >1 if multiple strengths exist).
    Returns [] if nothing is found — caller must treat this as UNKNOWN.
    """
    if not name:
        return []

    query = normalize_medicine_name(name)
    dataset = _load_dataset()

    exact_name = []
    exact_alias = []
    partial = []

    for record in dataset:
        norm_name = normalize_medicine_name(record['medicine_name'])
        norm_aliases = [normalize_medicine_name(a) for a in record.get('common_identifiers', [])]

        if query == norm_name:
            exact_name.append(record)
        elif query in norm_aliases:
            exact_alias.append(record)
        else:
            # Partial: query starts with medicine name or vice versa (handles "amoxicillin 500mg")
            if query.startswith(norm_name) or norm_name.startswith(query):
                partial.append(record)
            elif any(query.startswith(a) or a.startswith(query) for a in norm_aliases):
                partial.append(record)

    if exact_name:
        return exact_name
    if exact_alias:
        return exact_alias
    return partial


def get_active_ingredient(name: str) -> Optional[str]:
    """
    Return the active ingredient for the best-matching medicine.
    Returns None if the medicine cannot be identified.
    """
    matches = find_medicine(name)
    if matches:
        return matches[0]['active_ingredient']
    return None


# ---------------------------------------------------------------------------
# Comparison utilities
# ---------------------------------------------------------------------------

def compare_medicines(medicine1: str, medicine2: str) -> dict:
    """
    Compare two medicine names.

    Returns a dict with:
      - same_name (bool): normalised names match
      - same_active_ingredient (bool): share the same active ingredient
      - medicine1_record: first DB record found (or None)
      - medicine2_record: second DB record found (or None)
      - note: human-readable explanation
    """
    records1 = find_medicine(medicine1)
    records2 = find_medicine(medicine2)

    rec1 = records1[0] if records1 else None
    rec2 = records2[0] if records2 else None

    norm1 = normalize_medicine_name(medicine1)
    norm2 = normalize_medicine_name(medicine2)
    same_name = norm1 == norm2

    same_ingredient = False
    note = ''

    if rec1 and rec2:
        same_ingredient = (
            rec1['active_ingredient'].lower() == rec2['active_ingredient'].lower()
        )
        if same_name:
            note = 'Both names refer to the same medicine.'
        elif same_ingredient:
            note = (
                f"'{medicine1}' and '{medicine2}' contain the same active ingredient "
                f"({rec1['active_ingredient']}). A professional should verify whether "
                f"taking both is appropriate."
            )
        else:
            note = 'These medicines appear to have different active ingredients.'
    elif not rec1 and not rec2:
        note = 'Neither medicine could be identified in the demo dataset.'
    elif not rec1:
        note = f"'{medicine1}' could not be identified in the demo dataset."
    else:
        note = f"'{medicine2}' could not be identified in the demo dataset."

    return {
        'same_name': same_name,
        'same_active_ingredient': same_ingredient,
        'medicine1_record': rec1,
        'medicine2_record': rec2,
        'note': note,
    }


# ---------------------------------------------------------------------------
# Prescription matching
# ---------------------------------------------------------------------------

def is_current_medicine(name: str, current_medications: list) -> dict:
    """
    Check whether a medicine (or its active ingredient) appears in the
    patient's current discharge medication list.

    Parameters
    ----------
    name : str
        The old medicine name to check.
    current_medications : list of str
        List of medicine names from the discharge prescription.

    Returns a dict with:
      - found_exact (bool): exact or alias match in current plan
      - found_same_ingredient (bool): active ingredient overlap
      - matched_current_medicine (str | None): which current medicine matched
      - old_medicine_record: DB record for the old medicine (or None)
      - in_dataset (bool): whether the old medicine exists in demo dataset
    """
    old_records = find_medicine(name)
    old_rec = old_records[0] if old_records else None
    old_ingredient = old_rec['active_ingredient'].lower() if old_rec else None

    found_exact = False
    found_ingredient = False
    matched_name = None

    for current_name in current_medications:
        # Check exact / alias match via normalised string
        current_records = find_medicine(current_name)
        current_norm = normalize_medicine_name(current_name)
        old_norm = normalize_medicine_name(name)

        if current_norm == old_norm:
            found_exact = True
            matched_name = current_name
            break

        # Also check via DB: if both resolve to the same medicine_name it's a match
        if current_records and old_records:
            if (normalize_medicine_name(current_records[0]['medicine_name']) ==
                    normalize_medicine_name(old_records[0]['medicine_name'])):
                found_exact = True
                matched_name = current_name
                break

        # Check via common identifiers in DB
        if old_records and current_records:
            curr_rec = current_records[0]
            if curr_rec['active_ingredient'].lower() == old_ingredient:
                found_ingredient = True
                matched_name = current_name
                # Don't break — keep looking for an exact match

    return {
        'found_exact': found_exact,
        'found_same_ingredient': found_ingredient,
        'matched_current_medicine': matched_name,
        'old_medicine_record': old_rec,
        'in_dataset': old_rec is not None,
    }


# ---------------------------------------------------------------------------
# High-level lookup for the route layer
# ---------------------------------------------------------------------------

def lookup_medicine(name: str) -> dict:
    """
    Single entry-point called by the Flask route after the user confirms
    the medicine name (post OCR review).

    Returns a structured result dict ready for template rendering.
    """
    matches = find_medicine(name)

    if not matches:
        return {
            'identified': False,
            'medicine_name': name,
            'active_ingredient': None,
            'strength': None,
            'dosage_form': None,
            'category': None,
            'all_matches': [],
            'message': 'Unable to confidently identify this medicine. '
                       'Please verify the details manually or consult a pharmacist.',
        }

    best = matches[0]
    return {
        'identified': True,
        'medicine_name': best['medicine_name'],
        'active_ingredient': best['active_ingredient'],
        'strength': best['strength'],
        'dosage_form': best['dosage_form'],
        'category': best['category'],
        'all_matches': matches,   # may include other strengths
        'message': None,
    }
