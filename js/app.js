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

// Toast notification (replaces alert() throughout the app)
function showToast(message, type = 'success') {
    const colors = {
        success: { bg: '#d1fae5', text: '#065f46', border: '#10B981' },
        error:   { bg: '#fee2e2', text: '#991b1b', border: '#EF4444' },
        info:    { bg: '#eff6ff', text: '#1e40af', border: '#3B82F6' },
    };
    const c = colors[type] || colors.info;
    const toast = document.createElement('div');
    toast.style.cssText = `position:fixed;top:20px;right:20px;padding:14px 20px;border-radius:8px;font-size:14px;font-weight:500;z-index:10000;max-width:380px;box-shadow:0 4px 12px rgba(0,0,0,0.15);background:${c.bg};color:${c.text};border-left:4px solid ${c.border};opacity:1;transition:opacity 0.3s ease;`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4500);
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

    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

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
        // Show dashboard immediately — don't block on /auth/me
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('appShell').style.display = 'flex';

        // Restore cached user info instantly if available
        const cachedUser = localStorage.getItem('currentUser');
        if (cachedUser) {
            try {
                const parsed = JSON.parse(cachedUser);
                currentUser = parsed;
                currentOrgId = parsed.organization_id;
                if (parsed.organization && parsed.organization.name) {
                    document.getElementById('orgName').textContent = parsed.organization.name;
                }
                if (parsed.full_name) {
                    const initials = parsed.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
                    const avatar = document.querySelector('.navbar-right div[title="Profile"]');
                    if (avatar) avatar.textContent = initials;
                }
            } catch (_) {}
        }

        initCharts();
        attachEventListeners();
        loadDashboardData();

        // Refresh user data in background (non-blocking)
        apiFetch('/auth/me').then(userData => {
            if (userData) {
                currentUser = userData;
                currentOrgId = userData.organization_id;
                localStorage.setItem('currentUser', JSON.stringify(userData));

                if (userData.organization && userData.organization.name) {
                    document.getElementById('orgName').textContent = userData.organization.name;
                }
                if (userData.full_name) {
                    const initials = userData.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
                    const avatar = document.querySelector('.navbar-right div[title="Profile"]');
                    if (avatar) avatar.textContent = initials;
                }
            }
        }).catch(error => {
            console.error('Auth refresh failed:', error);
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            localStorage.removeItem('currentUser');
            document.getElementById('authScreen').style.display = 'flex';
            document.getElementById('appShell').style.display = 'none';
        });
    }
});

// ========== AUTH FUNCTIONS ==========

