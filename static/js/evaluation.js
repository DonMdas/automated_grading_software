// /static/js/evaluation.js

import { api } from './api.js';
import { protectPage } from './auth.js';

let coursesCache = [];
let currentCourseId = null;
let currentCourseworkId = null;
let currentGradingTaskId = null;
let statusCheckInterval = null;

// Page elements
const loadingState = document.getElementById('loading-state');
const connectState = document.getElementById('connect-classroom-state');
const coursesView = document.getElementById('courses-view');
const courseworkView = document.getElementById('coursework-view');

document.addEventListener('DOMContentLoaded', async () => {
    await protectPage();
    initializePage();
    addEventListeners();
});

async function initializePage() {
    showLoading();
    try {
        const status = await api.checkGoogleAuthStatus();
        if (status.has_google_linked) {
            await displayCourses();
        } else {
            displayConnectView(status.auth_url);
        }
    } catch (error) {
        console.error('Initialization failed:', error);
        alert('Could not load your workspace. Please try again.');
    } finally {
        hideLoading();
    }
}

function addEventListeners() {
    document.getElementById('refresh-courses-btn').addEventListener('click', displayCourses);
    document.getElementById('back-to-courses-btn').addEventListener('click', showCoursesView);
}

function showLoading() {
    loadingState.classList.remove('d-none');
    connectState.classList.add('d-none');
    coursesView.classList.add('d-none');
    courseworkView.classList.add('d-none');
}

function hideLoading() {
    loadingState.classList.add('d-none');
}

function displayConnectView(authUrl) {
    connectState.classList.remove('d-none');
    document.getElementById('connect-google-btn').onclick = () => {
        window.location.href = authUrl;
    };
}

async function displayCourses() {
    showCoursesView();
    const grid = document.getElementById('courses-grid');
    grid.innerHTML = '<div class="text-center py-5"><div class="spinner-border"></div></div>';
    
    try {
        coursesCache = await api.getCourses();
        if (coursesCache.length === 0) {
            grid.innerHTML = '<div class="col-12"><div class="alert alert-info">No Google Classroom courses found.</div></div>';
            return;
        }

        grid.innerHTML = coursesCache.map(course => `
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 shadow-sm hover-lift" style="cursor: pointer;" data-course-id="${course.id}">
                    <div class="card-body">
                        <h5 class="card-title">${course.name}</h5>
                        <p class="card-subtitle mb-2 text-muted">${course.section || 'General'}</p>
                        <p class="card-text small">${course.description || 'No description.'}</p>
                    </div>
                    <div class="card-footer bg-transparent border-0">
                        <span class="badge bg-primary">${course.courseState}</span>
                    </div>
                </div>
            </div>
        `).join('');

        // Add click listeners to course cards
        grid.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', () => {
                displayCoursework(card.dataset.courseId);
            });
        });
    } catch(error) {
        grid.innerHTML = `<div class="col-12"><div class="alert alert-danger">Failed to load courses: ${error.message}</div></div>`;
    }
}

async function displayCoursework(courseId) {
    currentCourseId = courseId;
    showCourseworkView();
    
    const course = coursesCache.find(c => c.id === courseId);
    document.getElementById('course-name-header').textContent = course.name;

    const list = document.getElementById('coursework-list');
    list.innerHTML = '<div class="list-group-item text-center"><div class="spinner-border spinner-border-sm"></div></div>';
    document.getElementById('submissions-list').innerHTML = '<div class="list-group-item text-muted">Select an assignment to view submissions.</div>';

    try {
        const coursework = await api.getCoursework(courseId);
        if(coursework.length === 0) {
            list.innerHTML = '<div class="list-group-item text-muted">No assignments found for this course.</div>';
            return;
        }

        list.innerHTML = coursework.map(cw => `
            <a href="#" class="list-group-item list-group-item-action" data-coursework-id="${cw.id}">
                ${cw.title}
            </a>
        `).join('');

        list.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                list.querySelectorAll('a').forEach(l => l.classList.remove('active'));
                link.classList.add('active');
                displaySubmissions(link.dataset.courseworkId, link.textContent);
            });
        });

    } catch(error) {
        list.innerHTML = `<div class="list-group-item text-danger">Failed to load assignments: ${error.message}</div>`;
    }
}

