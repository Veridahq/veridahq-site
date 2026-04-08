// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
            document.getElementById('navMenu').classList.remove('active');
            document.getElementById('hamburger').classList.remove('active');
        }
    });
});

// Hamburger menu toggle
const hamburger = document.getElementById('hamburger');
const navMenu = document.getElementById('navMenu');

hamburger.addEventListener('click', () => {
    navMenu.classList.toggle('active');
    hamburger.classList.toggle('active');
});

// Animated counter for compliance score
function animateCounter(element, target, duration = 2000) {
    let current = 0;
    const increment = target / (duration / 16);
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Start counter animation on page load
window.addEventListener('load', () => {
    const counter = document.getElementById('complianceCounter');
    if (counter) {
        animateCounter(counter, 94, 2500);
    }
});

// Scroll-triggered animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
        }
    });
}, observerOptions);

document.querySelectorAll('.slide-up').forEach(el => observer.observe(el));

// FAQ Accordion toggle
function toggleFAQ(button) {
    const faqItem = button.closest('.faq-item');
    faqItem.classList.toggle('active');
    
    // Close other FAQs
    document.querySelectorAll('.faq-item.active').forEach(item => {
        if (item !== faqItem) {
            item.classList.remove('active');
        }
    });
}

// Pricing toggle (Monthly/Annual)
const billingToggle = document.getElementById('billingToggle');
if (billingToggle) {
    billingToggle.addEventListener('change', function() {
        document.querySelectorAll('.amount').forEach(el => {
            const monthly = parseInt(el.dataset.monthly);
            const annual = parseInt(el.dataset.annual);
            
            if (this.checked) {
                el.textContent = Math.floor(annual / 12);
            } else {
                el.textContent = monthly;
            }
        });
    });
}

// Newsletter signup
function handleNewsletter(e) {
    e.preventDefault();
    const email = e.target.querySelector('input[type="email"]').value;
    
    // Store in localStorage
    const subscribers = JSON.parse(localStorage.getItem('subscribers') || '[]');
    if (!subscribers.includes(email)) {
        subscribers.push(email);
        localStorage.setItem('subscribers', JSON.stringify(subscribers));
    }
    
    alert('Thanks for subscribing! Check your email for weekly compliance tips.');
    e.target.reset();
}

// Pilot signup handler
async function handlePilotSignup(e) {
    e.preventDefault();

    const org      = document.getElementById('signupOrg').value.trim();
    const name     = document.getElementById('signupName').value.trim();
    const email    = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;

    const btn = document.getElementById('signupBtn');
    const errEl = document.getElementById('signupError');
    errEl.style.display = 'none';

    btn.disabled = true;
    btn.textContent = 'Creating account…';

    try {
        const res = await fetch('https://verida-api.onrender.com/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                password,
                full_name: name,
                organization_name: org,
            }),
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Sign up failed. Please try again.');
        }

        // Show email-sent confirmation
        document.getElementById('pilotFormWrap').style.display = 'none';
        document.getElementById('sentToEmail').textContent = email;
        document.getElementById('pilotEmailSent').style.display = 'block';

    } catch (err) {
        errEl.textContent = err.message;
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Get Started Free';
    }
}

// Forgot password helpers
function openForgotPassword(e) {
    e.preventDefault();
    document.getElementById('loginModal').style.display = 'none';
    document.getElementById('forgotPasswordModal').style.display = 'flex';
}

function switchToLogin(e) {
    e.preventDefault();
    document.getElementById('forgotPasswordModal').style.display = 'none';
    document.getElementById('loginModal').style.display = 'flex';
}

async function handleForgotPassword(e) {
    e.preventDefault();
    const email = e.target.querySelector('input[type="email"]').value;
    const btn = e.target.querySelector('button[type="submit"]');

    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
        const res = await fetch('https://verida-api.onrender.com/api/auth/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
        });

        // Always show the same message regardless of whether the email exists
        document.getElementById('forgotPasswordModal').style.display = 'none';
        alert('If that email address is registered, a password reset link has been sent. Check your inbox.');
        e.target.reset();
    } catch (err) {
        alert('Something went wrong. Please try again.');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Send Reset Link';
    }
}

// Login handler
async function handleLogin(e) {
    e.preventDefault();

    const email    = e.target.querySelector('input[type="email"]').value.trim();
    const password = e.target.querySelector('input[type="password"]').value;
    const btn      = e.target.querySelector('button[type="submit"]');

    let errEl = document.getElementById('loginError');
    if (!errEl) {
        errEl = document.createElement('p');
        errEl.id = 'loginError';
        errEl.style.cssText = 'color:#e53e3e;font-size:14px;margin-top:8px;display:none;';
        btn.insertAdjacentElement('afterend', errEl);
    }
    errEl.style.display = 'none';

    btn.disabled = true;
    btn.textContent = 'Signing in…';

    try {
        const res = await fetch('https://verida-api.onrender.com/api/auth/signin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Invalid email or password.');
        }

        // Persist session
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('refreshToken', data.refresh_token);
        localStorage.setItem('currentUser', JSON.stringify({
            ...data.user,
            loggedIn: true,
        }));

        document.getElementById('loginModal').style.display = 'none';
        window.location.href = 'app.html';

    } catch (err) {
        errEl.textContent = err.message;
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}

// Demo mode handler
function handleDemoMode() {
    localStorage.setItem('demoUser', JSON.stringify({
        org: 'Sunshine Support Services',
        name: 'Demo User',
        email: 'demo@example.com',
        plan: 'growth',
        startDate: new Date().toISOString()
    }));
    
    document.getElementById('loginModal').style.display = 'none';
    alert('Entering demo mode...');
    setTimeout(() => {
        window.location.href = 'app.html?demo=true';
    }, 1000);
}

// Close modals on background click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
});

// Close mobile menu when clicking links
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => {
        navMenu.classList.remove('active');
        hamburger.classList.remove('active');
    });
});

// Add scroll event for navbar shadow
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 10) {
        navbar.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)';
    } else {
        navbar.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.08)';
    }
});