async function handleAuthLogin(e) {
    e.preventDefault();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;

    const btn = e.target.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Signing in…'; }

    try {
        const response = await apiFetch('/auth/signin', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });

        if (response && response.access_token) {
            localStorage.setItem('accessToken', response.access_token);
            localStorage.setItem('refreshToken', response.refresh_token);
            localStorage.setItem('currentUser', JSON.stringify(response.user));
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
    } catch (error) {
        showToast('Login failed: ' + error.message, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Sign In'; }
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
        showToast('Password must be at least 6 characters long.', 'error');
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
            showToast('Account created! Please check your email to verify your account, then sign in.', 'success');
            showLogin();
            document.getElementById('authEmail').value = email;
        }
    } catch (error) {
        showLoading(false);
        showToast('Sign up failed: ' + error.message, 'error');
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

    if (tabName === 'clients') loadClientsList();
    if (tabName === 'staff') loadStaffList();
    if (tabName === 'settings') loadSettingsTab();
    if (tabName === 'reports') loadReportsTab();
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

// ---------------------------------------------------------------------------
// Document type → human-readable label
// Handles all NDIS audit document types across Core, Module 1, and Module 2/2A.
// Falls back to capitalising the snake_case string for any unmapped type.
// ---------------------------------------------------------------------------
const DOCUMENT_TYPE_LABELS = {
    // Core — Governance
    business_continuity_plan:           'Business Continuity Plan',
    strategic_operational_plan:         'Strategic & Operational Plan',
    conflict_of_interest_register:      'Conflict of Interest Register',
    continuous_improvement_plan:        'Continuous Improvement Plan',
    continuous_improvement_register:    'Continuous Improvement Register',
    internal_audit_schedule:            'Internal Audit Schedule',
    organisational_chart:               'Organisational Chart',
    quality_improvement_plan:           'Quality Improvement Plan',
    swot_analysis:                      'SWOT Analysis',
    // Core — Business / Risk Forms
    emergency_management_plan:          'Emergency Management Plan',
    emergency_evacuation_plan:          'Emergency Evacuation Plan',
    risk_assessment:                    'Risk Assessment',
    risk_management_plan:               'Risk Management Plan',
    risk_register:                      'Risk Register',
    workplace_inspection_checklist:     'Workplace Inspection Checklist',
    whs_inspection_checklist:           'WHS Inspection Checklist',
    meeting_minutes:                    'Meeting Minutes',
    // Core — Incident Management
    incident_report:                    'Incident Report',
    incident_register:                  'Incident Register',
    incident_investigation_form:        'Incident Investigation Form',
    reportable_incident_24hr:           'Reportable Incident (24-hr)',
    reportable_incident_5day:           'Reportable Incident (5-day)',
    // Core — Complaints & Feedback
    complaint_form:                     'Complaint Form',
    complaint_form_easy_english:        'Complaint Form (Easy English)',
    complaints_register:                'Complaints Register',
    complaints_process_checklist:       'Complaints Process Checklist',
    feedback_form:                      'Feedback Form',
    // Core — Participant Forms
    consent_form:                       'Consent Form',
    consent_form_easy_read:             'Consent Form (Easy Read)',
    intake_form:                        'Intake Form',
    intake_checklist:                   'Intake Checklist',
    referral_form:                      'Referral Form',
    service_agreement:                  'Service Agreement',
    service_agreement_easy_read:        'Service Agreement (Easy Read)',
    support_plan:                       'Support Plan',
    support_plan_easy_read:             'Support Plan (Easy Read)',
    support_plan_progress_report:       'Support Plan Progress Report',
    support_plan_review_register:       'Support Plan Review Register',
    participant_support_plan:           'Participant Support Plan',
    schedule_of_supports:               'Schedule of Supports',
    participant_handbook:               'Participant Handbook',
    welcome_pack_easy_read:             'Welcome Pack (Easy Read)',
    exit_form:                          'Exit Form',
    exit_transition_plan:               'Exit & Transition Plan',
    satisfaction_survey:                'Satisfaction Survey',
    acknowledgement_form:               'Acknowledgement Form',
    refusal_to_consent:                 'Refusal to Consent',
    money_handling_consent:             'Money Handling Consent',
    personal_emergency_plan:            'Personal Emergency Plan',
    safe_environment_risk_assessment:   'Safe Environment Risk Assessment',
    advocate_authority_form:            'Advocate Authority Form',
    opt_out_audit_form:                 'Opt-Out Audit Form',
    privacy_statement:                  'Privacy Statement',
    privacy_policy:                     'Privacy Policy',
    progress_notes:                     'Progress Notes',
    client_charter:                     'Client Charter',
    // Core — Staff / HR
    staff_induction_checklist:          'Staff Induction Checklist',
    staff_performance_review:           'Staff Performance Review',
    staff_training_log:                 'Staff Training Log',
    individual_training_register:       'Individual Training Register',
    training_development_book:          'Training & Development Book',
    supervision_record:                 'Supervision Record',
    staff_handbook:                     'Staff Handbook',
    personnel_file_setup:               'Personnel File Setup',
    privacy_confidentiality_agreement:  'Privacy & Confidentiality Agreement',
    conflict_of_interest_declaration:   'Conflict of Interest Declaration',
    delegation_of_authority:            'Delegation of Authority',
    worker_screening_check:             'Worker Screening Check',
    first_aid_certificate:              'First Aid Certificate',
    ndis_module_training:               'NDIS Module Training',
    // Core — Medication Management
    medication_administration_chart:    'Medication Administration Chart',
    medication_care_plan_consent:       'Medication Care Plan & Consent',
    medication_incident_report:         'Medication Incident Report',
    medication_management_plan:         'Medication Management Plan',
    medication_risk_assessment:         'Medication Risk Assessment',
    medication_phone_order:             'Medication Phone Order',
    prn_medication_record:              'PRN Medication Record',
    medication_register:                'Medication Register',
    // Core — Position Descriptions
    support_worker_pd:                  'Support Worker PD',
    team_leader_pd:                     'Team Leader PD',
    clinical_nurse_pd:                  'Clinical Nurse PD',
    registered_nurse_pd:                'Registered Nurse PD',
    management_pd:                      'Management PD',
    // Module 1 — Enteral Feeding
    enteral_feeding_care_plan:          'Enteral Feeding Care Plan',
    enteral_feeding_consent:            'Enteral Feeding Consent',
    enteral_feeding_assessment:         'Enteral Feeding Assessment',
    enteral_feeding_competency:         'Enteral Feeding Competency',
    fluid_balance_chart:                'Fluid Balance Chart',
    stoma_care_plan:                    'Stoma Care Plan',
    weight_chart:                       'Weight Chart',
    // Module 1 — Wound Management
    wound_assessment:                   'Wound Assessment',
    wound_management_care_plan:         'Wound Management Care Plan',
    wound_management_consent:           'Wound Management Consent',
    wound_progress_report:              'Wound Progress Report',
    // Module 1 — Catheter Management
    catheter_care_plan:                 'Catheter Care Plan',
    catheter_consent:                   'Catheter Consent',
    catheter_competency:                'Catheter Competency',
    // Module 1 — Subcutaneous Injections
    subcutaneous_care_plan:             'Subcutaneous Care Plan',
    subcutaneous_consent:               'Subcutaneous Consent',
    subcutaneous_medication_sheet:      'Subcutaneous Medication Sheet',
    subcutaneous_assessment:            'Subcutaneous Assessment',
    // Module 1 — Tracheostomy
    tracheostomy_care_plan:             'Tracheostomy Care Plan',
    tracheostomy_consent:               'Tracheostomy Consent',
    tracheostomy_competency:            'Tracheostomy Competency',
    // Module 1 — Ventilator
    ventilator_care_plan:               'Ventilator Care Plan',
    ventilator_consent:                 'Ventilator Consent',
    ventilator_competency:              'Ventilator Competency',
    // Module 1 — Complex Bowel
    complex_bowel_care_plan:            'Complex Bowel Care Plan',
    complex_bowel_consent:              'Complex Bowel Consent',
    complex_bowel_competency:           'Complex Bowel Competency',
    // Module 1 — Dysphagia
    dysphagia_care_plan:                'Dysphagia Care Plan',
    dysphagia_consent:                  'Dysphagia Consent',
    dysphagia_assessment:               'Dysphagia Assessment',
    // Module 1 — Epilepsy
    epilepsy_seizure_management_plan:   'Epilepsy Seizure Management Plan',
    epilepsy_consent:                   'Epilepsy Consent',
    epilepsy_competency:                'Epilepsy Competency',
    // Module 2 / 2A — Behaviour Support
    behaviour_support_plan:                 'Behaviour Support Plan',
    interim_behaviour_support_plan:         'Interim Behaviour Support Plan',
    reviewed_bsp_register:                  'Reviewed BSP Register',
    restrictive_practices_monthly_report:   'Restrictive Practices Monthly Report',
    legal_restraints_competency:            'Legal Restraints Competency',
    clinical_supervision_record:            'Clinical Supervision Record',
    reportable_incident_24hr_bsp:           'Reportable Incident 24hr (BSP)',
    reportable_incident_5day_bsp:           'Reportable Incident 5-day (BSP)',
    staff_training_needs_assessment:        'Staff Training Needs Assessment',
    ongoing_professional_development_plan:  'Ongoing Professional Development Plan',
    // Fallback
    unknown: 'Unclassified Document',
};

/**
 * Returns a human-readable label for an NDIS document type string.
 * Falls back to title-casing the snake_case value for unmapped types.
 * @param {string|null|undefined} docType
 * @returns {string}
 */
function formatDocumentType(docType) {
    if (!docType || docType === 'unknown') return 'Unclassified';
    if (DOCUMENT_TYPE_LABELS[docType]) return DOCUMENT_TYPE_LABELS[docType];
    // Fallback: convert snake_case to Title Case
    return docType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
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
        const filename = doc.original_filename || doc.file_name || doc.name || 'Untitled';
        const ext = filename.split('.').pop().toLowerCase();
        const icon = iconMap[ext] || iconMap['default'];
        const date = (doc.created_at || doc.uploaded_at) ? timeAgo(new Date(doc.created_at || doc.uploaded_at)) : 'Unknown';
        const status = doc.processing_status || doc.compliance_status || doc.status || 'pending';
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

        const docTypeLabel = doc.document_type
            ? formatDocumentType(doc.document_type)
            : null;

        return `
            <div class="document-card">
                <div class="doc-icon">${icon}</div>
                <div class="doc-name">${escapeHtml(filename)}</div>
                ${docTypeLabel ? `<div class="doc-type" title="${escapeHtml(doc.document_type)}">${escapeHtml(docTypeLabel)}</div>` : ''}
                <div class="doc-date">Uploaded ${date}</div>
                <div class="doc-status">${statusBadge}</div>
                <div class="doc-actions">
                    <button class="btn btn-small" onclick="openDocumentFile('${doc.id}')" title="Open in new tab">Open</button>
                    <button class="btn btn-small" onclick="viewDocument('${doc.id}')">Details</button>
                    <button class="btn btn-small" onclick="deleteDocument('${doc.id}')" style="color:#EF4444;">Delete</button>
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

            // Audit countdown
            const daysWrap = document.getElementById('statAuditWrap');
            const daysEl = document.getElementById('statAudit');
            if (dashboardData.days_until_audit !== null && dashboardData.days_until_audit !== undefined) {
                const d = dashboardData.days_until_audit;
                if (daysWrap) daysWrap.style.display = '';
                if (daysEl) {
                    daysEl.textContent = d;
                    daysEl.className = 'stat-value' + (d <= 30 ? ' danger' : d <= 90 ? ' warning' : '');
                }
            }

            // Onboarding checklist
            updateOnboardingChecklist(dashboardData);

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

// ========== ONBOARDING CHECKLIST ==========

function updateOnboardingChecklist(dashboardData) {
    const checklist = document.getElementById('onboardingChecklist');
    if (!checklist) return;

    const hasDocs = (dashboardData.total_documents || 0) > 0;
    const hasScore = (dashboardData.overall_compliance_score || 0) > 0;
    const hasAuditDate = !!dashboardData.audit_date;

    // Show checklist only when the account looks brand-new (no docs, no score)
    if (hasDocs && hasScore) {
        checklist.style.display = 'none';
        return;
    }
    checklist.style.display = '';

    // Mark steps complete based on what we know from the dashboard response
    const steps = {
        'step-org': hasAuditDate,
        'step-doc': hasDocs,
        'step-client': false, // can't know from dashboard — always unchecked
        'step-staff': false,
    };
    Object.entries(steps).forEach(([id, done]) => {
        const icon = document.getElementById('stepIcon-' + id.replace('step-', ''));
        if (icon) icon.textContent = done ? '✅' : '⬜';
        const row = document.getElementById(id);
        if (row) row.style.opacity = done ? '0.6' : '1';
    });
}

// ========== NOTIFICATIONS ==========

let _notificationsLoaded = false;

function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notificationDropdown');
    if (!dropdown) return;
    const isOpen = dropdown.style.display !== 'none';
    dropdown.style.display = isOpen ? 'none' : 'block';
    if (!isOpen && !_notificationsLoaded) loadNotifications();
    // Close on outside click
    if (!isOpen) {
        setTimeout(() => {
            document.addEventListener('click', function closeDropdown(e) {
                const wrap = document.getElementById('notificationBellWrap');
                if (wrap && !wrap.contains(e.target)) {
                    dropdown.style.display = 'none';
                    document.removeEventListener('click', closeDropdown);
                }
            });
        }, 0);
    }
}

async function loadNotifications() {
    const list = document.getElementById('notificationList');
    const badge = document.getElementById('notificationBadge');
    if (!list) return;

    if (isDemoMode()) {
        const items = [
            { label: 'John Smith — NDIS plan expires in 18 days', urgent: true },
            { label: 'Policy Manual — review due in 25 days', urgent: true },
            { label: 'Jane Doe — NDIS plan expires in 45 days', urgent: false },
        ];
        _renderNotificationItems(list, badge, items);
        _notificationsLoaded = true;
        return;
    }

    if (!currentOrgId) {
        list.innerHTML = '<p style="padding:16px;text-align:center;color:#9ca3af;font-size:13px;">Sign in to view alerts.</p>';
        return;
    }

    try {
        const today = new Date();
        const in90 = new Date(today.getTime() + 90 * 86400000).toISOString().split('T')[0];

        const [clientsResp, docsResp] = await Promise.all([
            apiFetch('/clients/?per_page=100').catch(() => null),
            apiFetch('/documents/?per_page=100').catch(() => null),
        ]);

        const items = [];

        // Client plan expiry
        const clients = (clientsResp && (clientsResp.clients || clientsResp)) || [];
        (Array.isArray(clients) ? clients : []).forEach(c => {
            if (!c.current_plan_end_date) return;
            const expiry = new Date(c.current_plan_end_date);
            const daysLeft = Math.round((expiry - today) / 86400000);
            if (daysLeft <= 90 && daysLeft >= 0) {
                const name = `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Participant';
                items.push({ label: `${name} — NDIS plan expires in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}`, urgent: daysLeft <= 30 });
            }
        });

        // Document review due
        const docs = (docsResp && (docsResp.documents || docsResp)) || [];
        (Array.isArray(docs) ? docs : []).forEach(d => {
            if (!d.review_due_date) return;
            const due = new Date(d.review_due_date);
            const daysLeft = Math.round((due - today) / 86400000);
            if (daysLeft <= 90 && daysLeft >= 0) {
                const name = d.original_filename || d.document_type || 'Document';
                items.push({ label: `${name} — review due in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}`, urgent: daysLeft <= 30 });
            }
        });

        items.sort((a, b) => (b.urgent ? 1 : 0) - (a.urgent ? 1 : 0));
        _renderNotificationItems(list, badge, items);
        _notificationsLoaded = true;
    } catch (error) {
        list.innerHTML = '<p style="padding:16px;text-align:center;color:#9ca3af;font-size:13px;">Could not load alerts.</p>';
    }
}

