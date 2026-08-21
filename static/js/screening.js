/**
 * VisionAI — screening.js
 * Upload handling, drag-and-drop, inference API call, and results DOM rendering.
 * Depends on: app.js (getCSRFToken, cap, darken), diseases.js (getDisease, DB)
 * Loaded only on the /screening page.
 */

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════

const State = { file: null, analyzing: false, result: null };

// ═══════════════════════════════════════════════════════════════════════════════
// BOOT — initialise all screening logic after DOM is ready
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 VisionAI Screening Initialized');
    initUpload();
    initActions();
    fetch('/config').then(r => r.json()).then(c => console.log('📋 Config:', c)).catch(() => { });
});

// ═══════════════════════════════════════════════════════════════════════════════
// UPLOAD
// ═══════════════════════════════════════════════════════════════════════════════

function initUpload() {
    const input = document.getElementById('imageInput');
    const area = document.getElementById('uploadArea');
    const btn = document.getElementById('uploadBtn');
    const preview = document.getElementById('imagePreview');
    const remove = document.getElementById('removeImage');

    if (!input || !area) return;

    btn?.addEventListener('click', e => { e.stopPropagation(); input.click(); });
    area.addEventListener('click', () => input.click());
    input.addEventListener('change', e => e.target.files[0] && handleFile(e.target.files[0]));
    remove?.addEventListener('click', reset);

    // Drag & drop
    ['dragover', 'dragenter'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.add('dragover'); }));
    ['dragleave', 'dragend'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.remove('dragover'); }));
    area.addEventListener('drop', e => {
        e.preventDefault();
        area.classList.remove('dragover');
        e.dataTransfer.files[0] && handleFile(e.dataTransfer.files[0]);
    });
}

function handleFile(file) {
    const area = document.getElementById('uploadArea');
    const preview = document.getElementById('imagePreview');
    const img = document.getElementById('previewImg');

    const valid = validateFile(file);
    if (!valid.ok) return showError(valid.error);

    State.file = file;
    const reader = new FileReader();
    reader.onload = e => {
        img.src = e.target.result;
        preview.style.display = 'flex';
        area.style.display = 'none';
        setTimeout(analyze, 500);
    };
    reader.readAsDataURL(file);
}

function validateFile(file) {
    if (!file) return { ok: false, error: 'No file selected' };
    const types = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff', 'image/webp'];
    if (!types.includes(file.type.toLowerCase())) return { ok: false, error: 'Unsupported format. Use PNG, JPG, BMP, TIFF, or WEBP' };
    if (file.size > 16 * 1024 * 1024) return { ok: false, error: 'File too large. Max 16MB' };
    return { ok: true };
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYSIS — POST to /predict via fetch
// ═══════════════════════════════════════════════════════════════════════════════

async function analyze() {
    if (!State.file || State.analyzing) return;
    State.analyzing = true;

    const section = document.getElementById('analysisSection');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');

    section.style.display = 'block';
    loading.style.display = 'block';
    results.style.display = 'none';
    error.style.display = 'none';

    // Scroll to analysis section
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const form = new FormData();
        form.append('image', State.file);

        // CRITICAL: Include credentials (session cookies) and CSRF token
        const res = await fetch('/predict', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() },
            body: form,
            credentials: 'same-origin'
        });

        // Check if we got redirected to login (authentication issue)
        if (res.redirected || res.url.includes('/login')) {
            loading.style.display = 'none';
            showError('Session expired. Please refresh and login again.');
            setTimeout(() => window.location.href = '/login', 2000);
            return;
        }

        // Check content type - if HTML, session expired
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            loading.style.display = 'none';
            showError('Session expired. Redirecting to login...');
            setTimeout(() => window.location.href = '/login', 2000);
            return;
        }

        const data = await res.json();
        loading.style.display = 'none';

        if (data.success && data.predictions) {
            State.result = data;
            showResults(data.predictions);
        } else {
            showError(data.error || 'Analysis failed');
        }
    } catch (e) {
        loading.style.display = 'none';
        showError('Network error. Check connection.');
        console.error('Analysis error:', e);
    }
    State.analyzing = false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// RESULTS DISPLAY
// ═══════════════════════════════════════════════════════════════════════════════

