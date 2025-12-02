const fileInput = document.getElementById('file-input');
const dropArea = document.getElementById('drop-area');
const previewContainer = document.getElementById('preview-container');
const imagePreview = document.getElementById('image-preview');
const extractBtn = document.getElementById('extract-btn');
const resultsSection = document.getElementById('results-section');
const rawText = document.getElementById('raw-text');
const verifyBtn = document.getElementById('verify-btn');
const verificationContainer = document.getElementById('verification-container');
const verificationResults = document.getElementById('verification-results');

let selectedFile = null;

// Drag and drop events
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

dropArea.addEventListener('drop', handleDrop, false);
fileInput.addEventListener('change', handleFiles, false);

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles({ target: { files: files } });
}

function handleFiles(e) {
    const files = e.target.files;
    if (files.length > 0) {
        selectedFile = files[0];
        previewFile(selectedFile);
        extractBtn.classList.remove('hidden');
        resultsSection.classList.add('hidden');
    }
}

function previewFile(file) {
    if (file.type === 'application/pdf') {
        imagePreview.src = "https://upload.wikimedia.org/wikipedia/commons/8/87/PDF_file_icon.svg"; // Placeholder
        imagePreview.style.width = "100px";
        previewContainer.classList.remove('hidden');
    } else {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onloadend = function () {
            imagePreview.src = reader.result;
            imagePreview.style.width = "100%";
            previewContainer.classList.remove('hidden');
        }
    }
}

extractBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    extractBtn.textContent = "Processing... (Auto-detecting type)";
    extractBtn.disabled = true;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('doc_type', 'auto'); // Always auto

    try {
        const response = await fetch('http://localhost:8000/extract', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Extraction failed');

        const data = await response.json();
        rawText.value = data.raw_text;

        // Quality Check
        if (data.quality_status === "Blurry") {
            alert(`Warning: The document appears to be blurry (Score: ${Math.round(data.quality_score)}). Accuracy might be low. Consider re-scanning.`);
        }

        // Show detected type (Optional)
        console.log("Detected Type:", data.detected_type);

        // Auto-fill fields
        if (data.fields) {
            document.getElementById('field-name').value = data.fields.name || '';
            document.getElementById('field-age').value = data.fields.age || '';
            document.getElementById('field-gender').value = data.fields.gender || '';
            document.getElementById('field-id').value = data.fields.id_number || '';
            document.getElementById('field-address').value = data.fields.address || '';
            document.getElementById('field-email').value = data.fields.email || '';
            document.getElementById('field-phone').value = data.fields.phone || '';
        }

        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error(error);
        if (error.message.includes('Failed to fetch')) {
            alert('Error: Could not connect to the backend server.\n\nPlease make sure you have run "run_app.bat" and the black terminal window is open and running without errors.');
        } else {
            alert('Error extracting text: ' + error.message);
        }
    } finally {
        extractBtn.textContent = "Extract Text";
        extractBtn.disabled = false;
    }
});

verifyBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    verifyBtn.textContent = "Verifying...";
    verifyBtn.disabled = true;

    const submittedData = {
        "name": document.getElementById('field-name').value,
        "age": document.getElementById('field-age').value,
        "gender": document.getElementById('field-gender').value,
        "id_number": document.getElementById('field-id').value,
        "address": document.getElementById('field-address').value,
        "email": document.getElementById('field-email').value,
        "phone": document.getElementById('field-phone').value
    };

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('submitted_data', JSON.stringify(submittedData));

    try {
        const response = await fetch('http://localhost:8000/verify', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Verification failed');

        const data = await response.json();
        displayVerificationResults(data.matches);

        verificationContainer.classList.remove('hidden');
        verificationContainer.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        alert('Error verifying data: ' + error.message);
    } finally {
        verifyBtn.textContent = "Verify Data";
        verifyBtn.disabled = false;
    }
});

function displayVerificationResults(matches) {
    verificationResults.innerHTML = '';

    for (const [key, score] of Object.entries(matches)) {
        const div = document.createElement('div');
        div.className = 'result-item';

        let status = "Mismatch";
        let statusClass = 'status-mismatch';

        if (score >= 90) {
            status = "Match";
            statusClass = 'status-match';
        } else if (score >= 75) {
            status = "Partial Match";
            statusClass = 'status-partial';
        }

        // Capitalize key
        const label = key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' ');

        div.innerHTML = `
            <div>
                <strong>${label}</strong>
                <div style="font-size: 0.8rem; color: #666;">Match Score: ${Math.round(score)}%</div>
            </div>
            <span class="status-badge ${statusClass}">${status}</span>
        `;
        verificationResults.appendChild(div);
    }
}
