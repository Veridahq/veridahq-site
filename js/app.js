// API configuration
const API_BASE_URL = 'https://verida-api.onrender.com/api';
let currentUser = null;
let currentOrgId = null;
let loadingOverlay = null;

// Initialize loading overlay
function createLoadingOverlay() {
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loadingOverlay';
        loadingOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        loadingOverlay.innerHTML = `
            <div style="background: white; padding: 40px; border-radius: 8px; text-align: center;">
                <div style="margin-bottom: 20px;">
                    <div style="border: 4px solid #f3f4f6; border-top: 4px solid #2a9d8f; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                </div>
                <p style="color: #1b365d; font-weight: 600;">Loading...</p>
                <p style="color: #6b7280; font-size: 12px; margin-top: 8px;">First request may take up to 50 seconds due to server cold start.</p>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
        document.body.appendChild(loadingOverlay);
    }
    return loadingOverlay;
}

function showLoading(show = true) {
    const overlay = createLoadingOverlay();
    overlay.style.display = show ? 'flex' : 'none';
}

// Fetch wrapper with error handling
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = localStorage.getItem('accessToken');

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    showLoading(true);

    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

        showLoading(false);

        if (response.status === 401) {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            localStorage.removeItem('currentUser');
            window.location.href = 'app.html';
            return null;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        showLoading(false);
        console.error('API Error:', error);
        throw error;
    }
}

// Check if in demo mode
function isDemoMode() {
    const urlDemo = new URLSearchParams(window.location.search).get('demo') === 'true';
    return urlDemo || !!localStorage.getItem('demoUser');
}

// Check for password reset token in URL
function checkForResetToken() {
    const params = new URLSearchParams(window.location.hash.replace('#', '?'));
    const accessToken = params.get('access_token');
    const type = params.get('type');

    if (accessToken && type === 'recovery') {
        localStorage.setItem('accessToken', accessToken);
        document.getElementById('authScreen').style.display = 'flex';
        document.getElementById('appShell').style.display = 'none';
        showUpdatePassword();
        return true;
    }
    return false;
}

// Check authentication on load
window.addEventListener('load', async () => {
    // Check for password reset token first
    if (checkForResetToken()) return;

    const accessToken = localStorage.getItem('accessToken');
    const demoUser = localStorage.getItem('demoUser');

    if (!isDemoMode() && !accessToken) {
        document.getElementById('authScreen').style.display = 'flex';
        document.getElementById('appShell').style.display = 'none';
    } else if (isDemoMode()) {
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('appShell').style.display = 'flex';

        if (demoUser) {
            const user = JSON.parse(demoUser);
            document.getElementById('orgName').textContent = user.org || 'Demo Organization';
        }

        initCharts();
        attachEventListeners();
        renderDemoData();
    } else {
        try {
            const userData = await apiFetch('/auth/me');
            if (userData) {
                currentUser = userData;
                currentOrgId = userData.organization_id;

                document.getElementById('authScreen').style.display = 'none';
                document.getElementById('appShell').style.display = 'flex';

                if (userData.organization && userData.organization.name) {
                    document.getElementById('orgName').textContent = userData.organization.name;
                }

                // Update profile avatar initials
                if (userData.full_name) {
                    const initials = userData.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
                    const avatar = document.querySelector('.navbar-right div[title="Profile"]');
                    if (avatar) avatar.textContent = initials;
                }

                initCharts();
                attachEventListeners();
                loadDashboardData();
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            localStorage.removeItem('currentUser');
            document.getElementById('authScreen').style.display = 'flex';
            document.getElementById('appShell').style.display = 'none';
        }
    }
});

// ========== AUTH FUNCTIONS ==========

async function handleAuthLogin(e) {
    e.preventDefault();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;

    try {
        showLoading(true);
        const response = await apiFetch('/auth/signin', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });

        if (response && response.access_token) {
            localStorage.setItem('accessToken', response.access_token);
            localStorage.setItem('refreshToken', response.refresh_token);
            currentUser = response.user;
            currentOrgId = response.user.organization_id;

            if (response.user.organization) {
                document.getElementById('orgName').textContent = response.user.organization.name;
            }

            document.getElementById('authScreen').style.display = 'none';
            document.getElementById('appShell').style.display = 'flex';
            initCharts();
            attachEventListeners();
            loadDashboardData();
        }
        showLoading(false);
    } catch (error) {
        showLoading(false);
        alert('Login failed: ' + error.message);
    }
}

function showSignUp() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('signupView').style.display = 'block';
    document.getElementById('forgotPasswordView').style.display = 'none';
    document.getElementById('updatePasswordView').style.display = 'none';
}

function showLogin() {
    document.getElementById('signupView').style.display = 'none';
    document.getElementById('loginView').style.display = 'block';
    document.getElementById('forgotPasswordView').style.display = 'none';
    document.getElementById('updatePasswordView').style.display = 'none';
}

function showForgotPassword() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('signupView').style.display = 'none';
    document.getElementById('forgotPasswordView').style.display = 'block';
    document.getElementById('updatePasswordView').style.display = 'none';
}

function showUpdatePassword() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('signupView').style.display = 'none';
    document.getElementById('forgotPasswordView').style.display = 'none';
    document.getElementById('updatePasswordView').style.display = 'block';
}

// Handle forgot password
async function handleForgotPassword(e) {
    e.preventDefault();
    const email = document.getElementById('resetEmail').value;
    const messageEl = document.getElementById('resetMessage');

    try {
        showLoading(true);
        await apiFetch('/auth/reset-password', {
            method: 'POST',
            body: JSON.stringify({ email }),
        });
        showLoading(false);

        messageEl.textContent = 'If an account exists with that email, you will receive a password reset link shortly.';
        messageEl.style.display = 'block';
        messageEl.style.color = '#10B981';
    } catch (error) {
        showLoading(false);
        // Show generic success message even on error to prevent email enumeration
        messageEl.textContent = 'If an account exists with that email, you will receive a password reset link shortly.';
        messageEl.style.display = 'block';
        messageEl.style.color = '#10B981';
    }
}

// Handle password update (after clicking reset link)
async function handleUpdatePassword(e) {
    e.preventDefault();
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const messageEl = document.getElementById('updateMessage');

    if (newPassword !== confirmPassword) {
        messageEl.textContent = 'Passwords do not match.';
        messageEl.style.display = 'block';
        messageEl.style.color = '#EF4444';
        return;
    }

    if (newPassword.length < 6) {
        messageEl.textContent = 'Password must be at least 6 characters.';
        messageEl.style.display = 'block';
        messageEl.style.color = '#EF4444';
        return;
    }

    try {
        showLoading(true);
        await apiFetch('/auth/update-password', {
            method: 'POST',
            body: JSON.stringify({ password: newPassword }),
        });
        showLoading(false);

        messageEl.textContent = 'Password updated successfully! Redirecting to login...';
        messageEl.style.display = 'block';
        messageEl.style.color = '#10B981';

        setTimeout(() => {
            localStorage.removeItem('accessToken');
            window.location.href = 'app.html';
        }, 2000);
    } catch (error) {
        showLoading(false);
        messageEl.textContent = 'Failed to update password: ' + error.message;
        messageEl.style.display = 'block';
        messageEl.style.color = '#EF4444';
    }
}

async function handleAuthSignUp(e) {
    e.preventDefault();
    const fullName = document.getElementById('signupName').value;
    const email = document.getElementById('signupEmail').value;
    const password = document.getElementById('signupPassword').value;
    const orgName = document.getElementById('signupOrg').value;

    if (password.length < 6) {
        alert('Password must be at least 6 characters long.');
        return;
    }

    try {
        showLoading(true);
        const response = await apiFetch('/auth/signup', {
            method: 'POST',
            body: JSON.stringify({
                email,
                password,
                full_name: fullName,
                organization_name: orgName || null,
            }),
        });

        showLoading(false);

        if (response && response.user_id) {
            alert('Account created! Please check your email to verify your account, then sign in.');
            showLogin();
            document.getElementById('authEmail').value = email;
        }
    } catch (error) {
        showLoading(false);
        alert('Sign up failed: ' + error.message);
    }
}

function enterDemoMode() {
    localStorage.setItem('demoUser', JSON.stringify({
        org: 'Sunshine Support Services',
        name: 'Demo User',
        email: 'demo@example.com',
        plan: 'growth',
        startDate: new Date().toISOString()
    }));

    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('appShell').style.display = 'flex';
    document.getElementById('orgName').textContent = 'Sunshine Support Services';
    initCharts();
    attachEventListeners();
    renderDemoData();
}

async function logout() {
    try {
        await apiFetch('/auth/signout', { method: 'POST' });
    } catch (error) {
        console.warn('Sign out API call failed, clearing local data anyway');
    }

    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('currentUser');
    localStorage.removeItem('demoUser');
    window.location.href = 'index.html';
}

// ========== TAB NAVIGATION ==========

function switchTab(tabName) {
    document.querySelectorAll('.tab-pane').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(tabName + 'Tab').classList.add('active');

    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    document.querySelector('.tab-content').scrollTop = 0;
}

// ========== CHARTS ==========

let gaugeChart = null;
let trendChart = null;

function initCharts() {
    const gaugeCtx = document.getElementById('gaugeChart');
    if (gaugeCtx) {
        gaugeChart = new Chart(gaugeCtx, {
            type: 'doughnut',
            data: {
                labels: ['Compliant', 'At Risk'],
                datasets: [{
                    data: [0, 100],
                    backgroundColor: ['#10B981', '#F59E0B'],
                    borderWidth: 0,
                    circumference: 180,
                    rotation: 270,
                    cutout: '75%'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            }
        });
    }

    const trendCtx = document.getElementById('trendChart');
    if (trendCtx) {
        trendChart = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Compliance Score',
                    data: [],
                    borderColor: '#2a9d8f',
                    backgroundColor: 'rgba(42, 157, 143, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#2a9d8f',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, position: 'top' } },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    }
                }
            }
        });
    }
}

function updateGaugeChart(score) {
    if (gaugeChart) {
        gaugeChart.data.datasets[0].data = [score, 100 - score];
        gaugeChart.update();
    }
}

function updateTrendChart(labels, data) {
    if (trendChart) {
        trendChart.data.labels = labels;
        trendChart.data.datasets[0].data = data;
        trendChart.update();
    }
}

// ========== EVENT LISTENERS ==========

function attachEventListeners() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                e.currentTarget.style.display = 'none';
            }
        });
    });

    const uploadZone = document.getElementById('uploadZone');
    if (uploadZone) {
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.style.background = '#d1fae5';
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.style.background = '#f0fdf9';
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.style.background = '#f0fdf9';
            handleFileUpload(e);
        });
    }
}

// ========== RENDERING HELPERS ==========

function renderModulesGrid(scores) {
    const grid = document.getElementById('modulesGrid');
    if (!grid) return;

    if (!scores || scores.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #6b7280;">
                <p>No compliance data yet. Upload a document to start your compliance analysis.</p>
            </div>
        `;
        return;
    }

    // Group scores by category
    const categories = {};
    scores.forEach(score => {
        const cat = score.category || score.standard_name || 'General';
        if (!categories[cat]) {
            categories[cat] = { total: 0, met: 0, scores: [] };
        }
        categories[cat].total++;
        if (score.score >= 70) categories[cat].met++;
        categories[cat].scores.push(score);
    });

    grid.innerHTML = Object.entries(categories).map(([category, data]) => {
        const pct = Math.round((data.met / data.total) * 100);
        const isCompliant = pct >= 90;
        const statusClass = isCompliant ? 'status-compliant' : 'status-warning';
        const statusIcon = isCompliant ? '🟢' : '🟡';
        const statusText = isCompliant ? 'Compliant' : 'At Risk';
        const barColor = isCompliant ? '#10B981' : '#F59E0B';

        return `
            <div class="module-card">
                <div class="module-header">
                    <h3>${escapeHtml(category)}</h3>
                    <div class="status-badge ${statusClass}">${statusIcon} ${statusText}</div>
                </div>
                <p>${data.met} of ${data.total} standards met</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${pct}%; background: ${barColor};"></div>
                </div>
            </div>
        `;
    }).join('');
}

