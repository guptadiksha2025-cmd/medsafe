import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename

from services.ocr_service import extract_prescription_text

prescription_bp = Blueprint('prescription', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@prescription_bp.route('/', methods=['GET'])
def index():
    ocr_data = session.pop('prescription_ocr', None)
    saved_text = session.get('prescription_text', '')
    return render_template('prescription.html', ocr=ocr_data, saved_text=saved_text)


@prescription_bp.route('/upload', methods=['POST'])
def upload():
    """Upload a prescription image or PDF document, extract text, and show for patient review."""
    file = request.files.get('prescription_image')
    if not file or not file.filename:
        flash('Please select a prescription image or PDF file to upload.', 'warning')
        return redirect(url_for('prescription.index'))

    if not _allowed_file(file.filename):
        flash('Invalid document format. Please upload PDF, PNG, JPG, or WebP.', 'danger')
        return redirect(url_for('prescription.index'))

    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    saved_filename = f"{uuid.uuid4().hex}.{ext}"
    saved_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(saved_path)

    ocr_result = extract_prescription_text(saved_path)

    session['prescription_ocr'] = {
        'raw_text': ocr_result.raw_text,
        'confidence': round(ocr_result.confidence, 1),
        'is_low_confidence': ocr_result.is_low_confidence,
        'is_pdf': ocr_result.is_pdf,
        'warnings': ocr_result.warnings,
        'image_filename': saved_filename,
    }

    if ocr_result.warnings:
        for w in ocr_result.warnings:
            flash(w, 'warning')
    elif ocr_result.raw_text:
        doc_type = "PDF document" if ext == "pdf" else "image"
        flash(f'Prescription text extracted from {doc_type}. Please review and correct if needed.', 'info')

    return redirect(url_for('prescription.index'))


@prescription_bp.route('/save', methods=['POST'])
def save():
    """Save the user-reviewed prescription text."""
    prescription_text = request.form.get('prescription_text', '').strip()
    if not prescription_text:
        flash('Please enter or confirm your prescription text.', 'warning')
        return redirect(url_for('prescription.index'))

    session['prescription_text'] = prescription_text
    flash('Prescription saved successfully.', 'success')
    return redirect(url_for('prescription.index'))
