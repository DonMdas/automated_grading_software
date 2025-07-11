const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3002;
const API_URL = 'http://localhost:8001';

// Enable CORS
app.use(cors());

// Serve static files
app.use('/static', express.static(path.join(__dirname, 'static')));

// Proxy API requests to backend
app.use('/api', createProxyMiddleware({
  target: API_URL,
  changeOrigin: true,
  logLevel: 'debug'
}));

// Serve templates as static HTML for development
app.use(express.static(path.join(__dirname, 'templates')));

// Specific route handlers
app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'dashboard.html'));
});

app.get('/evaluation', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'evaluation.html'));
});

// Authentication routes
app.get('/auth/teacher_login.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'auth', 'teacher_login.html'));
});

app.get('/auth/teacher_signup.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'auth', 'teacher_signup.html'));
});

app.get('/teacher-signup', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'auth', 'teacher_signup.html'));
});

// Additional routes for better navigation
app.get('/analytics', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'analytics', 'analytics.html'));
});

app.get('/classroom', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'classroom', 'classroom.html'));
});

app.get('/annotation', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'annotation', 'annotation.html'));
});

app.get('/upload', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'upload', 'upload.html'));
});

// Fallback for SPA routing
app.get('*', (req, res) => {
  // If the request is for a template, try to serve it
  const templatePath = path.join(__dirname, 'templates', req.path === '/' ? 'index.html' : req.path);
  res.sendFile(templatePath, (err) => {
    if (err) {
      res.sendFile(path.join(__dirname, 'templates', 'index.html'));
    }
  });
});

app.listen(PORT, () => {
  console.log(`🚀 Frontend server running at http://localhost:${PORT}`);
  console.log(`📡 Proxying API requests to ${API_URL}`);
  console.log('\n📋 Available pages:');
  console.log(`   • Home: http://localhost:${PORT}`);
  console.log(`   • Analytics: http://localhost:${PORT}/analytics`);
  console.log(`   • Evaluation: http://localhost:${PORT}/evaluation`);
  console.log(`   • Teacher Login: http://localhost:${PORT}/auth/teacher_login.html`);
  console.log(`   • Teacher Signup: http://localhost:${PORT}/auth/teacher_signup.html`);
  console.log(`   • Pricing: http://localhost:${PORT}/pricing.html`);
});