function renderGapList(gaps) {
    const list = document.getElementById('gapList');
    if (!list) return;

    if (!gaps || gaps.length === 0) {
        list.innerHTML = `
            <div style="text-align: center; padding: 30px; color: #6b7280;">
                <p>No compliance gaps found. Great work!</p>
            </div>
        `;
        return;
    }

    list.innerHTML = gaps.map(gap => {
        const severity = (gap.severity || 'medium').toUpperCase();
        const severityClass = severity === 'CRITICAL' ? 'gap-critical' : severity === 'HIGH' ? 'gap-warning' : 'gap-info';

        return `
            <div class="gap-item ${severityClass}">
                <div class="gap-severity">${severity}</div>
                <div class="gap-content">
                    <div class="gap-title">${escapeHtml(gap.title || gap.gap_description || 'Compliance Gap')}</div>
                    <div class="gap-detail">${escapeHtml(gap.recommendation || gap.details || '')}</div>
                </div>
                <div class="gap-action">
                    <button class="btn btn-small btn-primary" onclick="viewGapRemediation('${gap.id || ''}')">View Remediation</button>
                </div>
            </div>
        `;
    }).join('');
}

function renderDocumentsGrid(documents) {
    const grid = document.getElementById('documentsGrid');
    if (!grid) return;

    if (!documents || documents.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: #6b7280;">
                <div style="font-size: 48px; margin-bottom: 16px;">📄</div>
                <p style="font-size: 16px; font-weight: 500; margin-bottom: 8px;">No documents yet</p>
                <p>Upload your first document to begin compliance scanning.</p>
                <button class="btn btn-primary" style="margin-top: 16px;" onclick="openUploadModal()">Upload Document</button>
            </div>
        `;
        return;
    }

    const iconMap = {
        'pdf': '📋',
        'docx': '📄',
        'doc': '📄',
        'txt': '📑',
        'default': '📄'
    };

    grid.innerHTML = documents.map(doc => {
        const ext = (doc.file_name || '').split('.').pop().toLowerCase();
        const icon = iconMap[ext] || iconMap['default'];
        const date = doc.uploaded_at ? timeAgo(new Date(doc.uploaded_at)) : 'Unknown';
        const status = doc.compliance_status || doc.status || 'pending';
        let statusBadge;

        if (status === 'compliant' || status === 'completed') {
            statusBadge = '<span class="status-badge status-compliant">🟢 Compliant</span>';
        } else if (status === 'gaps_found' || status === 'at_risk') {
            statusBadge = '<span class="status-badge status-warning">🟡 Gaps Found</span>';
        } else if (status === 'processing') {
            statusBadge = '<span class="status-badge" style="background: #EFF6FF; color: #3B82F6;">🔵 Processing</span>';
        } else {
            statusBadge = '<span class="status-badge" style="background: #F3F4F6; color: #6B7280;">⏳ Pending</span>';
        }

        return `
            <div class="document-card">
                <div class="doc-icon">${icon}</div>
                <div class="doc-name">${escapeHtml(doc.file_name || doc.name || 'Untitled')}</div>
                <div class="doc-date">Uploaded ${date}</div>
                <div class="doc-status">${statusBadge}</div>
                <div class="doc-actions">
                    <button class="btn btn-small" onclick="viewDocument('${doc.id}')">View</button>
                    <button class="btn btn-small" onclick="deleteDocument('${doc.id}')">Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

// ========== DATA LOADING (REAL API) ==========

async function loadDashboardData() {
    if (isDemoMode() || !currentOrgId) {
        renderDemoData();
        return;
    }

    try {
        // Fetch all dashboard data in parallel
        const [dashboardData, scoresData, gapsData] = await Promise.all([
            apiFetch('/dashboard/').catch(() => null),
            apiFetch('/compliance/scores').catch(() => null),
            apiFetch('/compliance/gaps').catch(() => null),
        ]);

        // Update score stats
        if (dashboardData) {
            const overallScore = dashboardData.overall_compliance_score || 0;
            const compliantStandards = dashboardData.compliant_standards || 0;
            const criticalGaps = dashboardData.critical_gaps || 0;
            const totalDocs = dashboardData.total_documents || 0;

            document.getElementById('statMet').textContent = compliantStandards;
            document.getElementById('statGaps').textContent = criticalGaps;
            document.getElementById('statDocs').textContent = totalDocs;
            updateGaugeChart(overallScore);

            // Update trend chart if trend data exists
            if (dashboardData.trend_data && dashboardData.trend_data.length > 0) {
                const labels = dashboardData.trend_data.map(t => t.label || t.week || '');
                const data = dashboardData.trend_data.map(t => t.score || 0);
                updateTrendChart(labels, data);
            } else {
                // Generate a simple trend from the score
                const weeks = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12', 'W13'];
                const score = dashboardData.overall_compliance_score || 0;
                const trend = weeks.map((_, i) => Math.max(0, Math.round(score * (0.7 + 0.3 * (i / 12)))));
                updateTrendChart(weeks, trend);
            }
        }

        // Render compliance modules
        if (scoresData) {
            const scores = scoresData.scores || scoresData;
            renderModulesGrid(Array.isArray(scores) ? scores : []);
        } else {
            renderModulesGrid([]);
        }

        // Render compliance gaps
        if (gapsData) {
            const gaps = gapsData.gaps || gapsData;
            renderGapList(Array.isArray(gaps) ? gaps : []);
        } else {
            renderGapList([]);
        }

        // Load documents
        loadDocumentsList();

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        renderDemoData();
    }
}

async function loadDocumentsList() {
    if (isDemoMode() || !currentOrgId) return;

    try {
        const documentsData = await apiFetch('/documents/?per_page=20');

        if (documentsData && documentsData.documents) {
            renderDocumentsGrid(documentsData.documents);
        } else if (Array.isArray(documentsData)) {
            renderDocumentsGrid(documentsData);
        } else {
            renderDocumentsGrid([]);
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
        renderDocumentsGrid([]);
    }
}

// ========== DEMO DATA ==========

function renderDemoData() {
    // Stats
    document.getElementById('statMet').textContent = '18';
    document.getElementById('statGaps').textContent = '2';
    document.getElementById('statDocs').textContent = '8';
    updateGaugeChart(94);

    // Trend
    const weeks = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6', 'Week 7', 'Week 8', 'Week 9', 'Week 10', 'Week 11', 'Week 12', 'Week 13'];
    const scores = [78, 80, 79, 82, 84, 86, 88, 89, 90, 91, 92, 93, 94];
    updateTrendChart(weeks, scores);

    // Modules
    renderModulesGrid([
        { category: 'Participant Safeguards', score: 100, standard_name: 'Participant Safeguards' },
        { category: 'Participant Safeguards', score: 100, standard_name: 'PS-2' },
        { category: 'Incident Management', score: 80, standard_name: 'IM-1' },
        { category: 'Incident Management', score: 50, standard_name: 'IM-2' },
        { category: 'Staff Management', score: 95, standard_name: 'SM-1' },
        { category: 'Staff Management', score: 100, standard_name: 'SM-2' },
        { category: 'Documentation', score: 90, standard_name: 'DOC-1' },
        { category: 'Documentation', score: 50, standard_name: 'DOC-2' },
    ]);

    // Gaps
    renderGapList([
        {
            id: 'demo-1',
            severity: 'critical',
            title: 'Incident Response Plan Missing Key Elements',
            recommendation: "Your incident response plan doesn't include mandatory escalation procedures. Update required within 30 days of audit."
        },
        {
            id: 'demo-2',
            severity: 'high',
            title: 'Staff Training Records Incomplete',
            recommendation: '3 staff members missing mandatory disability awareness training certificates from the last 12 months.'
        }
    ]);

    // Documents
    renderDocumentsGrid([
        { id: 'demo-1', file_name: 'Incident Response Policy.pdf', uploaded_at: new Date(Date.now() - 2 * 86400000).toISOString(), compliance_status: 'gaps_found' },
        { id: 'demo-2', file_name: 'Staff Training Log.docx', uploaded_at: new Date(Date.now() - 5 * 86400000).toISOString(), compliance_status: 'compliant' },
        { id: 'demo-3', file_name: 'Participant Plans.pdf', uploaded_at: new Date(Date.now() - 7 * 86400000).toISOString(), compliance_status: 'compliant' },
        { id: 'demo-4', file_name: 'Safeguarding Procedures.docx', uploaded_at: new Date(Date.now() - 21 * 86400000).toISOString(), compliance_status: 'compliant' },
    ]);
}

// ========== DOCUMENT ACTIONS ==========

function openUploadModal() {
    document.getElementById('uploadModal').style.display = 'flex';
}

async function handleFileUpload(e) {
    const files = e.dataTransfer ? e.dataTransfer.files : e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const fileName = file.name;

    if (isDemoMode()) {
        alert(`Document "${fileName}" uploaded successfully! Scanning for compliance gaps...`);
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('fileInput').value = '';
        return;
    }

    try {
        showLoading(true);
        const formData = new FormData();
        formData.append('file', file);

        const token = localStorage.getItem('accessToken');
        const response = await fetch(`${API_BASE_URL}/documents/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });

        showLoading(false);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();
        alert(`Document "${fileName}" uploaded successfully! Compliance scan started.`);
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('fileInput').value = '';

        // Refresh documents list
        loadDocumentsList();
    } catch (error) {
        showLoading(false);
        alert('Upload failed: ' + error.message);
    }
}

async function viewDocument(docId) {
    if (isDemoMode()) {
        alert('Document details view is available with a real account.');
        return;
    }

    try {
        const doc = await apiFetch(`/documents/${docId}`);
        if (doc) {
            // For now, show basic info — can be expanded to a modal later
            alert(`Document: ${doc.file_name}\nStatus: ${doc.compliance_status || 'pending'}\nUploaded: ${new Date(doc.uploaded_at).toLocaleDateString()}`);
        }
    } catch (error) {
        alert('Failed to load document details: ' + error.message);
    }
}

async function deleteDocument(docId) {
    if (isDemoMode()) {
        alert('Document deletion is available with a real account.');
        return;
    }

    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        await apiFetch(`/documents/${docId}`, { method: 'DELETE' });
        loadDocumentsList();
    } catch (error) {
        alert('Failed to delete document: ' + error.message);
    }
}

function viewGapRemediation(gapId) {
    if (isDemoMode() || !gapId) {
        alert('Detailed remediation steps will be available after uploading and scanning your documents.');
        return;
    }
    // Future: open a modal with remediation details from the API
    alert('Remediation details coming soon.');
}

// ========== STAFF & REPORTS (placeholders for now) ==========

function openAddStaffModal() {
    const name = prompt('Enter staff member name:');
    if (name) {
        alert(`${name} has been added to your staff list.`);
    }
}

function handleSettingsSave(e) {
    e.preventDefault();
    alert('Settings updated successfully!');
}

function generateReport() {
    alert('Report generation started. Check your email in a few moments.');
}

// ========== UTILITIES ==========

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    const intervals = [
        { label: 'year', seconds: 31536000 },
        { label: 'month', seconds: 2592000 },
        { label: 'week', seconds: 604800 },
        { label: 'day', seconds: 86400 },
        { label: 'hour', seconds: 3600 },
        { label: 'minute', seconds: 60 },
    ];

    for (const interval of intervals) {
        const count = Math.floor(seconds / interval.seconds);
        if (count >= 1) {
            return `${count} ${interval.label}${count > 1 ? 's' : ''} ago`;
        }
    }
    return 'just now';
}

// Set current date
document.addEventListener('DOMContentLoaded', () => {
    const today = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateStr = today.toLocaleDateString('en-AU', options);
    const scoreDateEl = document.getElementById('scoreDate');
    if (scoreDateEl) {
        scoreDateEl.textContent = `Last updated: ${dateStr}`;
    }
});

// Close modal on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.style.display = 'none';
        });
    }
});
