let mediaRecorder;
let audioChunks = [];
let currentNoteId = null;

const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const statusText = document.getElementById('status');
const soapGrid = document.getElementById('soapGrid');
const jsonPlaceholder = document.getElementById('jsonPlaceholder');
const downloadBtn = document.getElementById('downloadBtn');
const saveStatus = document.getElementById('saveStatus');

// NEW: Sidebar Elements
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const historySidebar = document.getElementById('historySidebar');
const pastNotesList = document.getElementById('pastNotesList');

// --- 1. CORE UI LOGIC (Shared by Mic and Sidebar) ---
function renderSoapNoteToGrid(noteId, soapData) {
    currentNoteId = noteId;
    jsonPlaceholder.style.display = 'none';
    soapGrid.style.display = 'grid';
    saveStatus.innerText = "";
    downloadBtn.style.display = "inline-block";

    const populateList = (listId, items) => {
        const ul = document.getElementById(listId);
        ul.innerHTML = '';
        if (items && items.length > 0) {
            items.forEach(item => ul.appendChild(createEditableItem(item.text)));
        } else {
            ul.innerHTML = '<li class="empty-placeholder">None noted.</li>';
        }
    };

    populateList('list-S', soapData.Subjective);
    populateList('list-O', soapData.Objective);
    populateList('list-A', soapData.Assessment);
    populateList('list-P', soapData.Plan);

    if (soapData.Needs_Review && soapData.Needs_Review.length > 0) {
        document.getElementById('box-R').style.display = 'block';
        populateList('list-R', soapData.Needs_Review);
    } else {
        document.getElementById('box-R').style.display = 'none';
    }

    setupDragAndDrop();
    statusText.innerHTML = `✅ <span style="color: #16a34a; font-weight: bold;">Viewing Note #${noteId}. You can edit and save changes.</span>`;
}


// --- 2. BULLETPROOF DRAG AND DROP ENGINE ---
let draggedItem = null;

function setupDragAndDrop() {
    const boxes = document.querySelectorAll('.soap-box');
    boxes.forEach(box => {
        box.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; box.classList.add('drag-active'); });
        box.addEventListener('dragenter', e => { e.preventDefault(); box.classList.add('drag-active'); });
        box.addEventListener('dragleave', e => { if (!box.contains(e.relatedTarget)) box.classList.remove('drag-active'); });
        box.addEventListener('drop', e => {
            e.preventDefault();
            box.classList.remove('drag-active');
            if (draggedItem) {
                let ul = box.querySelector('ul');
                if (!ul) { ul = document.createElement('ul'); box.appendChild(ul); }
                const placeholder = ul.querySelector('.empty-placeholder');
                if (placeholder) placeholder.remove();
                ul.appendChild(draggedItem);
                saveStatus.innerText = "✍️ Unsaved changes...";
                saveStatus.style.color = "#dc2626";
            }
        });
    });
}

function createEditableItem(text) {
    let li = document.createElement('li');
    li.innerText = text;
    li.setAttribute('draggable', 'true');
    li.setAttribute('contenteditable', 'true');
    li.style.cursor = 'grab';

    li.addEventListener('dragstart', function (e) {
        draggedItem = this;
        e.dataTransfer.setData('text/plain', text);
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => this.style.opacity = '0.4', 0);
    });

    li.addEventListener('dragend', function () {
        draggedItem = null;
        this.style.opacity = '1';
    });

    li.addEventListener('input', () => {
        saveStatus.innerText = "✍️ Unsaved changes...";
        saveStatus.style.color = "#dc2626";
    });

    return li;
}

