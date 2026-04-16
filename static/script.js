let mediaRecorder;
let audioChunks = [];
let currentNoteId = null;
let draggedItem = null;

const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || "";

const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const statusText = document.getElementById('status');
const soapGrid = document.getElementById('soapGrid');
const jsonPlaceholder = document.getElementById('jsonPlaceholder');
const downloadBtn = document.getElementById('downloadBtn');
const saveStatus = document.getElementById('saveStatus');

// Review Panel
const reviewPanel = document.getElementById('reviewPanel');

// Sidebar Elements
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const historySidebar = document.getElementById('historySidebar');
const pastNotesList = document.getElementById('pastNotesList');

function apiUrl(path) {
    return `${API_BASE_URL}${path}`;
}

async function parseApiResponse(response) {
    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            if (contentType.includes("application/json")) {
                const err = await response.json();
                message = err.detail || err.message || message;
            } else {
                const text = await response.text();
                if (text) message = text;
            }
        } catch (_) { }
        throw new Error(message);
    }

    if (contentType.includes("application/json")) {
        return response.json();
    }

    return response;
}

function setStatus(html) {
    statusText.innerHTML = html;
}

function setSaveStatus(text, color) {
    saveStatus.innerText = text;
    saveStatus.style.color = color;
}

function markUnsaved() {
    setSaveStatus("✍️ Unsaved changes...", "#dc2626");
}

function populateReviewList(elementId, items, formatter, emptyText) {
    const ul = document.getElementById(elementId);
    ul.innerHTML = '';

    if (Array.isArray(items) && items.length > 0) {
        items.forEach(item => {
            const li = document.createElement('li');
            li.innerHTML = formatter(item);
            ul.appendChild(li);
        });
    } else {
        ul.innerHTML = `<li>${emptyText}</li>`;
    }
}

function createEditableItem(text) {
    const li = document.createElement('li');
    li.innerText = text;
    li.setAttribute('draggable', 'true');
    li.setAttribute('contenteditable', 'true');
    li.style.cursor = 'grab';

    li.addEventListener('dragstart', function (e) {
        draggedItem = this;
        e.dataTransfer.setData('text/plain', this.innerText);
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => {
            this.style.opacity = '0.4';
        }, 0);
    });

    li.addEventListener('dragend', function () {
        draggedItem = null;
        this.style.opacity = '1';
    });

    li.addEventListener('input', () => {
        markUnsaved();
    });

    return li;
}

function populateSoapList(listId, items) {
    const ul = document.getElementById(listId);
    ul.innerHTML = '';

    if (Array.isArray(items) && items.length > 0) {
        items.forEach(item => {
            ul.appendChild(createEditableItem(item.text || ""));
        });
    } else {
        ul.innerHTML = '<li class="empty-placeholder">None noted.</li>';
    }
}

function renderReviewPanel(reviewData) {
    if (!reviewData) {
        reviewPanel.style.display = 'none';
        return;
    }

    reviewPanel.style.display = 'block';

    populateReviewList(
        'review-quality',
        reviewData.note_quality_summary || [],
        text => `${text}`,
        'None identified.'
    );

    populateReviewList(
        'review-missing',
        reviewData.missing_or_incomplete_documentation || [],
        item => `<b>${item.item || "Item"}:</b> ${item.recommendation || ""}`,
        'None identified.'
    );

    populateReviewList(
        'review-risk',
        reviewData.high_risk_documentation_prompts || [],
        item => `<b>${item.item || "Item"}:</b> ${item.recommendation || ""}`,
        'None identified.'
    );

    populateReviewList(
        'review-icd10',
        reviewData.icd10_suggestions_beta || [],
        item => `<b>${item.code || "N/A"}</b>: ${item.label || "Unnamed"} <br><span style="font-size: 11px; color:#94a3b8;">(${item.reason || "No reason provided"})</span>`,
        'No reliable suggestions based on current documentation.'
    );

    document.getElementById('review-disclaimer').innerText =
        reviewData.final_disclaimer || "";
}

function renderSoapNoteToGrid(noteId, soapData, reviewData = null) {
    currentNoteId = noteId;
    jsonPlaceholder.style.display = 'none';
    soapGrid.style.display = 'grid';
    downloadBtn.style.display = "inline-block";
    setSaveStatus("", "#64748b");

    populateSoapList('list-S', soapData?.Subjective || []);
    populateSoapList('list-O', soapData?.Objective || []);
    populateSoapList('list-A', soapData?.Assessment || []);
    populateSoapList('list-P', soapData?.Plan || []);

    const needsReviewBox = document.getElementById('box-R');
    if (soapData?.Needs_Review && soapData.Needs_Review.length > 0) {
        needsReviewBox.style.display = 'block';
        populateSoapList('list-R', soapData.Needs_Review);
    } else {
        needsReviewBox.style.display = 'none';
        document.getElementById('list-R').innerHTML = '';
    }

    renderReviewPanel(reviewData);
    setupDragAndDrop();

    setStatus(`✅ <span style="color: #16a34a; font-weight: bold;">Viewing Note #${noteId}. You can edit and save changes.</span>`);
}