async function displaySubmissions(courseworkId, courseworkName) {
    console.log('🔍 displaySubmissions called for:', courseworkId, courseworkName);
    currentCourseworkId = courseworkId;
    document.getElementById('coursework-name-header').textContent = courseworkName;
    const list = document.getElementById('submissions-list');
    list.innerHTML = '<div class="list-group-item text-center"><div class="spinner-border spinner-border-sm"></div> Loading submissions...</div>';

    const header = document.getElementById('coursework-name-header');
    const existingButton = header.parentElement.querySelector('.evaluate-btn');
    if (existingButton) existingButton.remove();

    try {
        // First, try to load submissions from Google Classroom into database
        console.log('Loading submissions from Google Classroom...');
        const loadResponse = await fetch(`/api/submissions/load/${currentCourseId}/${courseworkId}`, {
            method: 'POST',
            credentials: 'include'
        });

        if (loadResponse.ok) {
            const loadData = await loadResponse.json();
            console.log(`Loaded ${loadData.loaded_count} submissions from Google Classroom`);
        } else {
            console.warn('Failed to load submissions from Google Classroom, continuing with existing data');
        }

        // Now get the submission status from database
        console.log('📡 Fetching submission status from API...');
        const statusResponse = await fetch(`/api/submissions/status/${courseworkId}`, {
            credentials: 'include'
        });
        
        console.log('📡 API Response status:', statusResponse.status);
        
        let submissionsData;
        if (statusResponse.ok) {
            submissionsData = await statusResponse.json();
            console.log('📊 API returned submissions:', submissionsData);
        } else {
            console.error('❌ API call failed:', statusResponse.status, await statusResponse.text());
            // Final fallback - this shouldn't happen now
            submissionsData = {
                submissions: [],
                total_submissions: 0,
                summary: {
                    downloaded: 0,
                    ocr_complete: 0,
                    ocr_failed: 0,
                    graded: 0,
                    grading_failed: 0
                }
            };
        }

        if (submissionsData.submissions.length === 0) {
            list.innerHTML = '<div class="list-group-item text-muted">No submissions found for this assignment in Google Classroom.</div>';
            return;
        }

        // Count ungraded submissions
        const ungradedSubmissions = submissionsData.submissions.filter(sub => 
            !['GRADED'].includes(sub.status)
        );
        const newSubmissions = submissionsData.submissions.filter(sub => 
            ['PENDING', 'DOWNLOADED', 'OCR_COMPLETE', 'GRADING_FAILED'].includes(sub.status)
        );

        // Create smart evaluation buttons (only if not already created)
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'd-flex gap-2 ms-auto evaluation-buttons';
        
        // Check if buttons already exist to prevent duplicates
        const existingButtons = header.parentElement.querySelector('.evaluation-buttons');
        if (existingButtons) {
            existingButtons.remove();
        }

        // Main evaluation button (context-aware)
        const mainEvaluateButton = document.createElement('button');
        mainEvaluateButton.className = 'btn btn-success evaluate-btn';
        
        if (newSubmissions.length > 0) {
            // There are new submissions to grade
            mainEvaluateButton.innerHTML = `<i class="fas fa-play-circle me-2"></i> Evaluate New (${newSubmissions.length})`;
            mainEvaluateButton.title = 'Evaluate only new/ungraded submissions';
        } else if (ungradedSubmissions.length > 0) {
            // There are some ungraded but no new ones
            mainEvaluateButton.innerHTML = `<i class="fas fa-redo me-2"></i> Re-evaluate Failed (${ungradedSubmissions.length})`;
            mainEvaluateButton.title = 'Re-evaluate failed submissions';
        } else {
            // All are graded
            mainEvaluateButton.innerHTML = `<i class="fas fa-check me-2"></i> All Graded`;
            mainEvaluateButton.disabled = true;
            mainEvaluateButton.className = 'btn btn-outline-success evaluate-btn';
        }

        // Evaluation button handler for smart evaluation
        mainEvaluateButton.onclick = async () => {
            // Prevent multiple clicks
            if (mainEvaluateButton.disabled || mainEvaluateButton.innerHTML.includes('spinner-border')) {
                return;
            }
            
            // Prompt for grading version first
            const gradingVersion = await promptForGradingVersion();
            if (!gradingVersion) {
                console.log('User cancelled grading version selection');
                return;
            }
            
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = '.pdf';
            
            fileInput.onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('answer_key', file);
                formData.append('grading_version', gradingVersion);

                try {
                    mainEvaluateButton.disabled = true;
                    mainEvaluateButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';
                    
                    // Use the smart evaluation endpoint
                    const response = await api.evaluateNewSubmissions(currentCourseId, courseworkId, formData);
                    
                    if (response.count === 0) {
                        showSuccessMessage('No new submissions to evaluate!');
                        return;
                    }
                    
                    // Show evaluation progress modal
                    showEvaluationProgress(courseworkId);
                    
                    // Start checking for updates
                    setTimeout(() => checkForUpdates(courseworkId), 2000);
                    
                    // Show success message
                    showSuccessMessage(`Started evaluation for ${response.count} new submissions using grading version ${gradingVersion}! The page will remain accessible while processing.`);
                
                } catch (error) {
                    showErrorMessage(`Error starting evaluation: ${error.message}`);
                } finally {
                    // Reset button state after a delay
                    setTimeout(() => {
                        displaySubmissions(courseworkId, document.getElementById('coursework-name-header').textContent);
                    }, 3000);
                }
            };
            
            fileInput.click();
        };

        // Add "Evaluate All" button as secondary option
        if (submissionsData.submissions.length > 0) {
            const evaluateAllButton = document.createElement('button');
            evaluateAllButton.className = 'btn btn-outline-warning evaluate-all-btn';
            evaluateAllButton.innerHTML = `<i class="fas fa-refresh me-2"></i> Re-evaluate All (${submissionsData.submissions.length})`;
            evaluateAllButton.title = 'Re-evaluate all submissions (including already graded ones)';
            
            evaluateAllButton.onclick = async () => {
                // Prevent multiple clicks
                if (evaluateAllButton.disabled || evaluateAllButton.innerHTML.includes('spinner-border')) {
                    return;
                }
                
                const confirmed = confirm(
                    `This will re-evaluate ALL ${submissionsData.submissions.length} submissions, including already graded ones.\n\n` +
                    `This is usually not necessary unless you have a new answer key.\n\n` +
                    `Are you sure you want to continue?`
                );
                
                if (!confirmed) return;
                
                // Prompt for grading version
                const gradingVersion = await promptForGradingVersion();
                if (!gradingVersion) {
                    console.log('User cancelled grading version selection');
                    return;
                }
                
                const fileInput = document.createElement('input');
                fileInput.type = 'file';
                fileInput.accept = '.pdf';
                
                fileInput.onchange = async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    const formData = new FormData();
                    formData.append('answer_key', file);
                    formData.append('grading_version', gradingVersion);

                    try {
                        evaluateAllButton.disabled = true;
                        evaluateAllButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Re-evaluating...';
                        
                        const response = await api.startEvaluationProcess(currentCourseId, courseworkId, formData);
                        
                        showEvaluationProgress(courseworkId);
                        setTimeout(() => checkForUpdates(courseworkId), 2000);
                        showSuccessMessage(`Re-evaluation started for all submissions using grading version ${gradingVersion}! The page will remain accessible while processing.`);
                    
                    } catch (error) {
                        showErrorMessage(`Error starting re-evaluation: ${error.message}`);
                    } finally {
                        // Reset button state after a delay
                        setTimeout(() => {
                            displaySubmissions(courseworkId, document.getElementById('coursework-name-header').textContent);
                        }, 3000);
                    }
                };
                
                fileInput.click();
            };
            
            buttonContainer.appendChild(evaluateAllButton);
        }

        buttonContainer.appendChild(mainEvaluateButton);
        header.parentElement.appendChild(buttonContainer);

        // Render submissions with status and individual buttons
        list.innerHTML = submissionsData.submissions.map(sub => {
            const statusBadge = getStatusBadge(sub.status);
            const viewResultsButton = sub.can_view_results ? 
                `<button class="btn btn-sm btn-outline-primary ms-1" onclick="viewResults('${sub.student_id}')">
                    <i class="fas fa-eye me-1"></i>View Results
                </button>` : '';

            // Individual evaluation button - Always show for all submissions
            let evaluateButton = '';
            
            if (['PENDING', 'DOWNLOADED', 'OCR_COMPLETE', 'GRADING_FAILED', 'OCR_FAILED'].includes(sub.status)) {
                // For ungraded submissions - Green "Evaluate" button
                evaluateButton = `
                    <button class="btn btn-sm btn-outline-success ms-1" onclick="evaluateIndividual('${sub.student_id}', '${sub.student_name}')">
                        <i class="fas fa-play me-1"></i>Evaluate
                    </button>`;
            } else if (sub.status === 'GRADED') {
                // For graded submissions - Orange "Re-evaluate" button
                evaluateButton = `
                    <button class="btn btn-sm btn-outline-warning ms-1" onclick="evaluateIndividual('${sub.student_id}', '${sub.student_name}')">
                        <i class="fas fa-redo me-1"></i>Re-evaluate
                    </button>`;
            } else {
                // For any other status - Default evaluate button
                evaluateButton = `
                    <button class="btn btn-sm btn-outline-secondary ms-1" onclick="evaluateIndividual('${sub.student_id}', '${sub.student_name}')">
                        <i class="fas fa-play me-1"></i>Evaluate
                    </button>`;
            }

            return `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${sub.student_name || 'Unknown Student'}</strong><br>
                        <small class="text-muted">
                            Status: ${statusBadge}
                            ${sub.status === 'GRADED' ? `<i class="fas fa-check-circle text-success ms-2"></i>` : ''}
                        </small>
                    </div>
                    <div class="d-flex align-items-center">
                        ${viewResultsButton}
                        ${evaluateButton}
                    </div>
                </div>
            `;
        }).join('');

        // Show summary if there are submissions
        if (submissionsData.total_submissions > 0) {
            const summaryHtml = `
                <div class="list-group-item bg-light">
                    <small class="text-muted">
                        <strong>Summary:</strong> 
                        ${submissionsData.summary.graded} graded, 
                        ${submissionsData.summary.ocr_complete} OCR complete, 
                        ${submissionsData.summary.downloaded} downloaded,
                        ${submissionsData.total_submissions - submissionsData.summary.graded - submissionsData.summary.ocr_complete - submissionsData.summary.downloaded} pending
                    </small>
                </div>
            `;
            list.innerHTML += summaryHtml;
        }

        // Start automatic status checking if there are active processes
        const hasActiveProcesses = submissionsData.submissions.some(sub => 
            ['DOWNLOADED', 'OCR_COMPLETE', 'GRADING'].includes(sub.status)
        );
        
        if (hasActiveProcesses) {
            setTimeout(() => checkGradingReadiness(courseworkId), 5000);
        }

    } catch(error) {
        list.innerHTML = `<div class="list-group-item text-danger">Failed to load submissions: ${error.message}</div>`;
        console.error('Error loading submissions:', error);
    }
}