// --- 3. RECORDING AND API LOGIC ---
recordBtn.onclick = async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();
        audioChunks = [];

        recordBtn.classList.add('recording-pulse');
        recordBtn.disabled = true;
        stopBtn.disabled = false;
        statusText.innerHTML = '<span style="color: #dc2626; font-weight: bold;">🎙️ Listening... Speak your clinical note clearly.</span>';

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

        mediaRecorder.onstop = async () => {
            recordBtn.classList.remove('recording-pulse');
            statusText.innerHTML = '🧠 <span style="color: #2563eb;">AI is transcribing and categorizing...</span>';

            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('file', audioBlob, 'live_dictation.webm');

            try {
                const response = await fetch('/upload-audio', { method: 'POST', body: formData });
                const data = await response.json();
                if (data && data.data) {
                    renderSoapNoteToGrid(data.note_id, data.data);
                }
            } catch (err) {
                statusText.innerText = '❌ Error processing response.';
                console.error(err);
            }
        };
    } catch (err) {
        statusText.innerText = '❌ Microphone access denied.';
    }
};

stopBtn.onclick = () => {
    mediaRecorder.stop();
    recordBtn.disabled = false;
    stopBtn.disabled = true;
    statusText.innerText = '⏳ Processing...';
};

// --- 4. SAVE AND EXPORT LOGIC ---
downloadBtn.onclick = async () => {
    if (!currentNoteId) return;
    saveStatus.innerText = "⏳ Saving...";
    saveStatus.style.color = "#2563eb";
    downloadBtn.disabled = true;

    const scrapeList = (listId) => {
        const items = document.querySelectorAll(`#${listId} li`);
        return Array.from(items)
            .filter(li => !li.classList.contains('empty-placeholder') && li.innerText.trim() !== "None noted.")
            .map(li => ({ text: li.innerText.trim(), confidence: 100 }));
    };

    const updatedData = {
        "Subjective": scrapeList('list-S'),
        "Objective": scrapeList('list-O'),
        "Assessment": scrapeList('list-A'),
        "Plan": scrapeList('list-P'),
        "Needs_Review": scrapeList('list-R')
    };

    try {
        await fetch(`/notes/${currentNoteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ structured_data: updatedData })
        });
        saveStatus.innerText = "✅ Saved!";
        saveStatus.style.color = "#16a34a";
        window.location.href = `/notes/${currentNoteId}/pdf`;
    } catch (error) {
        saveStatus.innerText = "❌ Failed to save";
        saveStatus.style.color = "#dc2626";
        console.error("Save error:", error);
    } finally {
        downloadBtn.disabled = false;
    }
};

// --- 5. SIDEBAR & PAST CASES LOGIC ---
toggleSidebarBtn.onclick = async () => {
    historySidebar.classList.add('open');
    pastNotesList.innerHTML = '<p style="text-align: center; color: #64748b;">Fetching records...</p>';

    try {
        const response = await fetch('/notes?limit=15');
        const data = await response.json();

        pastNotesList.innerHTML = ''; // Clear loading text

        if (data.notes.length === 0) {
            pastNotesList.innerHTML = '<p style="text-align: center; color: #64748b;">No past cases found.</p>';
            return;
        }

        data.notes.forEach(note => {
            const dateStr = new Date(note.created_at).toLocaleString();
            // Get a snippet of the transcript for the preview
            const previewText = note.raw_transcript ? note.raw_transcript.substring(0, 50) + '...' : 'No audio transcript available.';

            const card = document.createElement('div');
            card.className = 'history-card';
            card.innerHTML = `
                <div class="history-date">📅 ${dateStr} (ID: ${note.id})</div>
                <div class="history-preview">"${previewText}"</div>
            `;

            // When clicked, close sidebar and render the note!
            card.onclick = () => {
                historySidebar.classList.remove('open');
                renderSoapNoteToGrid(note.id, note.structured_data);
            };

            pastNotesList.appendChild(card);
        });
    } catch (err) {
        pastNotesList.innerHTML = '<p style="color: red; text-align:center;">Failed to load cases.</p>';
        console.error(err);
    }
};

closeSidebarBtn.onclick = () => {
    historySidebar.classList.remove('open');
};