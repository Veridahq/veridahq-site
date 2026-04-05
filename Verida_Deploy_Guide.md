# Verida Compliance Dashboard — Deployment Guide

A complete guide to deploying the Verida NDIS compliance dashboard to production using Vercel, Netlify, or GitHub Pages.

---

## Prerequisites

Before deploying, you'll need:

1. **Node.js & npm** (for local testing)
   - Download from https://nodejs.org/ (LTS version recommended)
   - Verify installation: `node --version` and `npm --version`

2. **Git** (for version control)
   - Download from https://git-scm.com/
   - Verify installation: `git --version`

3. **A deployment platform account** (choose one):
   - **Vercel** (recommended for fastest setup): https://vercel.com/signup
   - **Netlify**: https://app.netlify.com/signup
   - **GitHub**: https://github.com/signup (for GitHub Pages)

4. **A domain name** (optional but recommended)
   - Suggested: verida.com.au
   - Registrar: Namecheap, GoDaddy, or similar

---

## Option A: Deploy via Vercel CLI (Fastest for Developers)

### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Authenticate

```bash
vercel login
```

Follow the prompts to sign in with your Vercel account.

### Step 3: Deploy

Navigate to your project directory and run:

```bash
cd /path/to/verida/deploy
vercel
```

Answer the prompts:
- **Project name**: `verida-compliance-dashboard`
- **Directory**: `.` (current directory)
- **Settings**: Press Enter to accept defaults

### Step 4: Verify Deployment

- Vercel will provide a live URL (e.g., `https://verida-compliance-dashboard.vercel.app`)
- Visit the URL to confirm the dashboard is live

### Step 5: Production Deployment

To deploy to production (after testing):

```bash
vercel --prod
```

---

## Option B: Deploy via GitHub + Vercel Auto-Deploy (Best for Teams)

### Step 1: Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial Verida dashboard deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/verida-compliance-dashboard.git
git push -u origin main
```

### Step 2: Connect GitHub to Vercel

1. Go to https://vercel.com/dashboard
2. Click **Add New** → **Project**
3. Select **Import Git Repository**
4. Find and select your `verida-compliance-dashboard` repo
5. Click **Import**

### Step 3: Configure Project

- **Framework Preset**: Select "Other" (static site)
- **Build Command**: Leave blank or use `npm run build`
- **Install Command**: `npm install`
- **Output Directory**: `.` (root directory)

### Step 4: Deploy

Click **Deploy**. Vercel will automatically:
- Build the site
- Deploy to a preview URL
- Run on every push to main for automatic updates

### Step 5: Future Deployments

Every time you push to GitHub:

```bash
git add .
git commit -m "Update dashboard"
git push origin main
```

Vercel auto-deploys automatically.

---

## Option C: Deploy via Netlify (Drag & Drop)

### Step 1: Create a Netlify Account

Go to https://app.netlify.com/signup and sign up.

### Step 2: Deploy

**Method 1: Drag & Drop (Easiest)**
1. Drag the `/deploy` folder onto https://app.netlify.app/drop
2. Netlify automatically deploys to a live URL

**Method 2: Connect GitHub (Recommended for Teams)**
1. Click **New site from Git**
2. Select **GitHub**
3. Choose your `verida-compliance-dashboard` repo
4. Click **Deploy site**

### Step 3: Verify

Netlify provides a URL (e.g., `https://verida-dashboard.netlify.app`). Visit it to confirm.

### Step 4: Change Site Name

1. Go to **Site settings** → **General**
2. Change **Site name** to something memorable
3. Save

---

## Custom Domain Setup (verida.com.au)

### Using Vercel

1. Go to your **Vercel dashboard** → **Project settings**
2. Navigate to **Domains**
3. Click **Add**
4. Enter your domain: `verida.com.au`
5. Follow instructions to add DNS records:
   - Add CNAME record pointing to Vercel's nameservers
   - Or update your registrar's nameservers to Vercel's

### Using Netlify

1. Go to **Site settings** → **Domain management**
2. Click **Add custom domain**
3. Enter: `verida.com.au`
4. Follow DNS setup instructions:
   - Update nameservers at your registrar OR
   - Add CNAME record: `verida.com.au` → your Netlify domain

### Using GitHub Pages

1. Update `vercel.json` or add `.nojekyll` file
2. Configure custom domain in repo settings
3. Update DNS records at your registrar

**Typical DNS Update (at Namecheap, GoDaddy, etc.):**

| Type | Name | Value |
|------|------|-------|
| CNAME | www | `vercel.app` or `netlify.app` |
| A | @ | `76.76.19.0` |

Changes can take 24-48 hours to propagate.

---

## Environment Variables (for Future API Integration)

### Setting Up Environment Variables

When you add a backend API later, store sensitive credentials as environment variables.

**In Vercel:**
1. **Project settings** → **Environment variables**
2. Add variables:
   - `REACT_APP_API_URL`: `https://api.verida.com.au`
   - `REACT_APP_API_KEY`: `your-secret-key`
   - `REACT_APP_ENVIRONMENT`: `production`