function showResults(preds) {
    const results = document.getElementById('results');
    const primary = document.getElementById('primaryDiagnosis');
    const predsEl = document.getElementById('predictions');

    if (!preds?.length) return showError('No results');
    results.style.display = 'block';

    const top = preds[0];
    const d = getDisease(top.label);

    // Primary diagnosis card
    primary.innerHTML = `
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4)">
            <span style="font-size:2rem">${d.icon}</span>
            <div>
                <div style="font-size:0.875rem;opacity:0.9">Primary Finding</div>
                <div style="font-size:1.5rem;font-weight:700">${d.name}</div>
            </div>
        </div>
        <p style="opacity:0.9;margin-bottom:var(--space-4)">${d.desc}</p>
        <div style="background:rgba(255,255,255,0.2);border-radius:var(--radius-lg);padding:var(--space-3)">
            <div style="display:flex;justify-content:space-between;margin-bottom:var(--space-2);font-size:0.875rem">
                <span>AI Match Score</span>
                <span>${(top.confidence || 0).toFixed(1)}%</span>
            </div>
            <div style="height:8px;background:rgba(255,255,255,0.3);border-radius:var(--radius-full);overflow:hidden">
                <div style="height:100%;width:${Math.min(top.confidence || 0, 100)}%;background:linear-gradient(90deg,#2dd4bf,#10b981);border-radius:var(--radius-full)"></div>
            </div>
        </div>
    `;
    primary.style.background = `linear-gradient(135deg, ${d.color}, ${darken(d.color, 20)})`;

    // Prediction cards
    predsEl.innerHTML = preds.map((p, i) => {
        const dis = getDisease(p.label);
        return `
        <div class="disease-card ${i === 0 ? 'expanded' : ''}" id="card-${i}">
            <div class="disease-card-header" onclick="toggle('card-${i}')">
                <div class="disease-icon-wrapper ${dis.severity}"><span class="disease-icon">${dis.icon}</span></div>
                <div class="disease-info">
                    <h4 class="disease-name">${dis.name}</h4>
                    <span class="disease-severity ${dis.severity}">${cap(dis.severity)}</span>
                </div>
                <div class="disease-confidence">
                    <span class="confidence-value">${(p.confidence || 0).toFixed(1)}%</span>
                    <span class="confidence-text">match score</span>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="disease-card-body">
                <p style="color:var(--gray-500);margin-bottom:var(--space-5);line-height:1.7">${dis.info}</p>
                <div class="info-tabs" id="tabs-${i}">
                    <button class="info-tab active" data-tab="recs" onclick="tab(${i},'recs')">📋 Recommendations</button>
                    <button class="info-tab" data-tab="habits" onclick="tab(${i},'habits')">🌟 Daily Habits</button>
                    <button class="info-tab" data-tab="prevent" onclick="tab(${i},'prevent')">🛡️ Prevention</button>
                </div>
                <div class="tab-content active" id="recs-${i}">${renderRecs(dis.recs)}</div>
                <div class="tab-content" id="habits-${i}">${renderHabits(dis.habits)}</div>
                <div class="tab-content" id="prevent-${i}">${renderPrevent(dis.prevent)}</div>
            </div>
        </div>`;
    }).join('');
}

function renderRecs(recs) {
    if (!recs?.length) return '<p>No recommendations.</p>';
    return `<div class="recommendation-grid">${recs.map(r => `
        <div class="recommendation-card ${r.priority || ''}">
            <span class="recommendation-icon">${r.icon}</span>
            <h5 class="recommendation-title">${r.title}</h5>
            <p class="recommendation-text">${r.text}</p>
        </div>`).join('')}</div>`;
}

function renderHabits(habits) {
    if (!habits?.length) return '<p>No habits.</p>';
    return `<div class="habits-list">${habits.map(h => `
        <div class="habit-item">
            <div class="habit-icon-wrapper"><span class="habit-icon">${h.icon}</span></div>
            <div class="habit-content">
                <h5 class="habit-title">${h.title}</h5>
                <p class="habit-description">${h.desc}</p>
                <span class="habit-frequency"><span>🕐</span><span>${h.freq}</span></span>
            </div>
        </div>`).join('')}</div>`;
}

function renderPrevent(tips) {
    if (!tips?.length) return '<p>No tips.</p>';
    return `<div class="prevention-tips">${tips.map(t => `
        <div class="prevention-tip">
            <span class="prevention-icon">${t.icon}</span>
            <h5 class="prevention-title">${t.title}</h5>
            <p class="prevention-text">${t.text}</p>
        </div>`).join('')}</div>`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// GLOBAL ONCLICK HANDLERS (called from inline onclick= in rendered HTML)
// ═══════════════════════════════════════════════════════════════════════════════

window.toggle = id => document.getElementById(id)?.classList.toggle('expanded');

window.tab = (i, name) => {
    document.querySelectorAll(`#tabs-${i} .info-tab`).forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    ['recs', 'habits', 'prevent'].forEach(n => {
        const el = document.getElementById(`${n}-${i}`);
        el && (el.classList.toggle('active', n === name));
    });
};

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════════════════

function initActions() {
    document.getElementById('retryBtn')?.addEventListener('click', () => State.file && analyze());
    document.getElementById('newAnalysis')?.addEventListener('click', reset);
    document.getElementById('downloadReport')?.addEventListener('click', downloadReport);
}

function reset() {
    const input = document.getElementById('imageInput');
    const area = document.getElementById('uploadArea');
    const preview = document.getElementById('imagePreview');
    const section = document.getElementById('analysisSection');

    State.file = null;
    State.analyzing = false;
    State.result = null;
    if (input) input.value = '';
    if (preview) preview.style.display = 'none';
    if (area) area.style.display = 'block';
    if (section) section.style.display = 'none';
}

function showError(msg) {
    const section = document.getElementById('analysisSection');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');
    const errMsg = document.getElementById('errorMessage');

    if (section) section.style.display = 'block';
    if (loading) loading.style.display = 'none';
    if (results) results.style.display = 'none';
    if (error) error.style.display = 'block';
    if (errMsg) errMsg.textContent = msg;
}
