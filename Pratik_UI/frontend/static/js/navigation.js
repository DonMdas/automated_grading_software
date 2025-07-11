/**
 * UNIFIED NAVIGATION SYSTEM
 * This is the ONLY navigation file in the entire application
 * All navigation goes through standard href links - no onclick handlers
 */

// Google OAuth login - only function that needs JS
window.loginWithGoogle = () => {
    console.log('→ Redirecting to Google OAuth');
    window.location.href = '/api/auth/google';
};

// Simple logout
window.logout = () => {
    console.log('→ Logging out');
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    window.location.href = '/';
};

// Utility functions for modals/alerts
window.showDemo = () => alert('Demo feature coming soon!');
window.selectPlan = (planType) => alert(`Selected ${planType} plan. Checkout coming soon!`);

// Analytics specific functions
window.connectGoogleClassroomAnalytics = () => {
    console.log('→ Connecting to Google Classroom Analytics');
    // This would trigger Google OAuth for analytics
    window.location.href = '/api/auth/google-analytics';
};

console.log('✅ Unified navigation loaded - Contact modal uses index.html implementation');
