// API Configuration
const API_BASE_URL = 'http://localhost:8001/api';

// API Service Class
class APIService {
    constructor() {
        this.token = localStorage.getItem('access_token');
    }

    // Set authentication token
    setToken(token) {
        this.token = token;
        localStorage.setItem('access_token', token);
    }

    // Remove authentication token
    removeToken() {
        this.token = null;
        localStorage.removeItem('access_token');
    }

    // Get headers with authentication
    getHeaders(includeAuth = true) {
        const headers = {
            'Content-Type': 'application/json',
        };
        
        if (includeAuth && this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }

    // Generic API request method
    async request(endpoint, method = 'GET', data = null, includeAuth = true) {
        const url = `${API_BASE_URL}${endpoint}`;
        const config = {
            method,
            headers: this.getHeaders(includeAuth),
        };

        if (data) {
            if (data instanceof FormData) {
                // Remove Content-Type for FormData to let browser set it with boundary
                delete config.headers['Content-Type'];
                config.body = data;
            } else {
                config.body = JSON.stringify(data);
            }
        }

        try {
            const response = await fetch(url, config);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || `HTTP error! status: ${response.status}`);
            }

            return result;
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }

    // Authentication methods
    async login(email, password) {
        const response = await this.request('/auth/login', 'POST', { email, password }, false);
        if (response.access_token) {
            this.setToken(response.access_token);
        }
        return response;
    }

    async register(userData) {
        const response = await this.request('/auth/register', 'POST', userData, false);
        if (response.access_token) {
            this.setToken(response.access_token);
        }
        return response;
    }

    async getCurrentUser() {
        return await this.request('/auth/me');
    }

    async logout() {
        this.removeToken();
        window.location.href = '/';
    }

    // Analytics methods
    async getDashboardAnalytics() {
        return await this.request('/analytics/dashboard');
    }

    async getSubmissionAnalytics(assignmentId) {
        return await this.request(`/analytics/submissions/${assignmentId}`);
    }

    // Analytics methods for new workflow
    async connectGoogleClassroomAnalytics(authCode) {
        return await this.request('/analytics/connect/google-classroom', 'POST', { auth_code: authCode });
    }

    async connectMoodleAnalytics(connectionData) {
        return await this.request('/analytics/connect/moodle', 'POST', connectionData);
    }

    async getCourseAnalytics(platformType = null) {
        const params = platformType ? `?platform=${platformType}` : '';
        return await this.request(`/analytics/courses${params}`);
    }

    async getExamAnalytics(courseId) {
        return await this.request(`/analytics/courses/${courseId}/exams`);
    }

    async getDetailedExamAnalytics(examId) {
        return await this.request(`/analytics/exams/${examId}/detailed`);
    }

    async getStudentPerformanceAnalytics(examId) {
        return await this.request(`/analytics/exams/${examId}/students`);
    }

    async getQuestionAnalytics(examId) {
        return await this.request(`/analytics/exams/${examId}/questions`);
    }

    async getAIPerformanceMetrics(examId) {
        return await this.request(`/analytics/exams/${examId}/ai-performance`);
    }

    async getTrendsAnalytics(courseId, timeRange = '30d') {
        return await this.request(`/analytics/courses/${courseId}/trends?range=${timeRange}`);
    }

    async generateAnalyticsReport(examId, reportType = 'comprehensive') {
        return await this.request(`/analytics/exams/${examId}/report?type=${reportType}`, 'POST');
    }

    async exportAnalyticsData(examId, format = 'csv') {
        return await this.request(`/analytics/exams/${examId}/export?format=${format}`, 'GET');
    }

    // Evaluation methods
    async getAssignments() {
        return await this.request('/evaluation/assignments');
    }

    async createAssignment(assignmentData) {
        return await this.request('/evaluation/assignments', 'POST', assignmentData);
    }

    async submitAssignment(assignmentId, formData) {
        return await this.request(`/evaluation/assignments/${assignmentId}/submit`, 'POST', formData);
    }

    async getAssignmentSubmissions(assignmentId) {
        return await this.request(`/evaluation/assignments/${assignmentId}/submissions`);
    }

    async updateSubmissionGrade(submissionId, formData) {
        return await this.request(`/evaluation/submissions/${submissionId}/grade`, 'PUT', formData);
    }

    // Annotation methods
    async createAnnotation(annotationData) {
        return await this.request('/annotation/annotations', 'POST', annotationData);
    }

    async getSubmissionAnnotations(submissionId) {
        return await this.request(`/annotation/submissions/${submissionId}/annotations`);
    }

    async updateAnnotation(annotationId, annotationText) {
        const formData = new FormData();
        formData.append('annotation_text', annotationText);
        return await this.request(`/annotation/annotations/${annotationId}`, 'PUT', formData);
    }

    async deleteAnnotation(annotationId) {
        return await this.request(`/annotation/annotations/${annotationId}`, 'DELETE');
    }

    async getAnnotationTypes() {
        return await this.request('/annotation/annotation-types');
    }
}

// Global API instance
window.api = new APIService();

// Utility functions
function showToast(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

function showLoader(show = true) {
    let loader = document.getElementById('global-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'global-loader';
        loader.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center';
        loader.style.cssText = 'background: rgba(255,255,255,0.8); z-index: 9999;';
        loader.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        `;
        document.body.appendChild(loader);
    }
    
    loader.style.display = show ? 'flex' : 'none';
}

// Check authentication status
function isAuthenticated() {
    return !!localStorage.getItem('access_token');
}

function redirectToLogin() {
    window.location.href = '/auth/teacher_login.html';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is authenticated for protected pages
    const protectedPages = ['/teacher/', '/analytics', '/evaluation'];
    const currentPath = window.location.pathname;
    
    if (protectedPages.some(page => currentPath.includes(page)) && !isAuthenticated()) {
        redirectToLogin();
        return;
    }

    // Update navigation based on auth status
    updateNavigation();
});

function updateNavigation() {
    const authNav = document.querySelector('.auth-nav');
    if (!authNav) return;

    if (isAuthenticated()) {
        authNav.innerHTML = `
            <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                    <i class="fas fa-user me-1"></i>
                    Account
                </a>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item" href="/teacher/dashboard">Dashboard</a></li>
                    <li><a class="dropdown-item" href="/analytics">Analytics</a></li>
                    <li><hr class="dropdown-divider"></li>
                    <li><a class="dropdown-item" href="#" onclick="api.logout()">Logout</a></li>
                </ul>
            </li>
        `;
    } else {
        authNav.innerHTML = `
            <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                    <i class="fas fa-sign-in-alt me-1"></i>
                    Sign In
                </a>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item" href="/auth/teacher_login.html">Teacher Login</a></li>
                </ul>
            </li>
        `;
    }
}
