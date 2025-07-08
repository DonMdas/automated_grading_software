// /static/js/global.js

// This file is for scripts that run on public pages like index.html

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle navigation clicks
    window.navigateToHome = () => window.location.href = '/';
    window.navigateToEvaluation = () => window.location.href = '/evaluation.html';
    window.navigateToPricing = () => alert('Pricing page coming soon!');
    window.navigateToAnalytics = () => alert('Analytics page coming soon!');
    
    // Auth navigation
    window.openTeacherLogin = () => window.location.href = '/auth/login.html';
    window.openTeacherSignup = () => window.location.href = '/auth/login.html'; // Redirect to login for Google auth
});