**In Netlify:**
1. **Site settings** → **Build & deploy** → **Environment**
2. Add the same variables

**Reference in Code:**

```javascript
const apiUrl = process.env.REACT_APP_API_URL;
const apiKey = process.env.REACT_APP_API_KEY;
```

**Example Future API Call:**

```javascript
fetch(`${process.env.REACT_APP_API_URL}/compliance/score`, {
  headers: {
    'Authorization': `Bearer ${process.env.REACT_APP_API_KEY}`,
    'Content-Type': 'application/json'
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## SSL/HTTPS Setup (Automatic)

Good news: **SSL/HTTPS is automatic** with Vercel and Netlify.

- Both platforms provide free SSL certificates
- All deployments are HTTPS by default
- Certificates auto-renew

**Verify SSL:**
1. Visit your live domain
2. Click the lock icon in the browser
3. You should see "Connection is secure"

---

## Post-Deployment Checklist

After going live, verify everything works:

### Browser & Performance

- [ ] Dashboard loads in under 3 seconds
- [ ] All tabs (Dashboard, Documents, Staff, Incidents, Reports) are clickable
- [ ] Notifications bell responds to clicks
- [ ] Charts and gauges render correctly
- [ ] Mobile responsive (test on phone)
- [ ] All fonts load correctly (Inter font)

### Functionality

- [ ] Tab switching works smoothly
- [ ] Table displays all gap findings
- [ ] Badges display with correct colors
- [ ] Hover effects on cards and activity items work
- [ ] Module scores display correctly

### Analytics & Monitoring

- [ ] Enable Google Analytics:
  ```html
  <script async src="https://www.googletagmanager.com/gtag/js?id=GA_ID"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'GA_ID');
  </script>
  ```

- [ ] Set up error tracking (Sentry, LogRocket)
- [ ] Monitor uptime (UptimeRobot.com)

### Security

- [ ] HTTPS is active (check lock icon)
- [ ] No console errors or warnings
- [ ] Security headers are set (X-Frame-Options, Content-Security-Policy)
- [ ] Sensitive data is NOT in browser storage or URLs

### SEO & Meta Tags

- [ ] Page title appears in browser tab
- [ ] Meta description displays correctly
- [ ] Open Graph tags work (test on Twitter/LinkedIn sharing)
- [ ] Favicon displays in tab

---

## Troubleshooting Common Issues

### 1. Blank or Broken Page

**Cause:** Wrong build output directory
**Fix:**
```bash
# Verify vercel.json
cat vercel.json
# Look for "routes" section pointing to index.html
```

### 2. 404 Error on Page Refresh

**Cause:** SPA routing not configured
**Fix:** Ensure `vercel.json` has this route:
```json
{
  "src": "^/(?!.*\\.(js|css|png|jpg|svg)$).*$",
  "dest": "/index.html",
  "status": 200
}
```

### 3. Styles Not Loading

**Cause:** Incorrect CSS path
**Fix:** Verify styles are inline in `index.html` (they are)

### 4. Slow Performance

**Cause:** Large uncompressed assets
**Fix:**
```bash
# Check file sizes
ls -lh index.html
# Should be under 500KB
```

### 5. Environment Variables Not Working

**Cause:** Variables not redeployed after adding
**Fix:**
```bash
# For Vercel
vercel env pull
vercel --prod

# For Netlify
netlify deploy --prod
```

---

## Local Testing Before Deployment

### Test Locally

```bash
# Navigate to project
cd /path/to/verida/deploy

# Start local server
npm run dev
# or
python -m http.server 3000

# Visit
open http://localhost:3000
```

### Run in Production Mode

```bash
# Simulate Vercel production
npm run start
```

### Preview Deployment Before Publishing

```bash
# Vercel preview (staging)
vercel

# Visit the preview URL, not --prod
```

---

## Next Steps: Adding a Backend

Once the dashboard is live, you can add a backend API:

1. **Create an API server** (Node.js, Python, etc.)
2. **Connect to a database** (PostgreSQL, MongoDB)
3. **Add authentication** (OAuth, JWT tokens)
4. **Deploy API** (Heroku, AWS, DigitalOcean)
5. **Add environment variables** (from step above)
6. **Test API endpoints** before linking to dashboard

Example API structure:

```
POST   /api/compliance/score     → Get current score
GET    /api/staff                → List all staff
POST   /api/incidents            → Submit incident
GET    /api/audit-readiness      → Check audit status
```

---

## Support & Resources

- **Vercel Docs**: https://vercel.com/docs
- **Netlify Docs**: https://docs.netlify.com
- **GitHub Pages**: https://pages.github.com
- **DNS Help**: https://mxtoolbox.com
- **SSL Check**: https://www.ssllabs.com/ssltest

---

## Rollback & Downgrade

### Rollback Previous Deployment (Vercel)

```bash
vercel rollback
# Select the deployment to restore
```

### View Deployment History

```bash
vercel list
```

### Delete a Deployment

```bash
vercel remove [deployment-url]
```

---

**Deployment completed! Your Verida compliance dashboard is now live and accessible worldwide.**

For questions or issues, refer to the troubleshooting section or contact your deployment platform's support.
