// MedSafe — Client-side JavaScript & Interactive Enhancements

document.addEventListener('DOMContentLoaded', () => {

    // ── 1. Generic Drag & Drop and Preview Setup ──────────────────────
    function setupDropZone(inputId, dropZoneId, previewContainerId, previewImgId, filenameSpanId, clearBtnId, pdfBadgeId) {
        const fileInput = document.getElementById(inputId);
        const dropZone = document.getElementById(dropZoneId);
        const container = document.getElementById(previewContainerId);
        const img = document.getElementById(previewImgId);
        const filenameSpan = document.getElementById(filenameSpanId);
        const clearBtn = document.getElementById(clearBtnId);
        const pdfBadge = document.getElementById(pdfBadgeId);

        if (!fileInput || !dropZone) return;

        function handleFile(file) {
            if (!file) return;
            filenameSpan && (filenameSpan.textContent = file.name);

            const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

            if (isPdf) {
                if (img) img.classList.add('d-none');
                if (pdfBadge) pdfBadge.classList.remove('d-none');
                if (container) container.classList.remove('d-none');
            } else if (file.type.startsWith('image/')) {
                if (pdfBadge) pdfBadge.classList.add('d-none');
                const reader = new FileReader();
                reader.onload = (e) => {
                    if (img) {
                        img.src = e.target.result;
                        img.classList.remove('d-none');
                    }
                    if (container) container.classList.remove('d-none');
                };
                reader.readAsDataURL(file);
            } else {
                if (pdfBadge) pdfBadge.classList.remove('d-none');
                if (img) img.classList.add('d-none');
                if (container) container.classList.remove('d-none');
            }
        }

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFile(fileInput.files[0]);
            }
        });

        // Drag & Drop events
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                fileInput.files = dt.files;
                handleFile(dt.files[0]);
            }
        }, false);

        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                fileInput.value = '';
                if (img) { img.src = ''; img.classList.add('d-none'); }
                if (pdfBadge) pdfBadge.classList.add('d-none');
                if (filenameSpan) filenameSpan.textContent = '';
                if (container) container.classList.add('d-none');
            });
        }
    }

    // Initialize dropzones
    setupDropZone('prescription_image', 'rx-drop-zone', 'rx-image-preview', 'rx-preview-img', 'rx-filename', 'rx-clear-image', 'rx-pdf-badge');
    setupDropZone('medicine_image', 'med-drop-zone', 'image-preview', 'preview-img', 'med-filename', 'clear-image', 'med-pdf-badge');

    // ── 2. Scan Button Loading Feedback ───────────────────────────────
    const rxForm = document.getElementById('rx-upload-form');
    const rxScanBtn = document.getElementById('rx-scan-btn');
    const rxOcrStatus = document.getElementById('rx-ocr-status');

    if (rxForm && rxScanBtn) {
        rxForm.addEventListener('submit', () => {
            rxScanBtn.disabled = true;
            rxScanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Scanning...';
            if (rxOcrStatus) rxOcrStatus.classList.remove('d-none');
        });
    }

    const medScanForm = document.getElementById('med-scan-form');
    const medScanBtn = document.getElementById('med-scan-btn');
    const medOcrStatus = document.getElementById('med-ocr-status');

    if (medScanForm && medScanBtn) {
        medScanForm.addEventListener('submit', () => {
            medScanBtn.disabled = true;
            medScanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Scanning...';
            if (medOcrStatus) medOcrStatus.classList.remove('d-none');
        });
    }

    // ── 3. Processing Modal & Step Animation (Step 5 Requirement) ─────
    const checkForm = document.getElementById('medicine-check-form');
    const processingModalEl = document.getElementById('processingModal');

    if (checkForm && processingModalEl) {
        checkForm.addEventListener('submit', (e) => {
            const medInput = document.getElementById('medicine_name');
            if (medInput && !medInput.value.trim()) {
                return; // Let native HTML validation handle empty input
            }

            // Show processing modal
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const modal = new bootstrap.Modal(processingModalEl);
                modal.show();

                // Subtle step progression
                const stepIds = ['step-reading', 'step-identifying', 'step-comparing', 'step-safety', 'step-preparing'];
                stepIds.forEach((id, index) => {
                    setTimeout(() => {
                        const el = document.getElementById(id);
                        if (el) {
                            el.classList.add('active');
                            const icon = el.querySelector('i');
                            if (icon) {
                                icon.className = 'bi bi-check-circle-fill text-primary';
                            }
                        }
                    }, index * 250);
                });
            }
        });
    }

    // ── 4. Prescription Quick Add Helper ──────────────────────────────
    const quickAddBtn = document.getElementById('quick-add-btn');
    const quickName = document.getElementById('quick-med-name');
    const quickStrength = document.getElementById('quick-med-strength');
    const rxTextarea = document.getElementById('prescription_text');

    if (quickAddBtn && quickName && rxTextarea) {
        quickAddBtn.addEventListener('click', () => {
            const name = quickName.value.trim();
            const strength = quickStrength ? quickStrength.value.trim() : '';

            if (!name) return;

            const entry = strength ? `${name} ${strength}` : name;
            if (rxTextarea.value.trim() === '') {
                rxTextarea.value = entry;
            } else {
                rxTextarea.value = rxTextarea.value.trim() + '\n' + entry;
            }

            quickName.value = '';
            if (quickStrength) quickStrength.value = '';
            quickName.focus();
        });
    }
});