function _renderNotificationItems(list, badge, items) {
    if (items.length === 0) {
        list.innerHTML = '<p style="padding:16px;text-align:center;color:#9ca3af;font-size:13px;">No upcoming alerts.</p>';
        if (badge) badge.style.display = 'none';
        return;
    }
    const urgentCount = items.filter(i => i.urgent).length;
    if (badge) {
        badge.textContent = urgentCount || items.length;
        badge.style.display = '';
    }
    list.innerHTML = items.map(item => `
        <div style="padding:10px 16px;border-bottom:1px solid #f9fafb;display:flex;align-items:start;gap:10px;">
            <span style="font-size:16px;flex-shrink:0;">${item.urgent ? '🔴' : '🟡'}</span>
            <span style="font-size:13px;color:#374151;line-height:1.4;">${escapeHtml(item.label)}</span>
        </div>
    `).join('');
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

    // Clients
    renderDemoClients();
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
        showToast(`"${fileName}" uploaded. Scanning for compliance gaps...`);
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

        await response.json();
        showToast(`"${fileName}" uploaded. Compliance scan started.`);
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('fileInput').value = '';

        // Refresh documents list
        loadDocumentsList();
    } catch (error) {
        showLoading(false);
        showToast('Upload failed: ' + error.message, 'error');
    }
}

async function viewDocument(docId) {
    if (isDemoMode()) {
        showToast('Document viewing is available with a real account.', 'info');
        return;
    }

    try {
        // Fetch document detail and compliance scores in parallel
        const [doc, scoresResp] = await Promise.all([
            apiFetch(`/documents/${docId}`),
            apiFetch(`/compliance/scores?document_id=${docId}`).catch(() => null),
        ]);

        if (!doc) {
            showToast('Document not found.', 'error');
            return;
        }

        const scores = (scoresResp && scoresResp.scores) ? scoresResp.scores : [];
        const statusLabel = doc.processing_status || 'pending';
        const docTypeLabel = doc.document_type ? formatDocumentType(doc.document_type) : 'Unclassified';

        // Build scores HTML
        let scoresHtml = '';
        if (scores.length > 0) {
            scoresHtml = `
                <h4 style="margin: 16px 0 8px; font-size: 14px; font-weight: 600;">Compliance Scores</h4>
                <div style="max-height: 200px; overflow-y: auto;">
                    ${scores.map(s => {
                        const pct = Math.round(s.score || 0); // scores stored as 0–100, no ×100 needed
                        const color = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444';
                        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f3f4f6;">
                            <span style="font-size:13px;">${escapeHtml(s.standard_name || s.standard_id || 'Standard')}</span>
                            <span style="font-weight:600;color:${color};">${pct}%</span>
                        </div>`;
                    }).join('')}
                </div>
            `;
        } else if (statusLabel === 'completed') {
            scoresHtml = '<p style="color:#6b7280;font-size:13px;margin-top:12px;">No compliance scores recorded for this document.</p>';
        }

        // Build modal HTML
        const modalHtml = `
            <div id="docDetailOverlay" style="position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;" onclick="if(event.target===this)this.remove()">
                <div style="background:white;border-radius:12px;max-width:560px;width:90%;max-height:85vh;overflow-y:auto;padding:24px;">
                    <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px;">
                        <h3 style="margin:0;font-size:18px;font-weight:600;">${escapeHtml(doc.original_filename || 'Document')}</h3>
                        <button onclick="document.getElementById('docDetailOverlay').remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:#6b7280;">&times;</button>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;font-size:13px;margin-bottom:16px;">
                        <div><span style="color:#6b7280;">Type:</span> <strong>${escapeHtml(docTypeLabel)}</strong></div>
                        <div><span style="color:#6b7280;">Status:</span> <strong>${escapeHtml(statusLabel)}</strong></div>
                        <div><span style="color:#6b7280;">Size:</span> <strong>${doc.file_size ? (doc.file_size / 1024).toFixed(1) + ' KB' : 'N/A'}</strong></div>
                        <div><span style="color:#6b7280;">Uploaded:</span> <strong>${doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'N/A'}</strong></div>
                    </div>
                    <div style="display:flex;gap:8px;margin-bottom:16px;">
                        <button class="btn btn-primary" onclick="openDocumentFile('${doc.id}')">Open File</button>
                        <button class="btn btn-small" onclick="downloadDocumentFile('${doc.id}')">Download</button>
                    </div>
                    ${scoresHtml}
                    ${doc.processing_error ? `<div style="margin-top:12px;padding:10px;background:#FEF2F2;border-radius:8px;color:#DC2626;font-size:13px;"><strong>Processing Error:</strong> ${escapeHtml(doc.processing_error)}</div>` : ''}
                </div>
            </div>
        `;

        // Remove existing modal if any, then insert
        const existing = document.getElementById('docDetailOverlay');
        if (existing) existing.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);

    } catch (error) {
        showToast('Failed to generate view URL: ' + error.message, 'error');
    }
}

async function openDocumentFile(docId) {
    try {
        const result = await apiFetch(`/documents/${docId}/view`);
        if (result && result.url) {
            window.open(result.url, '_blank', 'noopener,noreferrer');
        } else {
            showToast('Could not generate file URL.', 'error');
        }
    } catch (error) {
        showToast('Failed to open file: ' + error.message, 'error');
    }
}

async function downloadDocumentFile(docId) {
    try {
        const result = await apiFetch(`/documents/${docId}/download`);
        if (result && result.url) {
            const a = document.createElement('a');
            a.href = result.url;
            a.download = result.filename || 'document';
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            showToast('Could not generate download URL.', 'error');
        }
    } catch (error) {
        showToast('Failed to download file: ' + error.message, 'error');
    }
}

async function deleteDocument(docId) {
    if (isDemoMode()) {
        showToast('Document deletion is available with a real account.', 'info');
        return;
    }

    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        await apiFetch(`/documents/${docId}`, { method: 'DELETE' });
        loadDocumentsList();
    } catch (error) {
        showToast('Failed to delete document: ' + error.message, 'error');
    }
}

async function viewGapRemediation(gapId) {
    if (isDemoMode() || !gapId) {
        showToast('Detailed remediation steps will be available after uploading and scanning your documents.', 'info');
        return;
    }
    try {
        const data = await apiFetch('/compliance/gaps?resolved=false&limit=100');
        const allGaps = (data && data.gaps) ? data.gaps : [];
        const gap = allGaps.find(g => g.id === gapId);
        if (!gap) {
            showToast('Gap details not found.', 'error');
            return;
        }

        const riskColors = { critical: '#DC2626', high: '#D97706', medium: '#2563EB', low: '#6B7280' };
        const riskColor = riskColors[gap.risk_level] || '#6B7280';
        const isResolved = gap.resolved || false;

        const existing = document.getElementById('gapRemediationOverlay');
        if (existing) existing.remove();

        document.body.insertAdjacentHTML('beforeend', `
            <div id="gapRemediationOverlay" style="position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;" onclick="if(event.target===this)this.remove()">
                <div style="background:white;border-radius:12px;max-width:520px;width:90%;max-height:85vh;overflow-y:auto;padding:28px;">
                    <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px;">
                        <div>
                            <span style="display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;background:${riskColor}20;color:${riskColor};text-transform:uppercase;letter-spacing:.5px;">${escapeHtml(gap.risk_level || 'unknown')} risk</span>
                        </div>
                        <button onclick="document.getElementById('gapRemediationOverlay').remove()" style="background:none;border:none;font-size:22px;cursor:pointer;color:#9ca3af;line-height:1;">&times;</button>
                    </div>
                    <h3 style="margin:0 0 6px;font-size:17px;font-weight:600;color:#111827;">${escapeHtml(gap.standard_name || gap.standard_id || 'NDIS Standard')}</h3>
                    <p style="font-size:12px;color:#6b7280;margin:0 0 16px;">Standard ${escapeHtml(gap.standard_id || '')}</p>
                    <div style="margin-bottom:16px;">
                        <p style="font-size:13px;font-weight:600;color:#374151;margin:0 0 6px;">Gap Identified</p>
                        <p style="font-size:14px;color:#4b5563;margin:0;line-height:1.6;">${escapeHtml(gap.gap_description || 'No description available.')}</p>
                    </div>
                    ${gap.remediation_action ? `
                    <div style="background:#F0FDF4;border-left:3px solid #10B981;padding:12px 14px;border-radius:0 6px 6px 0;margin-bottom:20px;">
                        <p style="font-size:13px;font-weight:600;color:#065F46;margin:0 0 4px;">Recommended Action</p>
                        <p style="font-size:14px;color:#047857;margin:0;line-height:1.6;">${escapeHtml(gap.remediation_action)}</p>
                    </div>` : ''}
                    <button onclick="markGapResolved('${gapId}', ${!isResolved})" style="width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;font-size:14px;font-weight:600;background:${isResolved ? '#F3F4F6' : '#1B365D'};color:${isResolved ? '#374151' : 'white'};">
                        ${isResolved ? 'Re-open Gap' : 'Mark as Resolved'}
                    </button>
                </div>
            </div>
        `);
    } catch (error) {
        showToast('Failed to load remediation details.', 'error');
    }
}

async function markGapResolved(gapId, resolved) {
    try {
        await apiFetch(`/compliance/gaps/${gapId}/resolve`, {
            method: 'PATCH',
            body: JSON.stringify({ resolved }),
        });
        const overlay = document.getElementById('gapRemediationOverlay');
        if (overlay) overlay.remove();
        showToast(resolved ? 'Gap marked as resolved.' : 'Gap re-opened.');
        loadDashboardData();
    } catch (error) {
        showToast('Failed to update gap status.', 'error');
    }
}

// ========== CLIENTS ==========

let currentClientId = null;

function showClients() {
    loadClientsList();
}

async function loadClientsList() {
    if (isDemoMode()) {
        renderDemoClients();
        return;
    }
    if (!currentOrgId) {
        const grid = document.getElementById('clientsList');
        if (grid) grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: #6b7280;">
                <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                <p style="font-size: 16px; font-weight: 500; margin-bottom: 8px;">Account not linked to an organisation</p>
                <p>Please contact support or sign out and sign up again.</p>
            </div>`;
        return;
    }

    try {
        const clientsData = await apiFetch('/clients/?per_page=50');

        if (clientsData && clientsData.clients) {
            renderClientsList(clientsData.clients);
        } else if (Array.isArray(clientsData)) {
            renderClientsList(clientsData);
        } else {
            renderClientsList([]);
        }
    } catch (error) {
        console.error('Failed to load clients:', error);
        renderClientsList([]);
    }
}

