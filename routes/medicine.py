import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename

from services.ocr_service import extract_text_from_image
from services.medicine_service import lookup_medicine, is_current_medicine
from services.safety_engine import run_safety_check
from services.ai_service import explain_safety_result, parse_ocr_text_with_ai
from dataclasses import asdict

medicine_bp = Blueprint('medicine', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@medicine_bp.route('/check', methods=['GET'])
def check():
    ocr_prefill = session.pop('ocr_prefill', None)
    return render_template('medicine_check.html', ocr=ocr_prefill)


@medicine_bp.route('/upload-scan', methods=['POST'])
def upload_scan():
    """Accept a medicine image, run OCR, redirect back to form with pre-filled fields."""
    file = request.files.get('medicine_image')
    if not file or not file.filename:
        flash('Please select an image to scan.', 'warning')
        return redirect(url_for('medicine.check'))

    if not _allowed_file(file.filename):
        flash('Invalid image format. Please upload PNG, JPG, or WebP.', 'danger')
        return redirect(url_for('medicine.check'))

    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    saved_filename = f"{uuid.uuid4().hex}.{ext}"
    saved_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(saved_path)

    ocr_result = extract_text_from_image(saved_path)

    # Try AI-assisted OCR parsing to recover structured fields from messy text
    ai_parsed = {}
    if ocr_result.raw_text:
        ai_parsed = parse_ocr_text_with_ai(ocr_result.raw_text)

    session['ocr_prefill'] = {
        # Prefer AI-parsed fields if they are non-empty, fall back to regex extraction
        'medicine_name': ai_parsed.get('medicine_name') or ocr_result.medicine_name,
        'strength':      ai_parsed.get('strength')      or ocr_result.strength,
        'dosage_info':   ai_parsed.get('dosage')        or ocr_result.dosage_info,
        'raw_text':      ocr_result.raw_text,
        'confidence':    round(ocr_result.confidence, 1),
        'is_low_confidence': ocr_result.is_low_confidence,
        'warnings':      ocr_result.warnings,
        'image_filename': saved_filename,
        'ai_ocr_used':   bool(ai_parsed.get('medicine_name')),
    }

    if ocr_result.warnings:
        for w in ocr_result.warnings:
            flash(w, 'warning')
    elif ocr_result.raw_text:
        flash('Text extracted. Please review the details below before continuing.', 'info')

    return redirect(url_for('medicine.check'))


@medicine_bp.route('/check', methods=['POST'])
def check_submit():
    """User has reviewed/corrected fields — run full safety analysis."""
    medicine_name = request.form.get('medicine_name', '').strip()
    strength      = request.form.get('strength', '').strip()
    reason        = request.form.get('reason', '')
    image_filename = request.form.get('image_filename', '')
    ocr_confidence = request.form.get('ocr_confidence')

    if not medicine_name:
        flash('Please enter or confirm the medicine name.', 'warning')
        return redirect(url_for('medicine.check'))

    # --- Medicine lookup ---
    lookup = lookup_medicine(medicine_name)

    # --- Parse saved discharge prescription ---
    current_rx = session.get('prescription_text', '')
    current_medications = [
        line.strip().lstrip('0123456789.-) ')
        for line in current_rx.splitlines()
        if line.strip()
    ] if current_rx else []

    # --- Run safety engine ---
    ocr_conf = float(ocr_confidence) if ocr_confidence else None
    safety_result = run_safety_check(
        medicine_name=medicine_name,
        strength=strength,
        patient_reason=reason,
        current_medications=current_medications,
        ocr_confidence=ocr_conf,
    )

    rx_comparison = is_current_medicine(medicine_name, current_medications)

    # --- AI explanation layer (optional — graceful fallback if unavailable) ---
    ai_explanation = explain_safety_result(
        medicine=safety_result.medicine,
        status=safety_result.status,
        reason=safety_result.reason,
        evidence=safety_result.evidence,
        recommended_next_step=safety_result.recommended_next_step,
        current_medicines=current_medications,
    )

    session['medicine_check'] = {
        'medicine_name':   medicine_name,
        'strength':        strength,
        'reason':          reason,
        'image_filename':  image_filename or None,
        'lookup':          lookup,
        'rx_comparison':   rx_comparison,
        'has_prescription': bool(current_rx),
        'safety':          asdict(safety_result),
        'ai_explanation':  ai_explanation,   # {explanation, ai_used, error}
    }

    return redirect(url_for('medicine.result'))


@medicine_bp.route('/result', methods=['GET'])
def result():
    check_data = session.get('medicine_check')
    if not check_data:
        flash('No medicine check data found. Please submit the form first.', 'info')
        return redirect(url_for('medicine.check'))
    return render_template('result.html', check_data=check_data)