function showCoursesView() {
    coursesView.classList.remove('d-none');
    courseworkView.classList.add('d-none');
    connectState.classList.add('d-none');
}

function showCourseworkView() {
    coursesView.classList.add('d-none');
    courseworkView.classList.remove('d-none');
    connectState.classList.add('d-none');
}

// --- NEW: GRADING FUNCTIONALITY ---

async function checkGradingReadiness(courseworkId) {
    try {
        const response = await fetch(`/api/classroom/courses/${currentCourseId}/coursework/${courseworkId}/submissions`, {
            credentials: 'include'
        });
        
        if (!response.ok) return;
        
        const submissions = await response.json();
        
        // Check if we have any OCR-complete submissions
        const hasOcrComplete = submissions.some(sub => sub.status === 'OCR_COMPLETE');
        
        if (hasOcrComplete) {
            showGradingOptions(courseworkId);
        } else {
            // Continue checking every 10 seconds
            setTimeout(() => checkGradingReadiness(courseworkId), 10000);
        }
    } catch (error) {
        console.error('Error checking grading readiness:', error);
    }
}

function showGradingOptions(courseworkId) {
    const header = document.getElementById('coursework-name-header');
    const existingGradingSection = header.parentElement.querySelector('.grading-section');
    if (existingGradingSection) existingGradingSection.remove();

    const gradingSection = document.createElement('div');
    gradingSection.className = 'grading-section mt-3 p-3 border rounded bg-light';
    gradingSection.innerHTML = `
        <h5><i class="fas fa-graduation-cap me-2"></i>Grading Options</h5>
        <p class="text-muted">OCR processing is complete. You can now start the grading process.</p>
        
        <div class="mb-3">
            <label for="grading-version" class="form-label">Select Grading Version:</label>
            <select class="form-select" id="grading-version">
                <option value="v2" selected>Version 2 (Recommended)</option>
                <option value="v1">Version 1</option>
            </select>
        </div>
        
        <div class="d-flex gap-2">
            <button class="btn btn-primary" id="start-grading-btn">
                <i class="fas fa-play me-2"></i>Start Grading
            </button>
            <button class="btn btn-outline-secondary" id="check-grading-status-btn">
                <i class="fas fa-refresh me-2"></i>Check Status
            </button>
            <button class="btn btn-success" id="view-results-btn" style="display: none;">
                <i class="fas fa-eye me-2"></i>View Results
            </button>
        </div>
        
        <div id="grading-status" class="mt-3" style="display: none;">
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: 0%"></div>
            </div>
            <p class="mt-2 mb-0" id="grading-message"></p>
        </div>
    `;
    
    header.parentElement.appendChild(gradingSection);
    
    // Add event listeners
    document.getElementById('start-grading-btn').addEventListener('click', () => startGrading(courseworkId));
    document.getElementById('check-grading-status-btn').addEventListener('click', () => checkGradingStatus(courseworkId));
    document.getElementById('view-results-btn').addEventListener('click', () => viewResults(courseworkId));
    
    // Check if grading is already in progress
    checkGradingStatus(courseworkId);
}

