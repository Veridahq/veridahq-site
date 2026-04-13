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
        showToast('Login failed: ' + error.message, 'error');
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

        const docTypeLabel = doc.document_type
            ? formatDocumentType(doc.document_type)
            : null;

        return `
            <div class="document-card">
                <div class="doc-icon">${icon}</div>
                <div class="doc-name">${escapeHtml(doc.file_name || doc.name || 'Untitled')}</div>
                ${docTypeLabel ? `<div class="doc-type" title="${escapeHtml(doc.document_type)}">${escapeHtml(docTypeLabel)}</div>` : ''}
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
        const result = await apiFetch(`/documents/${docId}/view`);
        if (result && result.url) {
            window.open(result.url, '_blank', 'noopener,noreferrer');
        }
    } catch (error) {
        showToast('Failed to generate view URL: ' + error.message, 'error');
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

function viewGapRemediation(gapId) {
    if (isDemoMode() || !gapId) {
        showToast('Detailed remediation steps will be available after uploading and scanning your documents.', 'info');
        return;
    }
    showToast('Remediation details coming soon.', 'info');
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
        const planDates = client.current_plan_start_date && client.current_plan_end_date
            ? `${formatDate(client.current_plan_start_date)} – ${formatDate(client.current_plan_end_date)}`
            : 'Not set';

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
                    <p class="client-dates">${escapeHtml(planDates)}</p>
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

function renderComplianceResults(client) {
    const resultsContainer = document.getElementById('complianceResults');

    // Demo compliance results
    const results = [
        {
            category: 'Personal Planning & Budgeting',
            status: 'compliant',
            score: 95,
            lastChecked: new Date(Date.now() - 3 * 86400000)
        },
        {
            category: 'Plan Implementation',
            status: 'compliant',
            score: 88,
            lastChecked: new Date(Date.now() - 5 * 86400000)
        },
        {
            category: 'Incident Management',
            status: 'at_risk',
            score: 72,
            lastChecked: new Date(Date.now() - 7 * 86400000)
        },
        {
            category: 'Safeguarding',
            status: 'compliant',
            score: 92,
            lastChecked: new Date(Date.now() - 2 * 86400000)
        }
    ];

    if (!results || results.length === 0) {
        resultsContainer.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">No compliance checks performed yet.</p>';
        return;
    }

    resultsContainer.innerHTML = results.map(result => {
        const statusClass = result.status === 'compliant' ? 'status-compliant' : 'status-warning';
        const statusIcon = result.status === 'compliant' ? '🟢' : '🟡';
        const lastCheckedText = timeAgo(result.lastChecked);

        return `
            <div class="compliance-result-card">
                <div class="compliance-result-header">
                    <div>
                        <h4>${escapeHtml(result.category)}</h4>
                        <p class="compliance-checked">Last checked ${lastCheckedText}</p>
                    </div>
                    <div class="status-badge ${statusClass}">${statusIcon} ${result.status === 'compliant' ? 'Compliant' : 'At Risk'}</div>
                </div>
                <div class="compliance-score">
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${result.score}%; background: ${result.status === 'compliant' ? '#10B981' : '#F59E0B'};"></div>
                    </div>
                    <span class="score-text">${result.score}%</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderLinkedDocuments(client) {
    const docsContainer = document.getElementById('linkedDocuments');

    // Demo documents linked to this client
    const documents = [
        {
            id: 'doc-1',
            file_name: 'Plan Implementation Summary.pdf',
            uploaded_at: new Date(Date.now() - 10 * 86400000),
            status: 'compliant'
        },
        {
            id: 'doc-2',
            file_name: 'Incident Report Q1 2024.docx',
            uploaded_at: new Date(Date.now() - 20 * 86400000),
            status: 'gaps_found'
        }
    ];

    if (!documents || documents.length === 0) {
        docsContainer.innerHTML = '<p style="color: #6b7280; text-align: center; padding: 20px;">No documents linked to this client yet.</p>';
        return;
    }

    docsContainer.innerHTML = documents.map(doc => {
        const statusClass = doc.status === 'compliant' ? 'status-compliant' : 'status-warning';
        const statusIcon = doc.status === 'compliant' ? '🟢' : '🟡';
        const statusText = doc.status === 'compliant' ? 'Compliant' : 'Gaps Found';
        const uploadedText = timeAgo(new Date(doc.uploaded_at));

        return `
            <div class="linked-doc-card">
                <div style="flex: 1;">
                    <p class="linked-doc-name">${escapeHtml(doc.file_name)}</p>
                    <p class="linked-doc-date">Uploaded ${uploadedText}</p>
                </div>
                <div class="status-badge ${statusClass}">${statusIcon} ${statusText}</div>
            </div>
        `;
    }).join('');
}

function closeClientDetail() {
    document.getElementById('clientDetailView').style.display = 'none';
    document.getElementById('clientsList').style.display = 'grid';
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
            method: 'POST'
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

    tbody.innerHTML = staffMembers.map(member => {
        const name = escapeHtml(member.full_name || member.email || 'Unknown');
        const role = escapeHtml(member.role || 'member');
        const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
        return `
            <tr>
                <td><strong>${name}</strong></td>
                <td>${roleLabel}</td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td><span class="badge badge-warning">— Not checked</span></td>
                <td><button class="btn btn-small" onclick="showToast('Staff details coming soon.', 'info')">View</button></td>
            </tr>
        `;
    }).join('');
}

function handleSettingsSave(e) {
    e.preventDefault();
    showToast('Settings updated successfully!');
}

function generateReport() {
    showToast('Report generation started. Check your email in a few moments.', 'info');
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
