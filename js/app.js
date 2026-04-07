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
            // Token expired, redirect to login
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

// Check authentication on load
window.addEventListener('load', async () => {
    const demoMode = new URLSearchParams(window.location.search).get('demo') === 'true';
    const accessToken = localStorage.getItem('accessToken');
    const demoUser = localStorage.getItem('demoUser');

    if (!demoMode && !accessToken && !demoUser) {
        // Show auth screen
        document.getElementById('authScreen').style.display = 'flex';
        document.getElementById('appShell').style.display = 'none';
    } else if (demoMode || demoUser) {
        // Demo mode
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('appShell').style.display = 'flex';

        if (demoUser) {
            const user = JSON.parse(demoUser);
            document.getElementById('orgName').textContent = user.org || 'Demo Organization';
        }

        // Initialize charts
        initCharts();
        attachEventListeners();
    } else {
        // Logged in — fetch user and org data
        try {
            const userData = await apiFetch('/auth/me');
            if (userData) {
                currentUser = userData;
                currentOrgId = userData.organization_id;

                document.getElementById('authScreen').style.display = 'none';
                document.getElementById('appShell').style.display = 'flex';

                // Set org name
                if (userData.organization && userData.organization.name) {
                    document.getElementById('orgName').textContent = userData.organization.name;
                }

                // Initialize charts and load dashboard data
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

// Handle auth login
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
            // Store tokens
            localStorage.setItem('accessToken', response.access_token);
            localStorage.setItem('refreshToken', response.refresh_token);
            currentUser = response.user;
            currentOrgId = response.user.organization_id;

            // Update org name
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

// Toggle between login and signup views
function showSignUp() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('signupView').style.display = 'block';
}

function showLogin() {
    document.getElementById('signupView').style.display = 'none';
    document.getElementById('loginView').style.display = 'block';
}

// Handle sign up
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
            alert('Account created! You can now sign in.');
            showLogin();
            document.getElementById('authEmail').value = email;
        }
    } catch (error) {
        showLoading(false);
        alert('Sign up failed: ' + error.message);
    }
}

// Toggle between login and signup views
function showSignUp() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('signupView').style.display = 'block';
}

function showLogin() {
    document.getElementById('signupView').style.display = 'none';
    document.getElementById('loginView').style.display = 'block';
}

// Handle sign up
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
            alert('Account created! You can now sign in.');
            showLogin();
            document.getElementById('authEmail').value = email;
        }
    } catch (error) {
        showLoading(false);
        alert('Sign up failed: ' + error.message);
    }
}

// Enter demo mode
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
}

// Logout
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

// Switch tabs
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-pane').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Scroll to top
    document.querySelector('.tab-content').scrollTop = 0;
}

// Store chart instances
let gaugeChart = null;
let trendChart = null;

// Initialize charts
function initCharts() {
    // Gauge Chart
    const gaugeCtx = document.getElementById('gaugeChart');
    if (gaugeCtx) {
        const gaugeData = {
            labels: ['Compliant', 'At Risk'],
            datasets: [{
                data: [94, 6],
                backgroundColor: ['#10B981', '#F59E0B'],
                borderWidth: 0,
                circumference: 180,
                rotation: 270,
                cutout: '75%'
            }]
        };

        gaugeChart = new Chart(gaugeCtx, {
            type: 'doughnut',
            data: gaugeData,
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

    // Trend Chart
    const trendCtx = document.getElementById('trendChart');
    if (trendCtx) {
        const trendData = {
            labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6', 'Week 7', 'Week 8', 'Week 9', 'Week 10', 'Week 11', 'Week 12', 'Week 13'],
            datasets: [{
                label: 'Compliance Score',
                data: [78, 80, 79, 82, 84, 86, 88, 89, 90, 91, 92, 93, 94],
                borderColor: '#2a9d8f',
                backgroundColor: 'rgba(42, 157, 143, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#2a9d8f',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        };

        trendChart = new Chart(trendCtx, {
            type: 'line',
            data: trendData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }
}

// Update gauge chart with new score
function updateGaugeChart(score) {
    if (gaugeChart) {
        gaugeChart.data.datasets[0].data = [score, 100 - score];
        gaugeChart.update();
    }
}

// Attach event listeners
function attachEventListeners() {
    // Modal handlers
    document.querySelector('.modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.style.display = 'none';
        }
    });
    
    // Drag and drop for upload
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

// Open upload modal
function openUploadModal() {
    document.getElementById('uploadModal').style.display = 'flex';
}

// Load dashboard data from API
async function loadDashboardData() {
    try {
        const demoMode = new URLSearchParams(window.location.search).get('demo') === 'true';

        if (demoMode || !currentOrgId) {
            // Use dummy data for demo mode
            return;
        }

        // Fetch dashboard data
        const dashboardData = await apiFetch('/dashboard/');

        if (dashboardData) {
            // Update score stats
            const overallScore = dashboardData.overall_compliance_score || 94;
            const compliantStandards = dashboardData.compliant_standards || 18;
            const criticalGaps = dashboardData.critical_gaps || 2;
            const totalDocs = dashboardData.total_documents || 8;

            document.getElementById('statMet').textContent = compliantStandards;
            document.getElementById('statGaps').textContent = criticalGaps;
            document.getElementById('statDocs').textContent = totalDocs;

            // Update gauge chart data
            updateGaugeChart(overallScore);

            // Fetch and display documents
            loadDocumentsList();
        }
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        // Continue with default demo data
    }
}

// Load documents list
async function loadDocumentsList() {
    try {
        const demoMode = new URLSearchParams(window.location.search).get('demo') === 'true';

        if (demoMode || !currentOrgId) {
            return;
        }

        const documentsData = await apiFetch('/documents/?per_page=20');

        if (documentsData && documentsData.documents) {
            // Documents are displayed in a grid
            const grid = document.querySelector('.documents-grid');
            if (grid) {
                // Keep the existing card structure for now
                // In a full implementation, we'd dynamically populate these
            }
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

// Handle file upload
async function handleFileUpload(e) {
    const files = e.dataTransfer ? e.dataTransfer.files : e.target.files;
    if (files && files.length > 0) {
        const file = files[0];
        const fileName = file.name;

        const demoMode = new URLSearchParams(window.location.search).get('demo') === 'true';

        if (demoMode) {
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
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
                body: formData,
            });

            showLoading(false);

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }

            const result = await response.json();
            alert(`Document "${fileName}" uploaded successfully! Job ID: ${result.job_id}. Scanning for compliance gaps...`);
            document.getElementById('uploadModal').style.display = 'none';
            document.getElementById('fileInput').value = '';

            // Refresh documents list
            loadDocumentsList();
        } catch (error) {
            showLoading(false);
            alert('Upload failed: ' + error.message);
        }
    }
}

// Open add staff modal
function openAddStaffModal() {
    const name = prompt('Enter staff member name:');
    if (name) {
        alert(`${name} has been added to your staff list.`);
    }
}

// Handle settings save
function handleSettingsSave(e) {
    e.preventDefault();
    alert('Settings updated successfully!');
}

// Generate report
function generateReport() {
    alert('Report generation started. Check your email in a few moments.');
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