function setupDragAndDrop() {
    const boxes = document.querySelectorAll('.soap-box');

    boxes.forEach(box => {
        box.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            box.classList.add('drag-active');
        });

        box.addEventListener('dragenter', e => {
            e.preventDefault();
            box.classList.add('drag-active');
        });

        box.addEventListener('dragleave', e => {
            if (!box.contains(e.relatedTarget)) {
                box.classList.remove('drag-active');
            }
        });

        box.addEventListener('drop', e => {
            e.preventDefault();
            box.classList.remove('drag-active');

            if (!draggedItem) return;

            let ul = box.querySelector('ul');
            if (!ul) {
                ul = document.createElement('ul');
                box.appendChild(ul);
            }

            const placeholder = ul.querySelector('.empty-placeholder');
            if (placeholder) placeholder.remove();

            ul.appendChild(draggedItem);
            markUnsaved();
        });
    });
}

function scrapeList(listId) {
    const items = document.querySelectorAll(`#${listId} li`);
    return Array.from(items)
        .filter(li => !li.classList.contains('empty-placeholder'))
        .map(li => ({
            text: li.innerText.trim(),
            confidence: 100
        }))
        .filter(item => item.text !== "" && item.text !== "None noted.");
}

async function uploadAudioForProcessing(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'live_dictation.webm');

    const response = await fetch(apiUrl('/upload-audio'), {
        method: 'POST',
        body: formData
    });

    return parseApiResponse(response);
}

async function saveCurrentNote(noteId, updatedData) {
    const response = await fetch(apiUrl(`/notes/${noteId}`), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ structured_data: updatedData })
    });

    return parseApiResponse(response);
}

async function fetchPastNotes(limit = 15) {
    const response = await fetch(apiUrl(`/notes?limit=${limit}`), {
        method: 'GET'
    });

    return parseApiResponse(response);
}

recordBtn.onclick = async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => {
            if (e.data && e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = async () => {
            try {
                recordBtn.classList.remove('recording-pulse');
                setStatus('🧠 <span style="color: #2563eb;">AI reasoning pipeline active. Transcribing & Drafting...</span>');

                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const data = await uploadAudioForProcessing(audioBlob);

                if (data && data.data) {
                    renderSoapNoteToGrid(data.note_id, data.data, data.review_panel || null);
                } else {
                    setStatus('❌ <span style="color: #dc2626;">Backend returned an unexpected response.</span>');
                }
            } catch (err) {
                console.error(err);
                setStatus(`❌ <span style="color: #dc2626;">${err.message || "Error processing response."}</span>`);
            } finally {
                stream.getTracks().forEach(track => track.stop());
                recordBtn.disabled = false;
                stopBtn.disabled = true;
            }
        };

        mediaRecorder.start();

        recordBtn.classList.add('recording-pulse');
        recordBtn.disabled = true;
        stopBtn.disabled = false;
        setStatus('<span style="color: #dc2626; font-weight: bold;">🎙️ Listening... Speak your clinical note clearly.</span>');
    } catch (err) {
        console.error(err);
        setStatus('❌ <span style="color: #dc2626;">Microphone access denied or unavailable.</span>');
    }
};

stopBtn.onclick = () => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;

    mediaRecorder.stop();
    recordBtn.disabled = true;
    stopBtn.disabled = true;
    statusText.innerText = '⏳ Processing... (This might take a few seconds for the multi-layer pipeline)';
};

downloadBtn.onclick = async () => {
    if (!currentNoteId) return;

    setSaveStatus("⏳ Saving...", "#2563eb");
    downloadBtn.disabled = true;

    const updatedData = {
        Subjective: scrapeList('list-S'),
        Objective: scrapeList('list-O'),
        Assessment: scrapeList('list-A'),
        Plan: scrapeList('list-P'),
        Needs_Review: scrapeList('list-R')
    };

    try {
        await saveCurrentNote(currentNoteId, updatedData);
        setSaveStatus("✅ Saved!", "#16a34a");
        window.open(apiUrl(`/notes/${currentNoteId}/pdf`), '_blank', 'noopener');
    } catch (error) {
        console.error("Save error:", error);
        setSaveStatus("❌ Failed to save", "#dc2626");
    } finally {
        downloadBtn.disabled = false;
    }
};

toggleSidebarBtn.onclick = async () => {
    historySidebar.classList.add('open');
    pastNotesList.innerHTML = '<p style="text-align: center; color: #64748b;">Fetching records...</p>';

    try {
        const data = await fetchPastNotes(15);
        pastNotesList.innerHTML = '';

        if (!data.notes || data.notes.length === 0) {
            pastNotesList.innerHTML = '<p style="text-align: center; color: #64748b;">No past cases found.</p>';
            return;
        }

        data.notes.forEach(note => {
            const dateStr = note.created_at
                ? new Date(note.created_at).toLocaleString()
                : 'Unknown date';

            const previewText = note.raw_transcript
                ? `${note.raw_transcript.substring(0, 50)}...`
                : 'No audio transcript available.';

            const card = document.createElement('div');
            card.className = 'history-card';
            card.innerHTML = `
                <div class="history-date">📅 ${dateStr} (ID: ${note.id})</div>
                <div class="history-preview">"${previewText}"</div>
            `;

            card.onclick = () => {
                historySidebar.classList.remove('open');
                renderSoapNoteToGrid(note.id, note.structured_data, null);
            };

            pastNotesList.appendChild(card);
        });
    } catch (err) {
        console.error(err);
        pastNotesList.innerHTML = `<p style="color: red; text-align:center;">${err.message || "Failed to load cases."}</p>`;
    }
};

closeSidebarBtn.onclick = () => {
    historySidebar.classList.remove('open');
};
