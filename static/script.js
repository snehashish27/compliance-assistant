// ─── DOM References ────────────────────────────────────────────────
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const selectedFilesContainer = document.getElementById('selectedFiles');
const analyzeBtn = document.getElementById('analyzeBtn');

const progressContainer = document.getElementById('progress-container');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');

const uploadSection = document.getElementById('upload-section');
const resultsContainer = document.getElementById('results-container');

const chatPlaceholder = document.getElementById('chatPlaceholder');
const chatSection = document.getElementById('chatSection');
const payloadPlaceholder = document.getElementById('payloadPlaceholder');
const payloadContent = document.getElementById('payloadContent');

const resizeHandle = document.getElementById('resizeHandle');
const rightPanel = document.getElementById('rightPanel');

let uploadedFiles = [];
let currentSessionId = null;
let chartInstance = null;

// ─── Panel Resize: outer handle (right panel total width) ──────────
let isPanelDragging = false, panelStartX = 0, panelStartWidth = 0;

resizeHandle.addEventListener('mousedown', (e) => {
    isPanelDragging = true;
    panelStartX = e.clientX;
    panelStartWidth = rightPanel.offsetWidth;
    resizeHandle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (!isPanelDragging) return;
    const dx = panelStartX - e.clientX;   // drag left → wider panel
    const newW = Math.max(260, Math.min(900, panelStartWidth + dx));
    rightPanel.style.width = newW + 'px';
});

document.addEventListener('mouseup', () => {
    if (!isPanelDragging) return;
    isPanelDragging = false;
    resizeHandle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
});

// ─── Right Panel Tab Switching ────────────────────────────────────
document.querySelectorAll('.rp-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.rp-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.rp-pane').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});


// ─── File Upload Logic ─────────────────────────────────────────────
browseBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--accent)';
});

dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = 'var(--border-color)';
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--border-color)';
    handleFiles(e.dataTransfer.files);
});

function handleFiles(files) {
    uploadedFiles = Array.from(files);
    renderFileChips();
    analyzeBtn.disabled = uploadedFiles.length === 0;
}

function renderFileChips() {
    selectedFilesContainer.innerHTML = '';
    uploadedFiles.forEach(file => {
        const chip = document.createElement('div');
        chip.className = 'file-chip';
        chip.innerHTML = `📄 ${file.name}`;
        selectedFilesContainer.appendChild(chip);
    });
}

// ─── Analysis Logic ────────────────────────────────────────────────
analyzeBtn.addEventListener('click', async () => {
    if (uploadedFiles.length === 0) return;

    uploadSection.classList.add('hidden');
    progressContainer.classList.remove('hidden');

    let progress = 0;
    const interval = setInterval(() => {
        progress += 5;
        if (progress > 90) clearInterval(interval);
        progressFill.style.width = `${Math.min(progress, 90)}%`;
        if (progress < 30) progressText.innerText = "📄 Parsing documents and extracting text...";
        else if (progress < 60) progressText.innerText = "🔍 Running NLP entity detection...";
        else if (progress < 80) progressText.innerText = "🔒 Masking and redacting PII...";
        else progressText.innerText = "🧠 Building FAISS vector index...";
    }, 500);

    const formData = new FormData();
    uploadedFiles.forEach(file => formData.append('files', file));

    try {
        const response = await fetch('/api/analyze', { method: 'POST', body: formData });
        const data = await response.json();
        clearInterval(interval);
        progressFill.style.width = '100%';
        progressText.innerText = "✅ Analysis Complete";
        setTimeout(() => { progressContainer.classList.add('hidden'); showResults(data); }, 1000);
    } catch (error) {
        clearInterval(interval);
        alert("Error during analysis: " + error.message);
        progressContainer.classList.add('hidden');
        uploadSection.classList.remove('hidden');
    }
});

// ─── Helpers ────────────────────────────────────────────────────────
const riskColors = {
    "Low Risk": "#10b981", "Medium Risk": "#f59e0b",
    "High Risk": "#ef4444", "Critical Risk": "#9f1239"
};

const entityIcons = {
    "EMAIL": "📧", "PHONE": "📞", "NAME": "👤", "ADDRESS": "🏠",
    "CREDIT_CARD": "💳", "DATE": "📅", "AADHAAR": "🪪", "PAN": "🗂️"
};

function getEntityIcon(entity) {
    for (const [key, icon] of Object.entries(entityIcons)) {
        if (entity.toUpperCase().includes(key)) return icon;
    }
    return "🔵";
}