async function startGrading(courseworkId) {
    const versionSelect = document.getElementById('grading-version');
    const startBtn = document.getElementById('start-grading-btn');
    const gradingVersion = versionSelect.value;
    
    try {
        startBtn.disabled = true;
        startBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';
        
        const response = await fetch(`/api/grading/start/${courseworkId}?grading_version=${gradingVersion}`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start grading');
        }
        
        const result = await response.json();
        currentGradingTaskId = result.task_id;
        
        alert(`Grading started successfully! Task ID: ${result.task_id}`);
        
        // Start status checking
        document.getElementById('grading-status').style.display = 'block';
        startStatusChecking();
        
    } catch (error) {
        alert(`Error starting grading: ${error.message}`);
    } finally {
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Grading';
    }
}

async function checkGradingStatus(courseworkId) {
    try {
        const response = await fetch(`/api/grading/tasks/${courseworkId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) return;
        
        const tasks = await response.json();
        
        if (tasks.length > 0) {
            const latestTask = tasks[0];
            currentGradingTaskId = latestTask.task_id;
            updateGradingStatus(latestTask);
            
            if (latestTask.status === 'RUNNING') {
                startStatusChecking();
            }
        }
    } catch (error) {
        console.error('Error checking grading status:', error);
    }
}

function startStatusChecking() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    statusCheckInterval = setInterval(async () => {
        if (!currentGradingTaskId) return;
        
        try {
            const response = await fetch(`/api/grading/status/${currentGradingTaskId}`, {
                credentials: 'include'
            });
            
            if (!response.ok) return;
            
            const task = await response.json();
            updateGradingStatus(task);
            
            if (task.status === 'COMPLETED' || task.status === 'FAILED') {
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
            }
        } catch (error) {
            console.error('Error checking task status:', error);
        }
    }, 3000); // Check every 3 seconds
}

function updateGradingStatus(task) {
    const statusDiv = document.getElementById('grading-status');
    const progressBar = statusDiv.querySelector('.progress-bar');
    const messageP = document.getElementById('grading-message');
    const viewResultsBtn = document.getElementById('view-results-btn');
    
    statusDiv.style.display = 'block';
    progressBar.style.width = `${task.progress}%`;
    progressBar.textContent = `${task.progress}%`;
    messageP.textContent = task.message || 'Processing...';
    
    // Update progress bar color based on status
    progressBar.className = 'progress-bar';
    if (task.status === 'COMPLETED') {
        progressBar.classList.add('bg-success');
        viewResultsBtn.style.display = 'inline-block';
    } else if (task.status === 'FAILED') {
        progressBar.classList.add('bg-danger');
    } else if (task.status === 'RUNNING') {
        progressBar.classList.add('bg-primary');
    }
}

async function viewResults(courseworkId) {
    try {
        const response = await fetch(`/api/results/${courseworkId}`, {
            credentials: 'include'
        });
        
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const textResponse = await response.text();
            console.error('Non-JSON response received:', textResponse.substring(0, 200));
            throw new Error(`Server returned ${response.status}: ${response.statusText}. Expected JSON but got ${contentType || 'unknown content type'}`);
        }
        
        if (!response.ok) {
            try {
                const error = await response.json();
                throw new Error(error.detail || error.error || 'Failed to fetch results');
            } catch (jsonError) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
        }
        
        const results = await response.json();
        
        // Check if results contain error information
        if (results.error) {
            throw new Error(results.error);
        }
        
        displayResults(results);
        
    } catch (error) {
        console.error('Full error details:', error);
        alert(`Error fetching results: ${error.message}`);
    }
}

function displayResults(results) {
    const resultsModal = document.createElement('div');
    resultsModal.className = 'modal fade';
    resultsModal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Grading Results</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <h6>Summary</h6>
                        <p>Total Graded Submissions: <strong>${results.total_graded_submissions}</strong></p>
                    </div>
                    
                    <div class="accordion" id="resultsAccordion">
                        ${results.results.map((student, index) => `
                            <div class="accordion-item">
                                <h2 class="accordion-header" id="heading${index}">
                                    <button class="accordion-button ${index === 0 ? '' : 'collapsed'}" 
                                            type="button" data-bs-toggle="collapse" 
                                            data-bs-target="#collapse${index}">
                                        ${student.student_name} (${student.total_questions} questions)
                                    </button>
                                </h2>
                                <div id="collapse${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" 
                                     data-bs-parent="#resultsAccordion">
                                    <div class="accordion-body">
                                        <button class="btn btn-sm btn-primary mb-3" 
                                                onclick="viewDetailedResults('${results.coursework_id}', '${student.student_id}')">
                                            View Detailed Results
                                        </button>
                                        <div class="row">
                                            ${student.results.slice(0, 3).map(result => `
                                                <div class="col-md-4">
                                                    <div class="card">
                                                        <div class="card-body">
                                                            <h6 class="card-title">Q${result.meta.id}</h6>
                                                            <p class="card-text small">${result.meta.original_answer.substring(0, 100)}...</p>
                                                            <span class="badge bg-${result.meta.predicted_grade === '1' ? 'success' : 'warning'}">
                                                                Grade: ${result.meta.predicted_grade}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            `).join('')}
                                        </div>
                                        ${student.results.length > 3 ? `<p class="text-muted mt-2">... and ${student.results.length - 3} more questions</p>` : ''}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(resultsModal);
    const modal = new bootstrap.Modal(resultsModal);
    modal.show();
    
    // Remove modal from DOM when closed
    resultsModal.addEventListener('hidden.bs.modal', () => {
        resultsModal.remove();
    });
}

window.viewDetailedResults = async function(courseworkId, studentId) {
    try {
        const response = await fetch(`/api/results/${courseworkId}/${studentId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to fetch detailed results');
        }
        
        const studentResults = await response.json();
        displayDetailedResults(studentResults);
        
    } catch (error) {
        alert(`Error fetching detailed results: ${error.message}`);
    }
};

function displayDetailedResults(studentResults) {
    const detailModal = document.createElement('div');
    detailModal.className = 'modal fade';
    detailModal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Detailed Results - ${studentResults.student_name}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <h6>Summary</h6>
                        <div class="row">
                            <div class="col-md-3">
                                <strong>Total Questions:</strong> ${studentResults.grading_summary.total_questions}
                            </div>
                            <div class="col-md-3">
                                <strong>Avg Similarity:</strong> ${(studentResults.grading_summary.average_similarity * 100).toFixed(1)}%
                            </div>
                            <div class="col-md-3">
                                <strong>Need Review:</strong> ${studentResults.grading_summary.questions_needing_review}
                            </div>
                        </div>
                    </div>
                    
                    <div class="accordion" id="detailAccordion">
                        ${studentResults.results.map((result, index) => `
                            <div class="accordion-item">
                                <h2 class="accordion-header" id="detailHeading${index}">
                                    <button class="accordion-button collapsed" type="button" 
                                            data-bs-toggle="collapse" data-bs-target="#detailCollapse${index}">
                                        Question ${result.question_id} 
                                        <span class="badge bg-${result.predicted_grade === '1' ? 'success' : 'warning'} ms-2">
                                            Grade: ${result.predicted_grade}
                                        </span>
                                        <span class="badge bg-info ms-2">
                                            Similarity: ${(result.similarity_scores.full_similarity * 100).toFixed(1)}%
                                        </span>
                                    </button>
                                </h2>
                                <div id="detailCollapse${index}" class="accordion-collapse collapse" 
                                     data-bs-parent="#detailAccordion">
                                    <div class="accordion-body">
                                        <div class="row">
                                            <div class="col-md-8">
                                                <h6>Student Answer:</h6>
                                                <p class="border p-2 bg-light">${result.student_answer}</p>
                                                
                                                <h6>Detected Spans:</h6>
                                                ${result.spans.map(span => `
                                                    <span class="badge bg-secondary me-1">${span.label}</span>
                                                `).join('')}
                                            </div>
                                            <div class="col-md-4">
                                                <h6>Scores:</h6>
                                                <ul class="list-unstyled">
                                                    <li><strong>Full Similarity:</strong> ${(result.similarity_scores.full_similarity * 100).toFixed(1)}%</li>
                                                    <li><strong>TF-IDF:</strong> ${(result.similarity_scores.tfidf_similarity * 100).toFixed(1)}%</li>
                                                    <li><strong>Structure:</strong> ${(result.similarity_scores.structure_similarity * 100).toFixed(1)}%</li>
                                                    <li><strong>Components:</strong> ${result.structure_components}</li>
                                                </ul>
                                                
                                                ${result.requires_llm_evaluation.length > 0 ? `
                                                    <div class="alert alert-warning">
                                                        <strong>Requires Review:</strong><br>
                                                        ${result.requires_llm_evaluation.join(', ')}
                                                    </div>
                                                ` : ''}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(detailModal);
    const modal = new bootstrap.Modal(detailModal);
    modal.show();
    
    // Remove modal from DOM when closed
    detailModal.addEventListener('hidden.bs.modal', () => {
        detailModal.remove();
    });
}

// Helper functions for the enhanced UI

function getStatusBadge(status) {
    const statusMap = {
        'PENDING': '<span class="badge bg-secondary">Pending</span>',
        'DOWNLOADED': '<span class="badge bg-info">Downloaded</span>',
        'OCR_COMPLETE': '<span class="badge bg-primary">OCR Complete</span>',
        'OCR_FAILED': '<span class="badge bg-danger">OCR Failed</span>',
        'GRADING': '<span class="badge bg-warning">Grading</span>',
        'GRADED': '<span class="badge bg-success">Graded</span>',
        'GRADING_FAILED': '<span class="badge bg-danger">Grading Failed</span>',
        'DOWNLOADING': '<span class="badge bg-info">Downloading</span>',
        'OCR_IN_PROGRESS': '<span class="badge bg-primary">OCR In Progress</span>'
    };
    
    return statusMap[status] || '<span class="badge bg-secondary">Unknown</span>';
}

function showEvaluationProgress(courseworkId) {
    // Remove existing modal if present
    const existingModal = document.getElementById('evaluationProgressModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'evaluationProgressModal';
    modal.setAttribute('data-bs-backdrop', 'static');
    modal.setAttribute('data-bs-keyboard', 'false');
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title">
                        <i class="fas fa-cogs me-2"></i>
                        Evaluation in Progress
                    </h5>
                </div>
                <div class="modal-body">
                    <div class="alert alert-info mb-4">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>Please be patient!</strong> We're processing all submissions through OCR and grading. This may take several minutes.
                    </div>
                    
                    <div class="progress-steps">
                        <div class="step completed" id="step-upload">
                            <div class="step-icon">
                                <i class="fas fa-check text-success"></i>
                            </div>
                            <div class="step-content">
                                <h6>Files Uploaded</h6>
                                <small class="text-muted">Answer key and student submissions uploaded</small>
                            </div>
                        </div>
                        
                        <div class="step active" id="step-ocr">
                            <div class="step-icon">
                                <div class="spinner-border spinner-border-sm"></div>
                            </div>
                            <div class="step-content">
                                <h6>OCR Processing</h6>
                                <small class="text-muted">Extracting text from all documents</small>
                            </div>
                        </div>
                        
                        <div class="step" id="step-grading">
                            <div class="step-icon">
                                <i class="fas fa-clock text-muted"></i>
                            </div>
                            <div class="step-content">
                                <h6>AI Grading</h6>
                                <small class="text-muted">Analyzing answers and generating grades</small>
                            </div>
                        </div>
                        
                        <div class="step" id="step-complete">
                            <div class="step-icon">
                                <i class="fas fa-clock text-muted"></i>
                            </div>
                            <div class="step-content">
                                <h6>Finalizing Results</h6>
                                <small class="text-muted">Preparing results for viewing</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="real-time-stats mt-4">
                        <div class="row text-center">
                            <div class="col-3">
                                <div class="stat-card">
                                    <div class="stat-number" id="processed-count">0</div>
                                    <div class="stat-label">Processed</div>
                                </div>
                            </div>
                            <div class="col-3">
                                <div class="stat-card">
                                    <div class="stat-number" id="graded-count">0</div>
                                    <div class="stat-label">Graded</div>
                                </div>
                            </div>
                            <div class="col-3">
                                <div class="stat-card">
                                    <div class="stat-number" id="failed-count">0</div>
                                    <div class="stat-label">Failed</div>
                                </div>
                            </div>
                            <div class="col-3">
                                <div class="stat-card">
                                    <div class="stat-number" id="total-count">-</div>
                                    <div class="stat-label">Total</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="minimizeModal()">
                        <i class="fas fa-window-minimize me-2"></i>Run in Background
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Store modal reference for updates
    window.evaluationProgressModal = bsModal;
    window.evaluationProgressElement = modal;
    
    // Add custom CSS for the progress steps
    if (!document.getElementById('progress-steps-css')) {
        const style = document.createElement('style');
        style.id = 'progress-steps-css';
        style.textContent = `
            .progress-steps {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            
            .step {
                display: flex;
                align-items: center;
                gap: 15px;
                padding: 15px;
                border-radius: 8px;
                transition: all 0.3s ease;
                opacity: 0.6;
                background-color: #f8f9fa;
            }
            
            .step.active {
                opacity: 1;
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
            }
            
            .step.completed {
                opacity: 1;
                background-color: #e8f5e8;
                border: 1px solid #4caf50;
            }
            
            .step-icon {
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                background-color: #f5f5f5;
                flex-shrink: 0;
            }
            
            .step-content h6 {
                margin: 0 0 4px 0;
                font-weight: 600;
            }
            
            .step-content small {
                line-height: 1.3;
            }
            
            .real-time-stats {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
            }
            
            .stat-card {
                text-align: center;
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
                color: #2196f3;
            }
            
            .stat-label {
                font-size: 0.9rem;
                color: #666;
                margin-top: 5px;
            }
        `;
        document.head.appendChild(style);
    }
}

function checkForUpdates(courseworkId) {
    let pollCount = 0;
    const maxPolls = 120; // Maximum 10 minutes of polling (120 * 5 seconds)
    
    const updateInterval = setInterval(async () => {
        pollCount++;
        
        try {
            // Check submission status
            const response = await fetch(`/api/submissions/status/${courseworkId}`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update progress modal if open
                updateProgressModal(data.summary);
                
                // Update real-time stats
                updateRealTimeStats(data.summary, data.total_submissions);
                
                // Update individual submission statuses without full refresh
                updateSubmissionStatuses(data.submissions);
                
                // Only do full refresh every 5 polls to avoid UI issues
                if (pollCount % 5 === 0) {
                    const courseworkName = document.getElementById('coursework-name-header').textContent;
                    displaySubmissions(courseworkId, courseworkName);
                }
                
                // Stop checking if all submissions are processed OR if we've been polling too long
                const totalProcessed = data.summary.graded + data.summary.grading_failed + data.summary.ocr_failed;
                const allProcessed = totalProcessed >= data.total_submissions;
                const timeoutReached = pollCount >= maxPolls;
                
                if (allProcessed || timeoutReached) {
                    clearInterval(updateInterval);
                    
                    // Close progress modal after a delay
                    if (window.evaluationProgressModal) {
                        setTimeout(() => {
                            window.evaluationProgressModal.hide();
                            if (timeoutReached && !allProcessed) {
                                showTimeoutNotification(data.summary, data.total_submissions);
                            } else {
                                showCompletionNotification(data.summary);
                            }
                        }, 3000);
                    }
                }
            } else {
                // If we get an error response, stop polling after a few attempts
                if (pollCount >= 5) {
                    clearInterval(updateInterval);
                    console.error('Stopped polling due to repeated errors');
                    if (window.evaluationProgressModal) {
                        window.evaluationProgressModal.hide();
                    }
                }
            }
        } catch (error) {
            console.error('Error checking for updates:', error);
            
            // Stop polling if we get too many errors
            if (pollCount >= 5) {
                clearInterval(updateInterval);
                if (window.evaluationProgressModal) {
                    window.evaluationProgressModal.hide();
                }
            }
        }
    }, 5000); // Check every 5 seconds
}

function updateProgressModal(summary) {
    if (!window.evaluationProgressElement) return;
    
    const ocrStep = window.evaluationProgressElement.querySelector('#step-ocr');
    const gradingStep = window.evaluationProgressElement.querySelector('#step-grading');
    const completeStep = window.evaluationProgressElement.querySelector('#step-complete');
    
    // Update OCR step
    if (summary.ocr_complete > 0) {
        ocrStep.querySelector('.step-icon').innerHTML = '<i class="fas fa-check text-success"></i>';
        ocrStep.classList.add('completed');
        ocrStep.classList.remove('active');
        
        // Start grading step
        gradingStep.classList.add('active');
        gradingStep.querySelector('.step-icon').innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
    }
    
    // Update grading step
    if (summary.graded > 0) {
        gradingStep.querySelector('.step-icon').innerHTML = '<i class="fas fa-check text-success"></i>';
        gradingStep.classList.add('completed');
        gradingStep.classList.remove('active');
        
        // Start complete step
        completeStep.classList.add('active');
        completeStep.querySelector('.step-icon').innerHTML = '<i class="fas fa-check text-success"></i>';
        completeStep.classList.add('completed');
    }
}

function updateRealTimeStats(summary, totalSubmissions) {
    if (!window.evaluationProgressElement) return;
    
    const processedCount = summary.ocr_complete + summary.ocr_failed;
    const gradedCount = summary.graded;
    const failedCount = summary.ocr_failed + summary.grading_failed;
    
    const processedElement = window.evaluationProgressElement.querySelector('#processed-count');
    const gradedElement = window.evaluationProgressElement.querySelector('#graded-count');
    const failedElement = window.evaluationProgressElement.querySelector('#failed-count');
    const totalElement = window.evaluationProgressElement.querySelector('#total-count');
    
    if (processedElement) processedElement.textContent = processedCount;
    if (gradedElement) gradedElement.textContent = gradedCount;
    if (failedElement) failedElement.textContent = failedCount;
    if (totalElement) totalElement.textContent = totalSubmissions;
}

function showCompletionNotification(summary) {
    const notification = document.createElement('div');
    notification.className = 'alert alert-success alert-dismissible fade show';
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.maxWidth = '400px';
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-check-circle me-2"></i>
            <div>
                <strong>Evaluation Complete!</strong><br>
                <small>
                    ${summary.graded} submissions graded successfully.
                    ${summary.grading_failed > 0 ? `${summary.grading_failed} failed.` : ''}
                </small>
            </div>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 10000);
}

function showTimeoutNotification(summary, totalSubmissions) {
    const notification = document.createElement('div');
    notification.className = 'alert alert-warning alert-dismissible fade show';
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.maxWidth = '450px';
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-clock me-2"></i>
            <div>
                <strong>Evaluation Timeout</strong><br>
                <small>
                    Stopped automatic checking after 10 minutes. 
                    ${summary.graded} of ${totalSubmissions} submissions completed.
                    You can refresh manually to check for updates.
                </small>
            </div>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 15 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 15000);
}

function minimizeModal() {
    if (window.evaluationProgressModal) {
        window.evaluationProgressModal.hide();
        
        // Show a floating progress indicator
        showFloatingProgressIndicator();
    }
}

function showFloatingProgressIndicator() {
    const existing = document.getElementById('floatingProgressIndicator');
    if (existing) existing.remove();
    
    const indicator = document.createElement('div');
    indicator.id = 'floatingProgressIndicator';
    indicator.className = 'floating-progress-indicator';
    indicator.innerHTML = `
        <div class="progress-content">
            <div class="spinner-border spinner-border-sm me-2"></div>
            <span>Processing...</span>
        </div>
    `;
    
    indicator.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #007bff;
        color: white;
        padding: 10px 15px;
        border-radius: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 1000;
        cursor: pointer;
        font-size: 14px;
    `;
    
    indicator.onclick = () => {
        indicator.remove();
        if (window.evaluationProgressModal) {
            window.evaluationProgressModal.show();
        }
    };
    
    document.body.appendChild(indicator);
}

function showSuccessMessage(message) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white bg-success border-0';
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-check-circle me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove from DOM after hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function showErrorMessage(message) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white bg-danger border-0';
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove from DOM after hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function showInfoMessage(message) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white bg-info border-0';
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-info-circle me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove from DOM after hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Global function to view results
window.viewResults = function(studentId) {
    window.open(`/results.html?coursework=${currentCourseworkId}&student=${studentId}`, '_blank');
};

// Individual evaluation function
window.evaluateIndividual = async function(studentId, studentName) {
    console.log(`Starting evaluation for student: ${studentId} (${studentName})`);
    console.log(`Current course ID: ${currentCourseId}`);
    console.log(`Current coursework ID: ${currentCourseworkId}`);
    
    // Check if this student is already being processed
    const existingButtons = document.querySelectorAll(`button[onclick*="${studentId}"]`);
    const isProcessing = Array.from(existingButtons).some(btn => 
        btn.innerHTML.includes('Processing...') || btn.innerHTML.includes('spinner-border')
    );
    
    if (isProcessing) {
        console.log('Student is already being processed, skipping');
        showInfoMessage(`${studentName} is already being processed. Please wait.`);
        return;
    }
    
    // Prompt for grading version
    const gradingVersion = await promptForGradingVersion();
    if (!gradingVersion) {
        console.log('User cancelled grading version selection');
        return;
    }

    const confirmed = confirm(
        `Evaluate submission for: ${studentName}\n\n` +
        `This will process only this student's submission using grading engine ${gradingVersion}.\n\n` +
        `Continue?`
    );
    
    if (!confirmed) {
        console.log('User cancelled evaluation');
        return;
    }

    try {
        // Find and disable the button
        const buttons = document.querySelectorAll(`button[onclick*="${studentId}"]`);
        console.log(`Found ${buttons.length} buttons to disable`);
        
        buttons.forEach(btn => {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processing...';
        });

        // First try without an answer key (backend will check for existing answer_key.json)
        const formData = new FormData();
        formData.append('grading_version', gradingVersion);
        
        try {
            console.log('Attempting to evaluate without answer key first...');
            const response = await api.evaluateSingleSubmission(currentCourseId, currentCourseworkId, studentId, formData);
            
            console.log('Evaluation response:', response);
            
            if (response.used_existing_answer_key) {
                showSuccessMessage(`Started evaluation for ${studentName} using existing answer key! The page will remain accessible while processing.`);
            } else {
                showSuccessMessage(`Started evaluation for ${studentName}! The page will remain accessible while processing.`);
            }
            
            // Update button to show processing state
            buttons.forEach(btn => {
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processing...';
                btn.disabled = true;
                btn.classList.add('btn-secondary');
                btn.classList.remove('btn-outline-success', 'btn-outline-warning');
            });
            
            // Start checking for updates to refresh the display
            setTimeout(() => {
                checkForUpdates(currentCourseworkId);
                // Refresh the display after a longer delay to show updated status
                setTimeout(() => {
                    displaySubmissions(currentCourseworkId, document.getElementById('coursework-name-header').textContent);
                }, 5000);
            }, 2000);
            
        } catch (error) {
            console.log('First attempt failed:', error);
            
            // If it fails because answer key is required, prompt for file
            if (error.message.includes('Answer key PDF is required')) {
                console.log('Answer key PDF is required, prompting user...');
                await promptForAnswerKey(studentId, studentName, gradingVersion);
            } else {
                throw error; // Re-throw other errors
            }
        }
        
    } catch (error) {
        console.error('Error in evaluateIndividual:', error);
        showErrorMessage(`Error evaluating ${studentName}: ${error.message}`);
    }
}

// Helper to prompt for grading version
async function promptForGradingVersion() {
    // Try using a Bootstrap modal first, fallback to native prompt
    try {
        return await showGradingVersionModal();
    } catch (error) {
        console.log('Bootstrap modal failed, using fallback prompt:', error);
        // Fallback to native prompt
        const version = prompt('Select grading version:\n\n1. Enter "v1" for Version 1\n2. Enter "v2" for Version 2 (Recommended)\n\nYour choice:', 'v2');
        if (version === null) return null; // User cancelled
        if (version === 'v1' || version === 'v2') return version;
        return 'v2'; // Default to v2 for invalid input
    }
}

// Bootstrap modal version
async function showGradingVersionModal() {
    return new Promise((resolve) => {
        // Check if Bootstrap is available
        if (typeof bootstrap === 'undefined') {
            throw new Error('Bootstrap not available');
        }
        
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'gradingVersionModal';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Select Grading Engine Version</h5>
                    </div>
                    <div class="modal-body">
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="gradingVersion" id="version-v2" value="v2" checked>
                            <label class="form-check-label" for="version-v2">
                                <strong>Version 2 (Recommended)</strong><br>
                                <small class="text-muted">Latest grading algorithm with improved accuracy</small>
                            </label>
                        </div>
                        <div class="form-check mt-2">
                            <input class="form-check-input" type="radio" name="gradingVersion" id="version-v1" value="v1">
                            <label class="form-check-label" for="version-v1">
                                <strong>Version 1</strong><br>
                                <small class="text-muted">Legacy grading algorithm</small>
                            </label>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" id="grading-version-confirm">OK</button>
                        <button type="button" class="btn btn-secondary" id="grading-version-cancel">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        document.getElementById('grading-version-confirm').onclick = () => {
            const selectedVersion = document.querySelector('input[name="gradingVersion"]:checked').value;
            bsModal.hide();
            modal.remove();
            resolve(selectedVersion);
        };
        
        document.getElementById('grading-version-cancel').onclick = () => {
            bsModal.hide();
            modal.remove();
            resolve(null);
        };
    });
}

// Helper to prompt for answer key when required for individual evaluation
async function promptForAnswerKey(studentId, studentName, gradingVersion) {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'answerKeyModal';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Answer Key Required</h5>
                    </div>
                    <div class="modal-body">
                        <p>No answer key found for this assignment. Please upload an answer key PDF to evaluate <strong>${studentName}</strong>.</p>
                        <input type="file" class="form-control" id="answer-key-file" accept=".pdf">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" id="answer-key-upload">Upload & Evaluate</button>
                        <button type="button" class="btn btn-secondary" id="answer-key-cancel">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        document.getElementById('answer-key-upload').onclick = async () => {
            const fileInput = document.getElementById('answer-key-file');
            const file = fileInput.files[0];
            
            if (!file) {
                alert('Please select an answer key PDF file');
                return;
            }
            
            try {
                const formData = new FormData();
                formData.append('answer_key', file);
                formData.append('grading_version', gradingVersion);
                
                const response = await api.evaluateSingleSubmission(currentCourseId, currentCourseworkId, studentId, formData);
                
                bsModal.hide();
                modal.remove();
                
                showSuccessMessage(`Started evaluation for ${studentName} using grading version ${gradingVersion}!`);
                
                // Start checking for updates
                setTimeout(() => {
                    checkForUpdates(currentCourseworkId);
                    setTimeout(() => {
                        displaySubmissions(currentCourseworkId, document.getElementById('coursework-name-header').textContent);
                    }, 5000);
                }, 2000);
                
                resolve(true);
            } catch (error) {
                showErrorMessage(`Error evaluating ${studentName}: ${error.message}`);
                resolve(false);
            }
        };
        
        document.getElementById('answer-key-cancel').onclick = () => {
            bsModal.hide();
            modal.remove();
            resolve(false);
        };
    });
}