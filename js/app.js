// Check authentication on load
window.addEventListener('load', () => {
    const demoMode = new URLSearchParams(window.location.search).get('demo') === 'true';
    const currentUser = localStorage.getItem('currentUser');
    const demoUser = localStorage.getItem('demoUser');
    
    if (!demoMode && !currentUser && !demoUser) {
        // Show auth screen
        document.getElementById('authScreen').style.display = 'flex';
        document.getElementById('appShell').style.display = 'none';
    } else {
        // Show app
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('appShell').style.display = 'flex';
        
        // Set user info
        if (demoUser) {
            const user = JSON.parse(demoUser);
            document.getElementById('orgName').textContent = user.org || 'Demo Organization';
        } else if (currentUser) {
            const user = JSON.parse(currentUser);
            const email = user.email.split('@')[0].toUpperCase();
            document.getElementById('orgName').textContent = 'Organization';
        }
        
        // Initialize charts
        initCharts();
        attachEventListeners();
    }
});

// Handle auth login
function handleAuthLogin(e) {
    e.preventDefault();
    const email = document.getElementById('authEmail').value;
    
    localStorage.setItem('currentUser', JSON.stringify({
        email,
        loggedIn: true,
        timestamp: new Date().toISOString()
    }));
    
    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('appShell').style.display = 'flex';
    initCharts();
    attachEventListeners();
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
function logout() {
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
        
        new Chart(gaugeCtx, {
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
        
        new Chart(trendCtx, {
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

// Handle file upload
function handleFileUpload(e) {
    const files = e.dataTransfer ? e.dataTransfer.files : e.target.files;
    if (files && files.length > 0) {
        const fileName = files[0].name;
        alert(`Document "${fileName}" uploaded successfully! Scanning for compliance gaps...`);
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('fileInput').value = '';
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
