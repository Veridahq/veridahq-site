# Verida - Production Deployment Guide

## Overview

This is a complete, production-ready static site for Verida built for Vercel deployment.

## Project Structure

```
deploy/
├── index.html              # Landing page
├── app.html                # Compliance dashboard
├── package.json            # Project metadata
├── vercel.json             # Vercel configuration
├── .gitignore              # Git ignore rules
├── css/
│   ├── style.css          # Shared landing page & base styles
│   └── dashboard.css      # Dashboard-specific styles
├── js/
│   ├── main.js            # Landing page JavaScript
│   └── app.js             # Dashboard app JavaScript
└── README_DEPLOYMENT.md   # This file
```

## Key Features

### Landing Page (index.html)
- Hero section with animated compliance score counter
- Feature cards highlighting core capabilities
- 3-step "How It Works" guide
- Pricing section with monthly/annual toggle (20% annual discount)
- FAQ accordion with 5 common questions
- Testimonials from real NDIS providers
- Newsletter signup form
- CTA sections with "Start Free Pilot" button
- Professional footer with links and social proof
- Fully responsive design

### Dashboard (app.html)
- Authentication screen with demo mode
- Sidebar navigation with 5 main modules
- Dashboard tab with:
  - Compliance gauge chart (animated doughnut)
  - 90-day compliance trend line chart
  - Module cards showing compliance status
  - Gap analysis section with priority-ranked gaps
- Documents tab with upload functionality
- Staff tab with training compliance tracking
- Reports tab with downloadable compliance reports
- Settings tab for account management
- All data persisted to localStorage for demo

### Technical Stack
- Pure HTML5, CSS3, and JavaScript (no framework dependencies)
- Chart.js 4.4.0 from CDN for visualizations
- Google Fonts (Inter) for typography
- Responsive grid system
- CSS custom properties for theming
- LocalStorage for session management

## Deployment to Vercel

### Option 1: Git + GitHub (Recommended)

1. Push the `/deploy` folder to a GitHub repository:
   ```bash
   cd deploy
   git init
   git add .
   git commit -m "Initial Verida production build"
   git remote add origin https://github.com/yourusername/verida.git
   git push -u origin main
   ```

2. Go to [Vercel Dashboard](https://vercel.com)
3. Click "Add New" > "Project"
4. Import the GitHub repository
5. Vercel auto-detects a static site (no build step needed)
6. Deploy!

### Option 2: Direct Upload via Vercel CLI

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Deploy from the project directory:
   ```bash
   cd deploy
   vercel
   ```

3. Follow the prompts to create a project and deploy

### Option 3: Drag & Drop to Vercel

1. Go to [Vercel Drop Zone](https://vercel.com/new)
2. Drag the `/deploy` folder onto the drop zone
3. Vercel automatically deploys your site

## Configuration

### Vercel Setup
- `vercel.json` configures:
  - Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
  - Cache settings (1 hour for static assets)
  - Redirects (/login → /app.html)
  - Rewrites for SPA routing

### Environment Variables (if needed later)
Create a `.env.local` file in `/deploy`:
```
REACT_APP_API_URL=https://api.veridahq.com
REACT_APP_ENV=production
```

## Local Development

### Option 1: Python HTTP Server
```bash
cd deploy
python -m http.server 3000
# Visit http://localhost:3000
```

### Option 2: Node.js HTTP Server
```bash
npm install -g http-server
cd deploy
http-server -p 3000
# Visit http://localhost:3000
```

### Option 3: Live Server (VS Code Extension)
1. Install Live Server extension in VS Code
2. Right-click `index.html` > Open with Live Server
3. Changes auto-refresh in browser

## User Flows

### Landing Page
1. User lands on `/` (index.html)
2. Can explore features, pricing, FAQ
3. Clicks "Start Free Pilot" → modal form
4. Enters org name, name, email, participant count
5. Form submits → stored in localStorage + redirects to app.html
6. OR clicks "Login" → login modal
7. Can enter demo email/password or click "Try Demo Mode" → direct to app

### Dashboard
1. User arrives at `/app.html`
2. Authentication check:
   - If logged in via pilot signup → logged in automatically
   - If demo mode → shows demo data
   - If not authenticated → shows login screen
3. Can navigate through Dashboard, Documents, Staff, Reports, Settings
4. All data is stored in localStorage (persists across browser sessions)
5. Charts render using Chart.js from CDN

## Demo Data

Pre-loaded demo data (Sunshine Support Services):
- Organisation: "Sunshine Support Services"
- Compliance Score: 94%
- Standards Met: 18/20
- Critical Gaps: 2 (Incident Response & Staff Training)
- Documents: 4 sample documents with status
- Staff: 5 team members with varied training status
- Reports: 3 sample compliance reports

## Styling & Branding

### Color Scheme
- Navy (Primary): `#1B365D`
- Teal (Accent): `#2A9D8F`
- White (Background): `#FFFFFF`
- Light Grey: `#F8F9FA`
- Dark Grey: `#6B7280`

### Typography
- Font: Inter (Google Fonts)
- Weights: 400, 500, 600, 700
- Used for all headings and body text

### Responsive Breakpoints
- Desktop: 1200px+
- Tablet: 768px - 1199px
- Mobile: < 768px
- Small Mobile: < 480px

All components are fully responsive and tested on mobile, tablet, and desktop.

## Performance Optimizations

1. **Static Site**: No server processing needed
2. **CDN Delivery**: Vercel serves all files from edge locations globally
3. **Asset Optimization**: CSS and JS are minified
4. **Lazy Loading**: Images use native lazy loading
5. **Caching**: Static assets cached for 1 hour
6. **No External APIs**: Demo mode runs entirely client-side

## Security

1. **HTTPS**: All Vercel deployments use HTTPS by default
2. **Security Headers**: Configured in vercel.json
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: SAMEORIGIN
   - X-XSS-Protection: 1; mode=block
3. **No Sensitive Data**: All demo data is non-sensitive
4. **localStorage Only**: No backend API calls in this version
5. **Content Security Policy**: Can be added to vercel.json for further protection

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

All modern browsers support ES6+ features used in the code.

## Future Enhancements

When moving to production with a real backend:

1. Replace localStorage with API calls
2. Add authentication with JWT tokens
3. Implement real document upload to S3/Azure Storage
4. Connect to backend database for compliance scoring
5. Add real-time notifications via WebSocket
6. Implement SSO with Google/Microsoft
7. Add PDF export functionality for reports
8. Integrate Stripe for billing
9. Add email notifications
10. Implement audit logging

## Support & Troubleshooting

### Page Not Loading
- Clear browser cache: Cmd+Shift+R (Mac) or Ctrl+Shift+F5 (Windows)
- Check vercel.json syntax
- Ensure all files are in `/deploy` directory

### Charts Not Rendering
- Verify Chart.js CDN link is accessible
- Check browser console for errors
- Ensure canvas elements have IDs: `gaugeChart`, `trendChart`

### LocalStorage Not Working
- Check browser privacy settings
- Ensure localStorage is not disabled
- Try incognito/private mode

### Deployment Issues
- Check Vercel build logs in dashboard
- Ensure vercel.json is valid JSON
- Verify no TypeScript/build errors in console

## Contact & Support

- Project: Verida (veridahq.com)
- Support: hello@veridahq.com
- Issues: Report via Vercel dashboard

## License

PROPRIETARY - Verida 2024
