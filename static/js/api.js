// /static/js/api.js

export class APIService {
    constructor() {
        this.baseUrl = '/api';
        // No longer using localStorage tokens - sessions are managed by cookies
    }

    getHeaders() {
        // Cookies are sent automatically, so we only need Content-Type
        return { 'Content-Type': 'application/json' };
    }

    async request(endpoint, method = 'GET', data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            method,
            headers: this.getHeaders(),
            credentials: 'include', // Include cookies in requests
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    errorDetail = errorJson.detail || errorDetail;
                } catch (e) {
                    console.error("Could not parse error response as JSON.");
                }
                if (response.status === 401) {
                    this.logout();
                }
                throw new Error(errorDetail);
            }

            // Check content-type before assuming JSON
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            } else {
                return await response.text(); 
            }

        } catch (error) {
            console.error(`API request to ${endpoint} failed:`, error);
            throw error;
        }
    }

    async startEvaluationProcess(courseId, courseworkId, formData) {
        const url = `${this.baseUrl}/evaluate/coursework/${courseId}/${courseworkId}`;
        const config = {
            method: 'POST',
            credentials: 'include',
            body: formData // Don't set Content-Type for FormData
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    errorDetail = errorJson.detail || errorDetail;
                } catch (e) {
                    console.error("Could not parse error response as JSON.");
                }
                if (response.status === 401) {
                    this.logout();
                }
                throw new Error(errorDetail);
            }

            return await response.json();
        } catch (error) {
            throw error;
        }
    }

    async evaluateNewSubmissions(courseId, courseworkId, formData) {
        const url = `${this.baseUrl}/submissions/evaluate-new/${courseId}/${courseworkId}`;
        const config = {
            method: 'POST',
            credentials: 'include',
            body: formData
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    errorDetail = errorJson.detail || errorDetail;
                } catch (e) {
                    console.error("Could not parse error response as JSON.");
                }
                throw new Error(errorDetail);
            }

            return await response.json();
        } catch (error) {
            throw error;
        }
    }

    async evaluateSingleSubmission(courseId, courseworkId, studentId, formData) {
        const url = `${this.baseUrl}/submissions/evaluate-single/${courseId}/${courseworkId}/${studentId}`;
        const config = {
            method: 'POST',
            credentials: 'include',
            body: formData
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    errorDetail = errorJson.detail || errorDetail;
                } catch (e) {
                    console.error("Could not parse error response as JSON.");
                }
                throw new Error(errorDetail);
            }

            return await response.json();
        } catch (error) {
            throw error;
        }
    }

    // --- Auth Methods ---
    async getCurrentUser() {
        try {
            const user = await this.request('/users/me');
            return user;
        } catch (error) {
            throw error;
        }
    }

    async logout() {
        try {
            await fetch(`${this.baseUrl}/auth/logout`, {
                method: 'POST',
                credentials: 'include',
            });
        } catch (error) {
            console.error('Logout request failed:', error);
        }
        // Always redirect to login regardless of API response
        window.location.href = '/auth/login.html';
    }

    // --- Google Classroom Methods ---
    async getGoogleAuthUrl(linkAccount = false) {
        return this.request(`/classroom/auth-url?link_account=${linkAccount}`);
    }

    async getLinkAccountUrl() {
        return this.request('/classroom/link-account-url');
    }

    async unlinkGoogleAccount() {
        return this.request('/classroom/unlink-account', 'POST');
    }

    async checkGoogleAuthStatus() {
        return this.request('/classroom/google-auth-check');
    }

    async checkCredentialsStatus() {
        return this.request('/classroom/credentials-status');
    }

    async getCourses() {
        return this.request('/classroom/courses');
    }

    async getCoursework(courseId) {
        return this.request(`/classroom/courses/${courseId}/coursework`);
    }

    async getSubmissions(courseId, courseworkId) {
        return this.request(`/classroom/courses/${courseId}/coursework/${courseworkId}/submissions`);
    }

    async loadSubmissions(courseId, courseworkId) {
        return this.request(`/submissions/load/${courseId}/${courseworkId}`, 'POST');
    }

    // --- Grading Methods ---
    async startGradingProcess(courseworkId, gradingVersion = 'v2') {
        return this.request(`/grading/start/${courseworkId}?grading_version=${gradingVersion}`, 'POST');
    }

    async getGradingStatus(taskId) {
        return this.request(`/grading/status/${taskId}`);
    }

    async getGradingTasks(courseworkId) {
        return this.request(`/grading/tasks/${courseworkId}`);
    }

    async getCourseworkResults(courseworkId) {
        return this.request(`/results/${courseworkId}`);
    }

    async getStudentResults(courseworkId, studentId) {
        return this.request(`/results/${courseworkId}/${studentId}`);
    }
}

export const api = new APIService();