function renderClientsList(clients) {
    const grid = document.getElementById('clientsList');
    if (!grid) return;

    if (!clients || clients.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: #6b7280;">
                <div style="font-size: 48px; margin-bottom: 16px;">👤</div>
                <p style="font-size: 16px; font-weight: 500; margin-bottom: 8px;">No clients yet</p>
                <p>Add your first client to start managing their NDIS compliance.</p>
                <button class="btn btn-primary" style="margin-top: 16px;" onclick="showAddClientModal()">Add Client</button>
            </div>
        `;
        return;
    }

    grid.innerHTML = clients.map(client => {
        const fullName = `${client.first_name || ''} ${client.last_name || ''}`.trim();
        const ndisNumber = client.ndis_participant_number || 'N/A';
        // Plan dates with expiry colour-coding
        let planDates = 'Not set';
        let planDateStyle = '';
        if (client.current_plan_start_date && client.current_plan_end_date) {
            const daysLeft = Math.round((new Date(client.current_plan_end_date) - new Date()) / 86400000);
            planDates = `${formatDate(client.current_plan_start_date)} – ${formatDate(client.current_plan_end_date)}`;
            if (daysLeft <= 30) planDateStyle = 'color:#EF4444;font-weight:600;';
            else if (daysLeft <= 90) planDateStyle = 'color:#F59E0B;font-weight:500;';
        }

        // Determine status badge
        let statusClass = 'status-active';
        let statusText = 'Active';
        if (client.status === 'inactive' || client.status === 'exited') {
            statusClass = 'status-inactive';
            statusText = client.status === 'exited' ? 'Exited' : 'Inactive';
        } else if (client.status === 'at_risk') {
            statusClass = 'status-atrisk';
            statusText = 'At Risk';
        }

        return `
            <div class="client-card" onclick="showClientDetail('${client.id}')">
                <div class="client-card-header">
                    <div class="client-avatar">${getInitials(fullName)}</div>
                    <div class="client-card-status ${statusClass}">${statusText}</div>
                </div>
                <div class="client-card-body">
                    <h3>${escapeHtml(fullName)}</h3>
                    <p class="client-ndis">NDIS #${escapeHtml(ndisNumber)}</p>
                    <p class="client-dates" style="${planDateStyle}">${escapeHtml(planDates)}</p>
                    ${client.requires_behaviour_support ? '<p class="client-behaviour">🎯 Behaviour Support</p>' : ''}
                </div>
                <div class="client-card-footer">
                    <button class="btn btn-small" onclick="event.stopPropagation(); showClientDetail('${client.id}')">View Details</button>
                </div>
            </div>
        `;
    }).join('');
}

function renderDemoClients() {
    const demoClients = [
        {
            id: 'demo-client-1',
            first_name: 'James',
            last_name: 'Wilson',
            ndis_participant_number: '123456789',
            date_of_birth: '1995-03-15',
            email: 'james.wilson@example.com',
            phone_number: '+61 2 5555 1234',
            current_plan_start_date: '2024-01-15',
            current_plan_end_date: '2025-01-14',
            requires_behaviour_support: true,
            status: 'active'
        },
        {
            id: 'demo-client-2',
            first_name: 'Sarah',
            last_name: 'Chen',
            ndis_participant_number: '987654321',
            date_of_birth: '1998-07-22',
            email: 'sarah.chen@example.com',
            phone_number: '+61 3 6666 2345',
            current_plan_start_date: '2024-02-01',
            current_plan_end_date: '2025-01-31',
            requires_behaviour_support: false,
            status: 'active'
        },
        {
            id: 'demo-client-3',
            first_name: 'Michael',
            last_name: 'Rodriguez',
            ndis_participant_number: '456789123',
            date_of_birth: '2000-11-08',
            email: 'michael.r@example.com',
            phone_number: '+61 7 7777 3456',
            current_plan_start_date: '2023-12-01',
            current_plan_end_date: '2024-11-30',
            requires_behaviour_support: true,
            status: 'at_risk'
        },
        {
            id: 'demo-client-4',
            first_name: 'Emma',
            last_name: 'Thompson',
            ndis_participant_number: '321654987',
            date_of_birth: '1997-05-30',
            email: 'emma.t@example.com',
            phone_number: '+61 4 8888 4567',
            current_plan_start_date: '2022-06-15',
            current_plan_end_date: '2023-06-14',
            requires_behaviour_support: false,
            status: 'exited'
        }
    ];

    renderClientsList(demoClients);
}

function showAddClientModal() {
    document.getElementById('addClientModal').style.display = 'flex';
}

function closeAddClientModal() {
    document.getElementById('addClientModal').style.display = 'none';
    document.getElementById('addClientForm').reset();
}

async function handleAddClient(e) {
    e.preventDefault();

    const clientData = {
        first_name: document.getElementById('clientFirstName').value,
        last_name: document.getElementById('clientLastName').value,
        date_of_birth: document.getElementById('clientDob').value,
        ndis_participant_number: document.getElementById('clientNdisNumber').value || null,
        email: document.getElementById('clientEmail').value || null,
        phone_number: document.getElementById('clientPhone').value || null,
        current_plan_start_date: document.getElementById('clientPlanStart').value || null,
        current_plan_end_date: document.getElementById('clientPlanEnd').value || null,
        requires_behaviour_support: document.getElementById('clientBehaviour').checked
    };

    if (isDemoMode()) {
        showToast(`Client "${clientData.first_name} ${clientData.last_name}" added successfully!`);
        closeAddClientModal();
        renderDemoClients();
        return;
    }

    if (!currentOrgId) {
        showToast('Your account is not linked to an organisation. Please sign out and sign up again.', 'error');
        return;
    }

    try {
        showLoading(true);
        const result = await apiFetch('/clients/', {
            method: 'POST',
            body: JSON.stringify(clientData)
        });

        showLoading(false);

        if (result) {
            showToast(`Client "${clientData.first_name} ${clientData.last_name}" added successfully!`);
            closeAddClientModal();
            loadClientsList();
        }
    } catch (error) {
        showLoading(false);
        showToast('Failed to add client: ' + error.message, 'error');
    }
}

async function showClientDetail(clientId) {
    currentClientId = clientId;

    if (isDemoMode()) {
        const demoClients = [
            {
                id: 'demo-client-1',
                first_name: 'James',
                last_name: 'Wilson',
                ndis_participant_number: '123456789',
                date_of_birth: '1995-03-15',
                email: 'james.wilson@example.com',
                phone_number: '+61 2 5555 1234',
                current_plan_start_date: '2024-01-15',
                current_plan_end_date: '2025-01-14',
                requires_behaviour_support: true,
                status: 'active'
            },
            {
                id: 'demo-client-2',
                first_name: 'Sarah',
                last_name: 'Chen',
                ndis_participant_number: '987654321',
                date_of_birth: '1998-07-22',
                email: 'sarah.chen@example.com',
                phone_number: '+61 3 6666 2345',
                current_plan_start_date: '2024-02-01',
                current_plan_end_date: '2025-01-31',
                requires_behaviour_support: false,
                status: 'active'
            },
            {
                id: 'demo-client-3',
                first_name: 'Michael',
                last_name: 'Rodriguez',
                ndis_participant_number: '456789123',
                date_of_birth: '2000-11-08',
                email: 'michael.r@example.com',
                phone_number: '+61 7 7777 3456',
                current_plan_start_date: '2023-12-01',
                current_plan_end_date: '2024-11-30',
                requires_behaviour_support: true,
                status: 'at_risk'
            },
            {
                id: 'demo-client-4',
                first_name: 'Emma',
                last_name: 'Thompson',
                ndis_participant_number: '321654987',
                date_of_birth: '1997-05-30',
                email: 'emma.t@example.com',
                phone_number: '+61 4 8888 4567',
                current_plan_start_date: '2022-06-15',
                current_plan_end_date: '2023-06-14',
                requires_behaviour_support: false,
                status: 'exited'
            }
        ];
        const client = demoClients.find(c => c.id === clientId);
        if (client) {
            renderClientDetailView(client);
        }
        return;
    }

    try {
        const client = await apiFetch(`/clients/${clientId}`);
        if (client) {
            _currentClientData = client;
            renderClientDetailView(client);
        }
    } catch (error) {
        console.error('Failed to load client details:', error);
        showToast('Failed to load client details', 'error');
    }
}

function renderClientDetailView(client) {
    const fullName = `${client.first_name || ''} ${client.last_name || ''}`.trim();

    // Determine status
    let statusClass = 'client-status-active';
    let statusText = 'Active';
    if (client.status === 'inactive' || client.status === 'exited') {
        statusClass = 'client-status-inactive';
        statusText = client.status === 'exited' ? 'Exited' : 'Inactive';
    } else if (client.status === 'at_risk') {
        statusClass = 'client-status-atrisk';
        statusText = 'At Risk';
    }

    document.getElementById('clientDetailName').textContent = escapeHtml(fullName);
    document.getElementById('clientDetailNdis').textContent = `NDIS Participant #${escapeHtml(client.ndis_participant_number || 'N/A')}`;
    document.getElementById('clientDetailStatus').className = `client-detail-status ${statusClass}`;
    document.getElementById('clientDetailStatus').textContent = statusText;

    document.getElementById('clientDetailDob').textContent = client.date_of_birth ? formatDate(client.date_of_birth) : '-';
    document.getElementById('clientDetailEmail').textContent = client.email ? escapeHtml(client.email) : '-';
    document.getElementById('clientDetailPhone').textContent = client.phone_number ? escapeHtml(client.phone_number) : '-';

    document.getElementById('clientDetailPlanStart').textContent = client.current_plan_start_date ? formatDate(client.current_plan_start_date) : '-';
    document.getElementById('clientDetailPlanEnd').textContent = client.current_plan_end_date ? formatDate(client.current_plan_end_date) : '-';
    document.getElementById('clientDetailBehaviour').textContent = client.requires_behaviour_support ? 'Yes' : 'No';

    // Render compliance results
    renderComplianceResults(client);

    // Render linked documents
    renderLinkedDocuments(client);

    // Hide list view, show detail view
    document.getElementById('clientsList').style.display = 'none';
    document.getElementById('clientDetailView').style.display = 'block';
}

async function renderComplianceResults(client) {
    const resultsContainer = document.getElementById('complianceResults');
    if (!resultsContainer) return;

    resultsContainer.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">Loading compliance checks…</p>';

    if (isDemoMode()) {
        _renderComplianceChecksList(resultsContainer, [
            { id: 'demo-1', check_type: 'comprehensive', overall_score: 88, status: 'completed', executed_at: new Date(Date.now() - 3 * 86400000).toISOString(), findings: { gaps: 2, total_standards: 17, met: 15 } },
            { id: 'demo-2', check_type: 'comprehensive', overall_score: 74, status: 'completed', executed_at: new Date(Date.now() - 14 * 86400000).toISOString(), findings: { gaps: 5, total_standards: 17, met: 12 } },
        ]);
        return;
    }

    try {
        const data = await apiFetch(`/clients/${client.id}/compliance-checks?limit=5`);
        _renderComplianceChecksList(resultsContainer, data.checks || []);
    } catch (error) {
        resultsContainer.innerHTML = '<p style="color: #ef4444; text-align: center; padding: 20px;">Failed to load compliance checks.</p>';
    }
}

function _renderComplianceChecksList(container, checks) {
    if (!checks || checks.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">No compliance checks performed yet. Click "Run Compliance Check" to start.</p>';
        return;
    }

    container.innerHTML = checks.map(check => {
        const score = Math.round(check.overall_score || 0);
        const color = score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#EF4444';
        const statusLabel = score >= 80 ? 'Compliant' : score >= 50 ? 'At Risk' : 'Non-Compliant';
        const statusIcon = score >= 80 ? '🟢' : score >= 50 ? '🟡' : '🔴';
        const findings = check.findings || {};
        const gaps = findings.gaps || 0;
        const checkedAt = check.executed_at ? timeAgo(new Date(check.executed_at)) : 'Unknown';

        return `
            <div class="compliance-result-card">
                <div class="compliance-result-header">
                    <div>
                        <h4>${escapeHtml(check.check_type === 'comprehensive' ? 'Full Compliance Check' : (check.check_type || 'Check'))}</h4>
                        <p class="compliance-checked">Run ${checkedAt}${gaps > 0 ? ` · ${gaps} gap${gaps !== 1 ? 's' : ''} found` : ''}</p>
                    </div>
                    <div class="status-badge ${score >= 80 ? 'status-compliant' : 'status-warning'}">${statusIcon} ${statusLabel}</div>
                </div>
                <div class="compliance-score">
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${score}%; background: ${color};"></div>
                    </div>
                    <span class="score-text">${score}%</span>
                </div>
            </div>
        `;
    }).join('');
}

async function renderLinkedDocuments(client) {
    const docsContainer = document.getElementById('linkedDocuments');
    docsContainer.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">Loading...</p>';

    if (isDemoMode()) {
        const documents = [
            { id: 'doc-1', document_type: 'individual_support_plan', review_due_date: '2025-06-30', status: 'active', is_current: true, created_at: new Date(Date.now() - 10 * 86400000).toISOString(), notes: null },
            { id: 'doc-2', document_type: 'incident_report', review_due_date: null, status: 'active', is_current: true, created_at: new Date(Date.now() - 20 * 86400000).toISOString(), notes: null }
        ];
        _renderLinkedDocumentsList(docsContainer, documents);
        return;
    }

    try {
        const data = await apiFetch(`/clients/${client.id}/documents`);
        _renderLinkedDocumentsList(docsContainer, data.documents || []);
    } catch (error) {
        docsContainer.innerHTML = '<p style="color: #ef4444; text-align: center; padding: 20px;">Failed to load linked documents.</p>';
    }
}

function _renderLinkedDocumentsList(container, documents) {
    if (!documents || documents.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">No documents linked to this client yet.</p>';
        return;
    }

    container.innerHTML = documents.map(doc => {
        const typeLabel = formatDocumentType(doc.document_type) || escapeHtml(doc.document_type);
        const reviewText = doc.review_due_date ? `Review due: ${formatDate(doc.review_due_date)}` : 'No review date set';
        const linkedText = timeAgo(new Date(doc.created_at));
        const isOverdue = doc.review_due_date && new Date(doc.review_due_date) < new Date();
        const reviewClass = isOverdue ? 'color: #ef4444;' : 'color: #6b7280;';

        return `
            <div class="linked-doc-card">
                <div style="flex: 1;">
                    <p class="linked-doc-name">${escapeHtml(typeLabel)}</p>
                    <p class="linked-doc-date" style="${reviewClass}">${reviewText}</p>
                    <p class="linked-doc-date">Linked ${linkedText}</p>
                </div>
                ${doc.notes ? `<p style="font-size:12px;color:#6b7280;margin-top:4px;">${escapeHtml(doc.notes)}</p>` : ''}
            </div>
        `;
    }).join('');
}

async function openLinkDocumentModal() {
    if (!currentClientId) return;
    document.getElementById('linkDocumentError').style.display = 'none';
    document.getElementById('linkDocumentForm').reset();
    document.getElementById('linkDocumentModal').style.display = 'flex';

    if (isDemoMode()) {
        document.getElementById('linkDocumentSelect').innerHTML = '<option value="">No documents available in demo mode</option>';
        return;
    }

    try {
        const data = await apiFetch('/documents/?per_page=100');
        const docs = data.documents || [];
        const select = document.getElementById('linkDocumentSelect');
        if (docs.length === 0) {
            select.innerHTML = '<option value="">No uploaded documents found</option>';
        } else {
            select.innerHTML = '<option value="">Select a document...</option>' +
                docs.map(d => `<option value="${escapeHtml(d.id)}">${escapeHtml(d.original_filename || d.filename)}</option>`).join('');
        }
    } catch (error) {
        document.getElementById('linkDocumentSelect').innerHTML = '<option value="">Failed to load documents</option>';
    }
}

function closeLinkDocumentModal() {
    document.getElementById('linkDocumentModal').style.display = 'none';
}

async function handleLinkDocument(event) {
    event.preventDefault();
    const errorEl = document.getElementById('linkDocumentError');
    errorEl.style.display = 'none';

    const documentId = document.getElementById('linkDocumentSelect').value;
    const documentType = document.getElementById('linkDocumentType').value;
    const documentDate = document.getElementById('linkDocumentDate').value;
    const reviewDueDate = document.getElementById('linkDocumentReviewDate').value;
    const notes = document.getElementById('linkDocumentNotes').value.trim();

    if (!documentId || !documentType) {
        errorEl.textContent = 'Please select a document and type.';
        errorEl.style.display = 'block';
        return;
    }

    try {
        const body = { document_id: documentId, document_type: documentType };
        if (documentDate) body.document_date = documentDate;
        if (reviewDueDate) body.review_due_date = reviewDueDate;
        if (notes) body.notes = notes;

        await apiFetch(`/clients/${currentClientId}/documents`, { method: 'POST', body: JSON.stringify(body) });
        closeLinkDocumentModal();
        showToast('Document linked successfully');
        // Refresh linked documents list
        const client = { id: currentClientId };
        renderLinkedDocuments(client);
    } catch (error) {
        errorEl.textContent = error.message || 'Failed to link document.';
        errorEl.style.display = 'block';
    }
}

function closeClientDetail() {
    document.getElementById('clientDetailView').style.display = 'none';
    document.getElementById('clientsList').style.display = 'grid';
}

let _currentClientData = null; // cache for edit modal pre-fill

function showEditClientModal() {
    if (isDemoMode()) {
        showToast('Client editing is not available in demo mode.', 'info');
        return;
    }
    if (!currentClientId) return;

    // Pre-fill from cached client data if we have it
    const c = _currentClientData;
    if (c) {
        document.getElementById('editClientFirstName').value = c.first_name || '';
        document.getElementById('editClientLastName').value = c.last_name || '';
        document.getElementById('editClientDob').value = c.date_of_birth || '';
        document.getElementById('editClientNdisNumber').value = c.ndis_participant_number || '';
        document.getElementById('editClientEmail').value = c.email || '';
        document.getElementById('editClientPhone').value = c.phone_number || '';
        document.getElementById('editClientPlanStart').value = c.current_plan_start_date || '';
        document.getElementById('editClientPlanEnd').value = c.current_plan_end_date || '';
        document.getElementById('editClientBehaviour').checked = !!c.requires_behaviour_support;
    }
    document.getElementById('editClientError').style.display = 'none';
    document.getElementById('editClientModal').style.display = 'flex';
}

function closeEditClientModal() {
    document.getElementById('editClientModal').style.display = 'none';
}

async function handleEditClient(e) {
    e.preventDefault();
    const errorEl = document.getElementById('editClientError');
    errorEl.style.display = 'none';

    const payload = {
        first_name: document.getElementById('editClientFirstName').value.trim(),
        last_name: document.getElementById('editClientLastName').value.trim(),
        ndis_participant_number: document.getElementById('editClientNdisNumber').value.trim() || null,
        email: document.getElementById('editClientEmail').value.trim() || null,
        phone_number: document.getElementById('editClientPhone').value.trim() || null,
        date_of_birth: document.getElementById('editClientDob').value || null,
        current_plan_start_date: document.getElementById('editClientPlanStart').value || null,
        current_plan_end_date: document.getElementById('editClientPlanEnd').value || null,
        requires_behaviour_support: document.getElementById('editClientBehaviour').checked,
    };

    const btn = e.target.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

    try {
        const updated = await apiFetch(`/clients/${currentClientId}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        _currentClientData = updated;
        closeEditClientModal();
        showToast('Client updated.');
        showClientDetail(currentClientId);
    } catch (error) {
        errorEl.textContent = error.message || 'Failed to save client.';
        errorEl.style.display = 'block';
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Save Changes'; }
    }
}

async function triggerClientComplianceCheck() {
    if (!currentClientId) return;

    if (isDemoMode()) {
        showToast('Compliance check started. Results will be available in a few moments.', 'info');
        return;
    }

    try {
        showLoading(true);
        await apiFetch(`/clients/${currentClientId}/compliance-check`, {
            method: 'POST',
            body: JSON.stringify({ check_type: 'comprehensive' }),
        });
        showLoading(false);

        showToast('Compliance check completed. Refreshing results...');
        showClientDetail(currentClientId);
    } catch (error) {
        showLoading(false);
        showToast('Failed to trigger compliance check: ' + error.message, 'error');
    }
}

// ========== STAFF ==========

function openAddStaffModal() {
    document.getElementById('addStaffError').style.display = 'none';
    document.getElementById('addStaffModal').style.display = 'flex';
}

function closeAddStaffModal() {
    document.getElementById('addStaffModal').style.display = 'none';
    document.getElementById('addStaffForm').reset();
    document.getElementById('addStaffError').style.display = 'none';
}

async function handleAddStaff(e) {
    e.preventDefault();

    const staffData = {
        full_name: document.getElementById('staffFullName').value,
        email: document.getElementById('staffEmail').value,
        role: document.getElementById('staffRole').value,
    };

    if (isDemoMode()) {
        showToast(`Staff member "${staffData.full_name}" added successfully!`);
        closeAddStaffModal();
        return;
    }

    try {
        showLoading(true);
        const result = await apiFetch('/staff/', {
            method: 'POST',
            body: JSON.stringify(staffData)
        });
        showLoading(false);

        if (result) {
            showToast(`Staff member "${staffData.full_name}" added successfully!`);
            closeAddStaffModal();
            loadStaffList();
        }
    } catch (error) {
        showLoading(false);
        const errEl = document.getElementById('addStaffError');
        errEl.textContent = 'Failed to add staff: ' + error.message;
        errEl.style.display = 'block';
    }
}

async function loadStaffList() {
    if (isDemoMode() || !currentOrgId) {
        return; // keep hardcoded demo data in HTML
    }

    try {
        const data = await apiFetch('/staff/');
        if (data && data.staff) {
            renderStaffList(data.staff);
        }
    } catch (error) {
        console.error('Failed to load staff:', error);
    }
}

function renderStaffList(staffMembers) {
    const tbody = document.querySelector('.staff-table tbody');
    if (!tbody) return;

    if (!staffMembers || staffMembers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align:center; padding:40px; color:#6b7280;">
                    No staff members yet. Add your first staff member above.
                </td>
            </tr>
        `;
        return;
    }

    const selfId = currentUser && currentUser.id;

    tbody.innerHTML = staffMembers.map(member => {
        const name = escapeHtml(member.full_name || member.email || 'Unknown');
        const role = escapeHtml(member.role || 'member');
        const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
        const isSelf = member.id === selfId;
        const actions = isSelf
            ? `<span style="color:#9ca3af; font-size:13px;">(you)</span>`
            : `<button class="btn btn-small" style="margin-right:6px;" onclick="openEditStaffModal('${member.id}','${role}','${name}')">Edit</button>
               <button class="btn btn-small btn-danger" onclick="confirmRemoveStaff('${member.id}','${name}')">Remove</button>`;
        return `
            <tr>
                <td><strong>${name}</strong></td>
                <td>${roleLabel}</td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');
}

function openEditStaffModal(userId, currentRole, name) {
    document.getElementById('editStaffUserId').value = userId;
    document.getElementById('editStaffName').textContent = name;
    document.getElementById('editStaffRole').value = currentRole;
    document.getElementById('editStaffError').style.display = 'none';
    document.getElementById('editStaffModal').style.display = 'flex';
}

function closeEditStaffModal() {
    document.getElementById('editStaffModal').style.display = 'none';
    document.getElementById('editStaffError').style.display = 'none';
}

async function handleEditStaff(e) {
    e.preventDefault();
    const userId = document.getElementById('editStaffUserId').value;
    const role = document.getElementById('editStaffRole').value;

    if (isDemoMode()) {
        showToast('Role updated successfully!');
        closeEditStaffModal();
        return;
    }

    try {
        showLoading(true);
        await apiFetch(`/staff/${userId}`, { method: 'PUT', body: JSON.stringify({ role }) });
        showLoading(false);
        showToast('Role updated successfully!');
        closeEditStaffModal();
        loadStaffList();
    } catch (error) {
        showLoading(false);
        const errEl = document.getElementById('editStaffError');
        errEl.textContent = 'Failed to update role: ' + error.message;
        errEl.style.display = 'block';
    }
}

async function confirmRemoveStaff(userId, name) {
    if (!confirm(`Remove ${name} from your organisation? They will lose access.`)) return;

    if (isDemoMode()) {
        showToast(`${name} removed.`);
        return;
    }

    try {
        showLoading(true);
        await apiFetch(`/staff/${userId}`, { method: 'DELETE' });
        showLoading(false);
        showToast(`${name} removed from organisation.`);
        loadStaffList();
    } catch (error) {
        showLoading(false);
        showToast('Failed to remove staff member: ' + error.message, 'error');
    }
}

async function loadSettingsTab() {
    if (isDemoMode() || !currentOrgId) return;
    try {
        const org = await apiFetch(`/organizations/${currentOrgId}`);
        const nameEl = document.getElementById('settingsOrgName');
        const abnEl = document.getElementById('settingsABN');
        const ndisEl = document.getElementById('settingsNDISReg');
        const addressEl = document.getElementById('settingsAddress');
        const auditDateEl = document.getElementById('settingsAuditDate');
        const auditTypeEl = document.getElementById('settingsAuditType');
        if (nameEl) nameEl.value = org.name || '';
        if (abnEl) abnEl.value = org.abn || '';
        if (ndisEl) ndisEl.value = org.ndis_registration_number || '';
        if (addressEl) addressEl.value = org.address || '';
        if (auditDateEl) auditDateEl.value = org.audit_date || '';
        if (auditTypeEl) auditTypeEl.value = org.audit_type || '';
    } catch (error) {
        console.warn('Could not load org settings:', error);
    }
}

async function handleSettingsSave(e) {
    e.preventDefault();
    if (isDemoMode() || !currentOrgId) {
        showToast('Settings saved (demo mode — no changes persisted).');
        return;
    }
    const payload = {};
    const name = document.getElementById('settingsOrgName')?.value.trim();
    const abn = document.getElementById('settingsABN')?.value.trim();
    const ndisReg = document.getElementById('settingsNDISReg')?.value.trim();
    const address = document.getElementById('settingsAddress')?.value.trim();
    const auditDate = document.getElementById('settingsAuditDate')?.value;
    const auditType = document.getElementById('settingsAuditType')?.value.trim();
    if (name) payload.name = name;
    if (abn) payload.abn = abn;
    if (ndisReg) payload.ndis_registration_number = ndisReg;
    if (address) payload.address = address;
    if (auditDate) payload.audit_date = auditDate;
    if (auditType) payload.audit_type = auditType;

    if (Object.keys(payload).length === 0) {
        showToast('No changes to save.');
        return;
    }
    try {
        const updated = await apiFetch(`/organizations/${currentOrgId}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        showToast('Organisation settings saved.');
        const nameEl = document.getElementById('orgName');
        if (nameEl && updated.name) nameEl.textContent = updated.name;
    } catch (error) {
        showToast('Failed to save settings: ' + error.message, 'error');
    }
}

// ========== INTEGRATIONS (external storage) ==========

const INTEGRATION_PROVIDERS = [
    {
        key: 'microsoft',
        label: 'SharePoint / OneDrive',
        blurb: 'Pull in everything your team already stores in Microsoft 365.',
        icon: '🔷',
        enabled: true,
    },
    {
        key: 'google',
        label: 'Google Drive',
        blurb: 'Sync shared drives and folders from Workspace.',
        icon: '📂',
        enabled: false,
    },
    {
        key: 'dropbox',
        label: 'Dropbox',
        blurb: 'Import policies and procedures straight from Dropbox.',
        icon: '📦',
        enabled: false,
    },
    {
        key: 'box',
        label: 'Box',
        blurb: 'Enterprise-grade storage for regulated providers.',
        icon: '🗄️',
        enabled: false,
    },
];

async function loadIntegrations() {
    const container = document.getElementById('integrationsList');
    if (!container) return;

    let connected = [];
    try {
        connected = await apiFetch('/integrations/');
        if (!Array.isArray(connected)) connected = [];
    } catch (error) {
        console.warn('Could not load integrations:', error);
        connected = [];
    }

    const byProvider = Object.fromEntries(connected.map(c => [c.provider, c]));
    container.innerHTML = INTEGRATION_PROVIDERS.map(p => {
        const existing = byProvider[p.key];
        return renderIntegrationCard(p, existing);
    }).join('');
}

function renderIntegrationCard(provider, existing) {
    const isConnected = !!existing;
    const isComingSoon = !provider.enabled;

    const statusLine = (() => {
        if (isComingSoon) return '<span class="badge badge-muted">Coming soon</span>';
        if (!isConnected) return '<span style="color:#6b7280; font-size:13px;">Not connected</span>';
        const status = existing.sync_status || 'idle';
        const when = existing.last_sync_at ? timeAgo(new Date(existing.last_sync_at)) : 'never';
        const folderCount = (existing.root_folders || []).length;
        const statusBadge = status === 'syncing'
            ? '<span style="color:#2563eb; font-size:12px; font-weight:600;">Syncing…</span>'
            : status === 'error'
                ? '<span style="color:#ef4444; font-size:12px; font-weight:600;">Error</span>'
                : '<span style="color:#059669; font-size:12px; font-weight:600;">Connected</span>';
        return `
            ${statusBadge}
            <div style="font-size:12px; color:#6b7280; margin-top:4px;">
                ${escapeHtml(existing.account_email || '')}<br>
                Last sync: ${when} · ${folderCount} folder${folderCount === 1 ? '' : 's'}
            </div>
            ${existing.last_error ? `<div style="font-size:12px; color:#ef4444; margin-top:6px;">${escapeHtml(existing.last_error)}</div>` : ''}
        `;
    })();

    const actions = (() => {
        if (isComingSoon) {
            return '<button class="btn btn-secondary" style="width:100%;" disabled>Coming soon</button>';
        }
        if (!isConnected) {
            return `<button class="btn btn-primary" style="width:100%;" onclick="connectIntegration('${provider.key}')">Connect</button>`;
        }
        return `
            <div style="display:flex; gap:8px;">
                <button class="btn btn-secondary" style="flex:1;" onclick="openFolderPickerFor('${existing.id}')">Folders</button>
                <button class="btn btn-secondary" style="flex:1;" onclick="resyncIntegration('${existing.id}')">Resync</button>
                <button class="btn btn-secondary" style="flex:1;" onclick="disconnectIntegration('${existing.id}')">Disconnect</button>
            </div>
        `;
    })();

    return `
        <div style="border:1px solid #e5e7eb; border-radius:10px; padding:16px; background:white; display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="font-size:22px;">${provider.icon}</div>
                <div style="flex:1;">
                    <div style="font-weight:600;">${provider.label}</div>
                    <div style="font-size:12px; color:#6b7280;">${provider.blurb}</div>
                </div>
            </div>
            <div>${statusLine}</div>
            <div>${actions}</div>
        </div>
    `;
}

async function connectIntegration(provider) {
    try {
        const result = await apiFetch(`/integrations/${provider}/authorize`);
        if (result && result.url) {
            // Open in a new tab so the user keeps Verida open while they consent
            window.open(result.url, '_blank', 'noopener');
            showToast('Finish connecting in the new tab. We\'ll refresh automatically.', 'info');
        } else {
            showToast('Could not start OAuth flow.', 'error');
        }
    } catch (error) {
        showToast('Failed to start OAuth: ' + error.message, 'error');
    }
}

async function resyncIntegration(integrationId) {
    try {
        await apiFetch(`/integrations/${integrationId}/sync`, { method: 'POST' });
        showToast('Sync started — new documents will appear shortly.', 'info');
        setTimeout(loadIntegrations, 1500);
    } catch (error) {
        showToast('Failed to start sync: ' + error.message, 'error');
    }
}

async function disconnectIntegration(integrationId) {
    if (!confirm('Disconnect this integration? Files already synced will stay in Verida.')) return;
    try {
        await apiFetch(`/integrations/${integrationId}`, { method: 'DELETE' });
        showToast('Integration disconnected.');
        loadIntegrations();
    } catch (error) {
        showToast('Failed to disconnect: ' + error.message, 'error');
    }
}

// ---- Folder picker ----
let _folderPickerSelected = new Map(); // id → {id, name, path}
let _folderPickerStack = [];            // breadcrumb: [{id|null, name}]

async function openFolderPickerFor(integrationId) {
    _folderPickerSelected = new Map();
    _folderPickerStack = [{ id: null, name: 'Root' }];
    document.getElementById('folderPickerIntegrationId').value = integrationId;
    document.getElementById('folderPickerModal').style.display = 'flex';
    document.getElementById('folderPickerError').style.display = 'none';
    await loadFolderPickerLevel(null);
}

async function loadFolderPickerLevel(parentId) {
    const list = document.getElementById('folderPickerList');
    list.innerHTML = '<div style="padding:24px; text-align:center; color:#9ca3af;">Loading folders…</div>';

    const integrationId = document.getElementById('folderPickerIntegrationId').value;
    const qs = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : '';
    try {
        const folders = await apiFetch(`/integrations/${integrationId}/folders${qs}`);
        renderFolderPickerBreadcrumb();
        if (!folders || folders.length === 0) {
            list.innerHTML = '<div style="padding:24px; text-align:center; color:#9ca3af;">No folders at this level.</div>';
            return;
        }
        list.innerHTML = folders.map(f => {
            const selected = _folderPickerSelected.has(f.id);
            return `
                <div style="display:flex; align-items:center; gap:10px; padding:10px 12px; border-bottom:1px solid #f3f4f6;">
                    <input type="checkbox" ${selected ? 'checked' : ''} onchange="toggleFolderSelect('${f.id}', '${escapeAttr(f.name)}', '${escapeAttr(f.path)}', this.checked)">
                    <div style="flex:1; cursor:${f.has_children ? 'pointer' : 'default'};" onclick="${f.has_children ? `drillIntoFolder('${f.id}', '${escapeAttr(f.name)}')` : ''}">
                        <div style="font-weight:500;">📁 ${escapeHtml(f.name)}</div>
                        <div style="font-size:11px; color:#9ca3af;">${escapeHtml(f.path || '')}</div>
                    </div>
                    ${f.has_children ? `<button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="drillIntoFolder('${f.id}', '${escapeAttr(f.name)}')">Open ›</button>` : ''}
                </div>
            `;
        }).join('');
        updateFolderPickerCount();
    } catch (error) {
        list.innerHTML = '';
        const err = document.getElementById('folderPickerError');
        err.textContent = 'Could not load folders: ' + error.message;
        err.style.display = 'block';
    }
}

function escapeAttr(str) {
    return String(str || '').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

function toggleFolderSelect(id, name, path, checked) {
    if (checked) {
        _folderPickerSelected.set(id, { id, name, path });
    } else {
        _folderPickerSelected.delete(id);
    }
    updateFolderPickerCount();
}

function updateFolderPickerCount() {
    const el = document.getElementById('folderPickerCount');
    const n = _folderPickerSelected.size;
    if (el) el.textContent = `${n} folder${n === 1 ? '' : 's'} selected`;
}

function drillIntoFolder(id, name) {
    _folderPickerStack.push({ id, name });
    loadFolderPickerLevel(id);
}

function renderFolderPickerBreadcrumb() {
    const el = document.getElementById('folderPickerBreadcrumb');
    if (!el) return;
    el.innerHTML = _folderPickerStack.map((crumb, idx) => {
        const isLast = idx === _folderPickerStack.length - 1;
        if (isLast) return `<span style="color:#111827; font-weight:600;">${escapeHtml(crumb.name)}</span>`;
        return `<a href="#" style="color:#2563eb; text-decoration:none;" onclick="popFolderStackTo(${idx}); return false;">${escapeHtml(crumb.name)}</a> › `;
    }).join('');
}

function popFolderStackTo(index) {
    _folderPickerStack = _folderPickerStack.slice(0, index + 1);
    const crumb = _folderPickerStack[index];
    loadFolderPickerLevel(crumb.id);
}

function closeFolderPicker() {
    document.getElementById('folderPickerModal').style.display = 'none';
}

async function saveFolderSelection() {
    const integrationId = document.getElementById('folderPickerIntegrationId').value;
    const folders = Array.from(_folderPickerSelected.values());
    if (folders.length === 0) {
        const err = document.getElementById('folderPickerError');
        err.textContent = 'Pick at least one folder to sync.';
        err.style.display = 'block';
        return;
    }
    try {
        await apiFetch(`/integrations/${integrationId}/folders/select`, {
            method: 'POST',
            body: JSON.stringify({ folders }),
        });
        closeFolderPicker();
        showToast(`Syncing ${folders.length} folder${folders.length === 1 ? '' : 's'} in the background.`, 'info');
        setTimeout(loadIntegrations, 1500);
    } catch (error) {
        const err = document.getElementById('folderPickerError');
        err.textContent = 'Failed to save: ' + error.message;
        err.style.display = 'block';
    }
}

// When we come back from an OAuth redirect with ?integration=connected, pop the
// folder picker automatically so the first-run experience is seamless.
function handleIntegrationReturnFromOAuth() {
    const hash = window.location.hash || '';
    const queryIdx = hash.indexOf('?');
    if (queryIdx === -1) return;
    const params = new URLSearchParams(hash.slice(queryIdx + 1));
    const status = params.get('integration');
    const integrationId = params.get('id');
    if (status === 'connected' && integrationId) {
        // Jump to settings tab + open folder picker
        try { switchTab('settings'); } catch (e) {}
        setTimeout(() => {
            loadIntegrations().then(() => openFolderPickerFor(integrationId));
        }, 200);
        // Clean the URL
        history.replaceState({}, '', window.location.pathname + '#settings');
    } else if (status === 'error') {
        showToast('Could not connect storage: ' + (params.get('message') || 'unknown error'), 'error');
    }
}

async function loadReportsTab() {
    const container = document.getElementById('reportsContent');
    if (!container) return;

    if (isDemoMode()) {
        _renderReportsSummary(container, {
            organization_name: 'Sunshine Support Services',
            overall_compliance_score: 88,
            total_documents: 12,
            critical_gaps: 1,
            high_gaps: 2,
            audit_date: null,
            days_until_audit: null,
            compliant_standards: 14,
            needs_attention_standards: 2,
            non_compliant_standards: 1,
            not_assessed_standards: 0,
        }, [
            { standard_number: '1.1', title: 'Person-centred approaches', score: 92, status: 'compliant' },
            { standard_number: '1.2', title: 'Individual values and beliefs', score: 87, status: 'compliant' },
            { standard_number: '1.3', title: 'Responsive support provision', score: 61, status: 'needs_attention' },
            { standard_number: '2.1', title: 'Governance and operational management', score: 78, status: 'needs_attention' },
            { standard_number: '3.1', title: 'Feedback and complaints management', score: 55, status: 'non_compliant' },
        ]);
        return;
    }

    container.innerHTML = '<p style="color:#6b7280;text-align:center;padding:40px;">Loading report data…</p>';

    try {
        const [dashboard, scoresResp] = await Promise.all([
            apiFetch('/dashboard/'),
            apiFetch('/compliance/scores'),
        ]);
        const standards = (scoresResp && scoresResp.scores) ? scoresResp.scores : [];
        _renderReportsSummary(container, dashboard, standards);
    } catch (error) {
        container.innerHTML = `<p style="color:#ef4444;text-align:center;padding:40px;">Failed to load report data: ${escapeHtml(error.message)}</p>`;
    }
}

function _renderReportsSummary(container, dash, standards) {
    const score = Math.round(dash.overall_compliance_score || 0);
    const scoreColor = score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444';
    const totalGaps = (dash.critical_gaps || 0) + (dash.high_gaps || 0);
    const generatedDate = new Date().toLocaleDateString('en-AU', { year: 'numeric', month: 'long', day: 'numeric' });

    const standardsRows = standards.map(s => {
        const pct = Math.round(s.score || 0);
        const c = pct >= 80 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444';
        const label = s.status === 'compliant' ? 'Compliant' : s.status === 'needs_attention' ? 'Needs Attention' : 'Non-Compliant';
        return `<tr>
            <td style="padding:8px 12px;font-size:13px;color:#374151;">${escapeHtml(s.standard_number || '')}</td>
            <td style="padding:8px 12px;font-size:13px;color:#374151;">${escapeHtml(s.title || s.standard_name || '')}</td>
            <td style="padding:8px 12px;font-size:13px;font-weight:600;color:${c};">${pct}%</td>
            <td style="padding:8px 12px;font-size:13px;color:${c};">${label}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
        <div id="printableReport" style="max-width:860px;">
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:24px;">
                <div>
                    <h2 style="margin:0 0 4px;font-size:20px;font-weight:700;color:#1B365D;">NDIS Compliance Report</h2>
                    <p style="margin:0;color:#6b7280;font-size:13px;">${escapeHtml(dash.organization_name || '')} · Generated ${generatedDate}</p>
                </div>
                <button onclick="printReport()" class="btn btn-secondary" style="font-size:13px;">Print / Save PDF</button>
            </div>

            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px;">
                <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:32px;font-weight:700;color:${scoreColor};">${score}%</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Overall Score</div>
                </div>
                <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:32px;font-weight:700;color:#1B365D;">${dash.total_documents || 0}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Documents</div>
                </div>
                <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:32px;font-weight:700;color:${totalGaps > 0 ? '#EF4444' : '#10B981'};">${totalGaps}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Critical/High Gaps</div>
                </div>
                <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:32px;font-weight:700;color:#1B365D;">${dash.compliant_standards || 0}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Standards Met</div>
                </div>
                ${dash.days_until_audit !== null && dash.days_until_audit !== undefined ? `
                <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:32px;font-weight:700;color:${dash.days_until_audit <= 30 ? '#EF4444' : dash.days_until_audit <= 90 ? '#F59E0B' : '#1B365D'};">${dash.days_until_audit}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Days to Audit</div>
                </div>` : ''}
            </div>

            ${standards.length > 0 ? `
            <h3 style="font-size:15px;font-weight:600;color:#1B365D;margin:0 0 12px;">Standards Breakdown</h3>
            <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:24px;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#F9FAFB;border-bottom:1px solid #e5e7eb;">
                            <th style="padding:10px 12px;font-size:12px;font-weight:600;color:#6b7280;text-align:left;">No.</th>
                            <th style="padding:10px 12px;font-size:12px;font-weight:600;color:#6b7280;text-align:left;">Standard</th>
                            <th style="padding:10px 12px;font-size:12px;font-weight:600;color:#6b7280;text-align:left;">Score</th>
                            <th style="padding:10px 12px;font-size:12px;font-weight:600;color:#6b7280;text-align:left;">Status</th>
                        </tr>
                    </thead>
                    <tbody>${standardsRows}</tbody>
                </table>
            </div>` : '<p style="color:#6b7280;font-size:14px;">No standards scored yet. Upload and scan documents to populate this report.</p>'}
        </div>
    `;
}

function generateReport() {
    loadReportsTab();
}

function printReport() {
    const el = document.getElementById('printableReport');
    if (!el) return;
    const w = window.open('', '_blank');
    w.document.write(`<!DOCTYPE html><html><head><title>NDIS Compliance Report</title>
        <style>body{font-family:Inter,sans-serif;padding:32px;color:#111;}table{width:100%;border-collapse:collapse;}th,td{border:1px solid #e5e7eb;padding:8px 12px;font-size:13px;text-align:left;}</style>
        </head><body>${el.outerHTML}<script>window.print();window.close();<\/script></body></html>`);
    w.document.close();
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

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-AU', options);
}

function getInitials(name) {
    if (!name) return '?';
    return name
        .split(' ')
        .map(word => word[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
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