// ─── Show Results ──────────────────────────────────────────────────
function showResults(data) {
    currentSessionId = data.session_id;
    resultsContainer.classList.remove('hidden');

    // Metrics
    const riskValue = document.getElementById('riskValue');
    riskValue.innerText = data.metrics.risk;
    riskValue.style.color = riskColors[data.metrics.risk] || "#6366f1";
    document.getElementById('totalValue').innerText = data.metrics.total;
    document.getElementById('distinctCount').innerText = Object.keys(data.metrics.breakdown).length;
    document.getElementById('docsValue').innerText = data.processed_files.length;

    // Entities list
    const entitiesList = document.getElementById('entitiesList');
    entitiesList.innerHTML = '';
    const breakdown = Object.entries(data.metrics.breakdown).sort((a, b) => b[1] - a[1]);

    if (breakdown.length === 0) {
        entitiesList.innerHTML = `<div style="text-align:center;padding:1.5rem;color:var(--text-muted)">
            <div style="font-size:1.75rem">✅</div><div>No PII intercepted</div></div>`;
    } else {
        breakdown.forEach(([entity, count]) => {
            const row = document.createElement('div');
            row.className = 'entity-row';
            row.innerHTML = `<span>${getEntityIcon(entity)} ${entity.replace(/_/g, ' ').toUpperCase()}</span>
                             <span class="entity-count">${count}</span>`;
            entitiesList.appendChild(row);
        });
        drawChart(data.metrics.breakdown);
    }

    // Reset report CTA
    document.getElementById('reportGenerateArea').style.display = '';
    document.getElementById('aiReportBox').style.display = 'none';
    document.getElementById('aiReportBox').innerHTML = '';
    document.getElementById('downloadReportBtn').style.display = 'none';
    const genBtn = document.getElementById('generateReportBtn');
    genBtn.disabled = false;
    genBtn.innerText = '⚡ Generate Compliance Report';

    // ── Activate right panel ────────────────────────────────────────
    chatPlaceholder.classList.add('hidden');
    chatSection.classList.remove('hidden');
    payloadPlaceholder.classList.add('hidden');
    payloadContent.classList.remove('hidden');

    // Reset chat
    const chatHistory = document.getElementById('chatHistory');
    chatHistory.innerHTML = `
        <div class="chat-placeholder" id="chatInitPlaceholder">
            <div class="icon">💬</div>
            <h4>Ready to answer your questions</h4>
            <p>Try: "Summarize key risks" · "What PII was found?"</p>
        </div>`;

    // Fill payload textarea
    document.getElementById('rawPayload').value = data.masked_context;
}

// ─── Generate Compliance Report ────────────────────────────────────
let rawReportMarkdown = '';

document.getElementById('generateReportBtn').addEventListener('click', async () => {
    if (!currentSessionId) return;
    const btn = document.getElementById('generateReportBtn');
    btn.disabled = true;
    btn.innerText = '⏳ Generating Report...';

    try {
        const response = await fetch('/api/generate-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Unknown error');
        }
        const data = await response.json();
        rawReportMarkdown = data.report;

        document.getElementById('reportGenerateArea').style.display = 'none';
        const reportBox = document.getElementById('aiReportBox');
        let html = data.report.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br>');
        reportBox.innerHTML = html;
        reportBox.style.display = '';
        document.getElementById('downloadReportBtn').style.display = '';
    } catch (e) {
        btn.disabled = false;
        btn.innerText = '⚡ Generate Compliance Report';
        alert('Error generating report: ' + e.message);
    }
});

// ─── Chart ─────────────────────────────────────────────────────────
function drawChart(breakdown) {
    const ctx = document.getElementById('distributionChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(breakdown),
            datasets: [{ label: 'Entities Found', data: Object.values(breakdown), backgroundColor: '#6366f1', borderRadius: 4 }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, grid: { color: '#334155' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

// ─── Chat Logic ─────────────────────────────────────────────────────
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatHistory = document.getElementById('chatHistory');

async function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message || !currentSessionId) return;

    const placeholder = chatHistory.querySelector('.chat-placeholder');
    if (placeholder) placeholder.remove();

    appendMessage('user', message);
    chatInput.value = '';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId, message })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            appendMessage('bot', `⚠️ Server error: ${err.detail || response.statusText}`);
            return;
        }
        const data = await response.json();
        appendMessage('bot', data.reply);
    } catch (e) {
        appendMessage('bot', '⚠️ Error connecting to server.');
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`;
    msgDiv.innerText = text;
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

sendBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendChatMessage(); });

// ─── Downloads ──────────────────────────────────────────────────────
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

document.getElementById('downloadReportBtn').addEventListener('click', () => {
    if (!rawReportMarkdown) return;
    downloadFile(rawReportMarkdown, `compliance_report_${new Date().toISOString().slice(0,10)}.md`, 'text/markdown');
});

document.getElementById('downloadPayloadBtn').addEventListener('click', () => {
    const payload = document.getElementById('rawPayload').value;
    if (!payload) return;
    downloadFile(payload, `sanitized_payload_${new Date().toISOString().slice(0,10)}.txt`, 'text/plain');
});
