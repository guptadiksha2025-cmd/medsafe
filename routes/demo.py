"""
MedSafe Demo Mode Route
=======================
Executes the four core demo scenarios using the exact same backend
services, dataset lookup, and Safety Decision Engine.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, session
from dataclasses import asdict

from services.medicine_service import lookup_medicine, is_current_medicine
from services.safety_engine import run_safety_check
from services.ai_service import explain_safety_result

demo_bp = Blueprint('demo', __name__)

DEMO_SCENARIOS = {
    '1': {
        'id': '1',
        'title': 'Current Plan Match',
        'badge': 'GREEN',
        'badge_class': 'success',
        'prescription_text': "1. Amoxicillin 500mg — 1 capsule 3 times daily\n2. Pantoprazole 40mg — 1 tablet before breakfast",
        'prescription_items': [
            {'name': 'Amoxicillin', 'strength': '500 mg', 'dosage': '1 capsule 3 times daily'},
            {'name': 'Pantoprazole', 'strength': '40 mg', 'dosage': '1 tablet before breakfast'}
        ],
        'old_medicine': 'Amoxicillin',
        'strength': '500 mg',
        'reason': 'It was prescribed to me before',
        'description': 'The patient finds an older bottle of Amoxicillin 500mg at home. It matches an active item on their current discharge prescription.',
        'expected_outcome': 'GREEN: Current Plan Match — Verified as present in current plan.'
    },
    '2': {
        'id': '2',
        'title': 'Old Medicine — Not in Plan',
        'badge': 'YELLOW',
        'badge_class': 'warning',
        'prescription_text': "1. Amoxicillin 500mg — 1 capsule 3 times daily\n2. Pantoprazole 40mg — 1 tablet before breakfast",
        'prescription_items': [
            {'name': 'Amoxicillin', 'strength': '500 mg', 'dosage': '1 capsule 3 times daily'},
            {'name': 'Pantoprazole', 'strength': '40 mg', 'dosage': '1 tablet before breakfast'}
        ],
        'old_medicine': 'Metformin',
        'strength': '500 mg',
        'reason': 'I have similar symptoms again',
        'description': 'The patient finds old Metformin tablets from a previous illness. It is identified in the demo database, but is NOT part of the new discharge plan.',
        'expected_outcome': 'YELLOW: Verify Before Taking — Identified medicine, but not in current plan.'
    },
    '3': {
        'id': '3',
        'title': 'Potential Duplicate / Overlap',
        'badge': 'RED',
        'badge_class': 'danger',
        'prescription_text': "1. Amoxicillin 500mg — 1 capsule 3 times daily\n2. Pantoprazole 40mg — 1 tablet before breakfast",
        'prescription_items': [
            {'name': 'Amoxicillin', 'strength': '500 mg', 'dosage': '1 capsule 3 times daily'},
            {'name': 'Pantoprazole', 'strength': '40 mg', 'dosage': '1 tablet before breakfast'}
        ],
        'old_medicine': 'Augmentin',
        'strength': '625 mg',
        'reason': 'It was prescribed to me before',
        'description': 'The patient finds Augmentin (Co-Amoxiclav) at home. Both Augmentin and the prescribed Amoxicillin share the same active ingredient (Amoxicillin), presenting a duplicate dose risk.',
        'expected_outcome': 'RED: Professional Review Required — Active ingredient overlap detected.'
    },
    '4': {
        'id': '4',
        'title': 'Unknown Medicine',
        'badge': 'GRAY',
        'badge_class': 'secondary',
        'prescription_text': "1. Amoxicillin 500mg — 1 capsule 3 times daily\n2. Pantoprazole 40mg — 1 tablet before breakfast",
        'prescription_items': [
            {'name': 'Amoxicillin', 'strength': '500 mg', 'dosage': '1 capsule 3 times daily'},
            {'name': 'Pantoprazole', 'strength': '40 mg', 'dosage': '1 tablet before breakfast'}
        ],
        'old_medicine': 'CardioPlus',
        'strength': '25 mg',
        'reason': "I don't remember why I have it",
        'description': 'The patient finds an unidentifiable old tablet strip. The system cannot identify it in the database and never guesses medical safety.',
        'expected_outcome': 'GRAY: Unable to Verify — Insufficient information, manual verification required.'
    }
}


@demo_bp.route('/', methods=['GET'])
def index():
    return render_template('demo.html', scenarios=DEMO_SCENARIOS)


@demo_bp.route('/run/<scenario_id>', methods=['POST', 'GET'])
def run(scenario_id):
    scenario = DEMO_SCENARIOS.get(str(scenario_id))
    if not scenario:
        flash("Invalid demo scenario selected.", "warning")
        return redirect(url_for('demo.index'))

    # Load the scenario's prescription into the user's session
    session['prescription_text'] = scenario['prescription_text']

    current_medications = [
        item['name'] + ' ' + item['strength']
        for item in scenario['prescription_items']
    ]

    medicine_name = scenario['old_medicine']
    strength = scenario['strength']
    reason = scenario['reason']

    # Execute the REAL Safety Decision Engine and Services
    lookup = lookup_medicine(medicine_name)
    safety_result = run_safety_check(
        medicine_name=medicine_name,
        strength=strength,
        patient_reason=reason,
        current_medications=current_medications,
        ocr_confidence=None,
    )
    rx_comparison = is_current_medicine(medicine_name, current_medications)

    ai_explanation = explain_safety_result(
        medicine=safety_result.medicine,
        status=safety_result.status,
        reason=safety_result.reason,
        evidence=safety_result.evidence,
        recommended_next_step=safety_result.recommended_next_step,
        current_medicines=current_medications,
    )

    session['medicine_check'] = {
        'medicine_name': medicine_name,
        'strength': strength,
        'reason': reason,
        'image_filename': None,
        'lookup': lookup,
        'rx_comparison': rx_comparison,
        'has_prescription': True,
        'safety': asdict(safety_result),
        'ai_explanation': ai_explanation,
        'is_demo': True,
        'demo_title': scenario['title']
    }

    return redirect(url_for('medicine.result'))
