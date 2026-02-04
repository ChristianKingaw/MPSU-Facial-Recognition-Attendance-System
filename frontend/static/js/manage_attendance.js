// Global variables
let currentClassId = null;
let currentStudentId = null;
let currentDate = null;
let currentStatus = null;
let allClasses = [];
let allStudents = [];
let allAttendanceRecords = {}; // Initialize as empty object, not array
let needsClassDetailRefresh = false; // Flag to track if class detail needs refresh
let confirmationCallback = null; // Store the confirmation callback

const SESSION_STATUS_LABELS = {
    active: 'Active session in progress',
    scheduled: 'Session scheduled – waiting to start',
    upcoming: 'Upcoming class (no session yet)',
    completed: 'Attendance completed',
    none: 'No session scheduled today'
};

function parseISODate(value) {
    if (!value) return null;
    const parsed = new Date(value);
    return isNaN(parsed.getTime()) ? null : parsed;
}

function formatShortTime(date) {
    if (!date) return '';
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatShortDateTime(date) {
    if (!date) return '';
    return date.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function formatCountdown(targetDate, referenceIso) {
    if (!targetDate) return '';
    const reference = parseISODate(referenceIso) || new Date();
    const diffMs = targetDate.getTime() - reference.getTime();
    const diffMinutes = Math.abs(Math.round(diffMs / 60000));
    if (diffMinutes === 0) {
        return diffMs >= 0 ? 'less than 1 min left' : 'just ended';
    }
    const unit = diffMinutes === 1 ? 'min' : 'mins';
    if (diffMinutes < 60) {
        return diffMs >= 0 ? `${diffMinutes} ${unit} left` : `${diffMinutes} ${unit} ago`;
    }
    const diffHours = Math.abs(Math.round(diffMs / 3600000));
    const hourUnit = diffHours === 1 ? 'hr' : 'hrs';
    return diffMs >= 0 ? `${diffHours} ${hourUnit} left` : `${diffHours} ${hourUnit} ago`;
}

function buildSessionStatusText(classObj) {
    if (!classObj) return '';
    const statusKey = (classObj.sessionStatus || '').toLowerCase();
    let baseText = SESSION_STATUS_LABELS[statusKey];
    if (!baseText && classObj.hasSessionToday === false) {
        baseText = 'No session recorded for today';
    }
    if (!baseText && classObj.schedule) {
        baseText = `Scheduled (${classObj.schedule})`;
    }
    if (classObj.sessionProcessed) {
        baseText = 'Attendance processed';
    }
    if (classObj.sessionRoomNumber) {
        baseText = baseText ? `${baseText} · Room ${classObj.sessionRoomNumber}` : `Room ${classObj.sessionRoomNumber}`;
    }
    return baseText || '';
}

function buildTimeoutText(classObj) {
    if (!classObj) return '';
    const deadline = parseISODate(classObj.sessionTimeoutDeadline || classObj.sessionScheduledEndTime || classObj.plannedEndTime);
    if (!deadline) return '';
    const countdown = formatCountdown(deadline, classObj.serverTimestamp);
    const labelTime = formatShortTime(deadline);
    const labelDateTime = formatShortDateTime(deadline);
    let prefix = 'Auto timeout';
    if (classObj.sessionStatus === 'completed') {
        prefix = 'Completed at';
    } else if (deadline.getTime() < (parseISODate(classObj.serverTimestamp) || new Date()).getTime()) {
        prefix = 'Auto timeout triggered';
    }
    return `${prefix}: ${labelTime || labelDateTime}${countdown ? ` (${countdown})` : ''}`;
}

function buildScheduleWindowText(classObj) {
    const start = parseISODate(classObj.plannedStartTime || classObj.sessionStartTime);
    const end = parseISODate(classObj.plannedEndTime || classObj.sessionScheduledEndTime);
    if (!start && !end) return '';
    if (start && end) {
        return `Scheduled window: ${formatShortTime(start)} – ${formatShortTime(end)}`;
    }
    if (start) {
        return `Starts at ${formatShortTime(start)}`;
    }
    if (end) {
        return `Ends at ${formatShortTime(end)}`;
    }
    return '';
}

function buildSessionMetaHTML(classObj, { variant = 'compact' } = {}) {
    const lines = [];
    const statusText = buildSessionStatusText(classObj);
    const timeoutText = buildTimeoutText(classObj);
    const scheduleText = buildScheduleWindowText(classObj);
    if (statusText) {
        lines.push(`<span><strong>Status:</strong> ${statusText}</span>`);
    }
    if (timeoutText) {
        lines.push(`<span><strong>Auto timeout:</strong> ${timeoutText}</span>`);
    }
    if (variant === 'detailed' && scheduleText) {
        lines.push(`<span>${scheduleText}</span>`);
    }
    if (!lines.length) return '';
    const lineWrapper = variant === 'compact' ? 'session-meta-line text-muted small d-block' : 'session-meta-line text-muted d-block';
    return `<div class="session-meta ${variant === 'compact' ? 'session-meta--compact' : ''}">
        ${lines.map(line => `<div class="${lineWrapper}">${line}</div>`).join('')}
    </div>`;
}

function updateClassSessionInfo(classObj) {
    const codeElement = document.getElementById('classDetailCode');
    if (!codeElement) return;
    let infoElement = document.getElementById('classSessionInfo');
    if (!infoElement) {
        infoElement = document.createElement('div');
        infoElement.id = 'classSessionInfo';
        infoElement.className = 'mt-2';
        codeElement.insertAdjacentElement('afterend', infoElement);
    }
    infoElement.innerHTML = buildSessionMetaHTML(classObj, { variant: 'detailed' }) || '';
}

// Helper: return local date in YYYY-MM-DD (avoids UTC offset issues from toISOString())
function getLocalISODate(dateObj = new Date()) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    loadClassOverview();
    setupEventListeners();
    setupExportButtons();
    updateCurrentDate(); // Initialize current date
    
    // Update current date every minute
    setInterval(updateCurrentDate, 60000);
    
    // Auto-refresh overview every 5 minutes when the page is visible
    setInterval(function() {
        if (!document.hidden && document.getElementById('classOverview').style.display !== 'none') {
            console.log('Auto-refreshing class overview...');
            refreshClassOverview();
        }
    }, 5 * 60 * 1000); // 5 minutes
    
    // Refresh when page becomes visible (user switches back to tab)
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden && document.getElementById('classOverview').style.display !== 'none') {
            console.log('Page became visible, refreshing class overview...');
            setTimeout(() => refreshClassOverview(), 1000); // Small delay to ensure page is fully loaded
        }
    });
});

// Update current date display
function updateCurrentDate() {
    const currentDateElement = document.getElementById('currentDateValue');
    if (currentDateElement) {
        const now = new Date();
        const formattedDate = now.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        currentDateElement.textContent = formattedDate;
    }
}

// Setup event listeners
function setupEventListeners() {
    // Search input listeners
    const searchInput = document.getElementById('searchInput');
    const studentSearchInput = document.getElementById('studentSearchInput');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            filterClasses(this.value);
        }, 300));
        // clear button behavior for class search
        const clearSearchBtn = document.getElementById('clearSearchBtn');
        if (clearSearchBtn) {
            searchInput.addEventListener('input', function(e) {
                clearSearchBtn.style.display = e.target.value ? 'inline-block' : 'none';
            });
            clearSearchBtn.addEventListener('click', function() {
                searchInput.value = '';
                filterClasses('');
                clearSearchBtn.style.display = 'none';
                searchInput.focus();
            });
        }
    }
    
    if (studentSearchInput) {
        studentSearchInput.addEventListener('input', debounce(function() {
            filterStudents(this.value);
        }, 300));
        // clear button behavior for student search
        const clearStudentSearchBtn = document.getElementById('clearStudentSearchBtn');
        if (clearStudentSearchBtn) {
            studentSearchInput.addEventListener('input', function(e) {
                clearStudentSearchBtn.style.display = e.target.value ? 'inline-block' : 'none';
            });
            clearStudentSearchBtn.addEventListener('click', function() {
                studentSearchInput.value = '';
                filterStudents('');
                clearStudentSearchBtn.style.display = 'none';
                studentSearchInput.focus();
            });
        }
    }
    
    // Refresh button listener
    const refreshOverviewBtn = document.getElementById('refreshOverviewBtn');
    if (refreshOverviewBtn) {
        refreshOverviewBtn.addEventListener('click', function() {
            refreshClassOverview();
        });
    }
    
    // Modal close button
    const closeModal = document.getElementById('closeModal');
    if (closeModal) {
        closeModal.addEventListener('click', function() {
            document.getElementById('attendanceModal').style.display = 'none';
        });
    }
    
    // Back buttons
    const backToOverview = document.getElementById('backToOverview');
    if (backToOverview) {
        backToOverview.addEventListener('click', function() {
            console.log('[FRONTEND LOG] Navigating back to overview - hiding detail views and refreshing overview');
            
            // Hide all detail views
            document.getElementById('classDetailView').style.display = 'none';
            document.getElementById('studentDetailView').style.display = 'none';
            
            // Show overview
            document.getElementById('classOverview').style.display = 'block';
            
            // Always refresh overview to ensure it shows latest data
            console.log('[FRONTEND LOG] Back to overview - refreshing class overview');
            refreshClassOverview().then(() => {
                console.log('[FRONTEND LOG] Overview refresh completed');
            }).catch(error => {
                console.error('[FRONTEND LOG] Error refreshing overview:', error);
            });
        });
    }
    
    const backToClassDetail = document.getElementById('backToClassDetail');
    if (backToClassDetail) {
        backToClassDetail.addEventListener('click', function() {
            // Hide student detail view first
            document.getElementById('studentDetailView').style.display = 'none';
            
            // Always refresh the class detail view to ensure latest data
            if (currentClassId) {
                console.log(`[FRONTEND LOG] Back to class detail - refreshing class ${currentClassId} (needs refresh: ${needsClassDetailRefresh})`);
                showClassDetail(currentClassId);
                // Reset the refresh flag
                needsClassDetailRefresh = false;
            } else {
                // Fallback - just show the view without refresh
                document.getElementById('classDetailView').style.display = 'block';
            }
        });
    }
    
    // Update attendance button
    const updateAttendanceBtn = document.getElementById('updateAttendance');
    if (updateAttendanceBtn) {
        updateAttendanceBtn.addEventListener('click', updateAttendance);
    }
}

// Debounce function to limit how often a function can be called
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Filter classes based on search input
function filterClasses(searchTerm) {
    if (!searchTerm) {
        renderClassTable(allClasses);
        return;
    }
    
    searchTerm = searchTerm.toLowerCase();
    const filteredClasses = allClasses.filter(classObj => {
        return (
            classObj.classCode.toLowerCase().includes(searchTerm) ||
            classObj.description.toLowerCase().includes(searchTerm) ||
            classObj.schedule.toLowerCase().includes(searchTerm)
        );
    });
    
    renderClassTable(filteredClasses, searchTerm);
}

// Filter students based on search input
function filterStudents(searchTerm) {
    if (!searchTerm) {
        renderStudentTable(allStudents);
        return;
    }
    
    searchTerm = searchTerm.toLowerCase();
    const filteredStudents = allStudents.filter(student => {
        return (
            student.id.toLowerCase().includes(searchTerm) ||
            student.name.toLowerCase().includes(searchTerm)
        );
    });
    
    renderStudentTable(filteredStudents, searchTerm);
}

// Highlight search terms in text
function highlightText(text, searchTerm) {
    if (!searchTerm) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// Load class overview data
function loadClassOverview() {
    console.log('Fetching class overview data...');
    
    // Add cache-busting headers
    const headers = new Headers();
    headers.append('Cache-Control', 'no-cache, no-store, must-revalidate');
    headers.append('Pragma', 'no-cache');
    headers.append('Expires', '0');
    
    // Send the client's current date (local) to the server to avoid timezone mismatches
    const dateStr = getLocalISODate();
    return fetch(`/instructors/api/class-attendance-overview?date=${dateStr}&_=${Date.now()}`, {
        method: 'GET',
        headers: headers,
        cache: 'no-store'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Response data from class overview API:', data);
            if (data.success) {
                allClasses = data.classes;
                renderClassTable(allClasses);
                updateCurrentDate(); // Update current date on initial load
            } else {
                console.error('Error loading class overview:', data.message);
                showFeedback('Error loading class overview: ' + (data.message || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            console.error('Error loading class overview:', error);
            showFeedback('Error loading class overview: ' + error.message, 'error');
        });
}

// Refresh class overview data
function refreshClassOverview() {
    console.log('Refreshing class overview data...');
    const refreshBtn = document.getElementById('refreshOverviewBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    }
    
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
    
    // Add cache-busting headers and timestamp
    const headers = new Headers();
    headers.append('Cache-Control', 'no-cache, no-store, must-revalidate');
    headers.append('Pragma', 'no-cache');
    headers.append('Expires', '0');
    
    // Include the client's current date (local) when refreshing overview
    const dateStr = getLocalISODate();
    return fetch(`/instructors/api/class-attendance-overview?date=${dateStr}&_=${Date.now()}&refresh=1`, {
        method: 'GET',
        headers: headers,
        cache: 'no-store'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Refreshed data from class overview API:', data);
            if (data.success) {
                allClasses = data.classes;
                renderClassTable(allClasses);
                updateCurrentDate(); // Update current date on refresh
                console.log('Successfully refreshed class overview with latest attendance data');
            } else {
                console.error('Error refreshing class overview:', data.message);
                showFeedback('Error refreshing class overview: ' + (data.message || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            console.error('Error refreshing class overview:', error);
            showFeedback('Error refreshing class overview: ' + error.message, 'error');
        })
        .finally(() => {
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
            }
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        });
}

// Render class table with optional search term highlighting
function renderClassTable(classes, searchTerm = '') {
    const tbody = document.getElementById('class-overview-tbody');
    if (!tbody) return;
    
    if (classes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No classes found</td></tr>';
        return;
    }
    
    tbody.innerHTML = classes.map(classObj => {
        console.log('Rendering class row for:', classObj);
        const sessionMeta = buildSessionMetaHTML(classObj, { variant: 'compact' }) || '';
        return `
        <tr>
            <td>${highlightText(classObj.classCode, searchTerm)}</td>
            <td>${highlightText(classObj.description, searchTerm)}</td>
            <td>${classObj.term || 'N/A'}</td>
            <td>${classObj.enrolledCount}</td>
            <td>
                <div>${highlightText(classObj.schedule || 'N/A', searchTerm)}</div>
                ${sessionMeta}
            </td>
            <td>
                <button class="btn btn-primary" onclick="showClassDetail(${classObj.id})">
                    View Details
                </button>
            </td>
        </tr>
    `;
    }).join('');

    // Log the updated counter value for verification
    const firstPresentCounter = tbody.querySelector('.attendance-counter.present span:last-child');
    if (firstPresentCounter) {
        console.log('Rendered Present Counter for first class:', firstPresentCounter.textContent);
    }
}

// Render student table with optional search term highlighting
function renderStudentTable(students, searchTerm = '') {
    const tbody = document.getElementById('class-detail-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = ''; // Clear existing rows
    
    if (students.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No students found</td></tr>';
        return;
    }
    
    students.forEach(student => {
        console.log('Rendering student row for:', student.id, 'Status:', student.status);
        // Get status badge class based on attendance status
        const statusClass = student.status ? `badge-${student.status.toLowerCase()}` : 'badge-absent';
        const statusText = student.status || 'Absent';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${highlightText(student.id, searchTerm)}</td>
            <td>${highlightText(student.name, searchTerm)}</td>
            <td>${student.yearLevel}</td>
            <td>
                <span class="badge-status ${statusClass}">
                    ${statusText}
                </span>
            </td>
            <td>
                <button class="btn btn-primary view-details-btn" data-student-id="${student.id}" data-student-name="${student.name}" data-class-id="${student.classId}" data-class-name="${student.className}">
                    View Details
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    // Add event listeners to view details buttons
    tbody.querySelectorAll('.view-details-btn').forEach(button => {
        button.addEventListener('click', function() {
            const studentId = this.dataset.studentId;
            const studentName = this.dataset.studentName;
            const classId = parseInt(this.dataset.classId); // Ensure classId is a number
            const className = this.dataset.className;
            showStudentDetail(studentId, studentName, classId, className);
        });
    });
}

// Show class details
async function showClassDetail(classId) {
    console.log(`[FRONTEND LOG] showClassDetail called for class ID: ${classId}`);
    try {
        currentClassId = classId;
        
        // Show loading indicator
        const loadingIndicator = document.getElementById('classDetailLoading');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
        }
        
        // Show class detail view immediately but with loading state
        document.getElementById('classOverview').style.display = 'none';
        document.getElementById('classDetailView').style.display = 'block';
        
        // Update class title and current date first
        const classObj = allClasses.find(c => c.id === classId);
        if (classObj) {
            document.getElementById('classDetailTitle').textContent = `Class: ${classObj.description}`;
            document.getElementById('classDetailCode').textContent = `Class Code: ${classObj.classCode}`;
            updateClassSessionInfo(classObj);
        }
        
        // Update current date display
        const currentDateElement = document.getElementById('currentDateValue');
        if (currentDateElement) {
            const today = new Date();
            const formattedDate = today.toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            currentDateElement.textContent = formattedDate;
        }
        
        // Get today's date in YYYY-MM-DD format (local)
        const today = new Date();
        const dateStr = getLocalISODate(today);
        
        console.log(`[FRONTEND LOG] Fetching fresh class students data for class ID: ${classId} on date: ${dateStr}`);
        // Fetch class students with attendance for today (fresh data)
        const response = await fetch(`/instructors/api/class-students/${classId}?date=${dateStr}&_=${Date.now()}`);
        if (!response.ok) {
            throw new Error('Failed to load class students');
        }
        
        const data = await response.json();
        console.log('[FRONTEND LOG] Response data from /instructors/api/class-students:', data);
        
        if (data.students) {
            allStudents = data.students;
            console.log(`[FRONTEND LOG] Received ${allStudents.length} students for class detail.`);
            
            // Update counters using the counts from the response
            const presentCount = data.counts.present;
            const absentCount = data.counts.absent;
            const lateCount = data.counts.late;
            
            console.log(`[FRONTEND LOG] Using counts from response - Present: ${presentCount}, Absent: ${absentCount}, Late: ${lateCount}`);
            
            const presentCounterElement = document.getElementById('presentCounter');
            const absentCounterElement = document.getElementById('absentCounter');
            const lateCounterElement = document.getElementById('lateCounter');

            if(presentCounterElement) {
                console.log(`[FRONTEND LOG] Updating #presentCounter from ${presentCounterElement.textContent} to ${presentCount}`);
                presentCounterElement.textContent = presentCount;
                console.log(`[FRONTEND LOG] #presentCounter updated to: ${presentCounterElement.textContent}`);
            }
            if(absentCounterElement) {
                console.log(`[FRONTEND LOG] Updating #absentCounter from ${absentCounterElement.textContent} to ${absentCount}`);
                absentCounterElement.textContent = absentCount;
                console.log(`[FRONTEND LOG] #absentCounter updated to: ${absentCounterElement.textContent}`);
            }
            if(lateCounterElement) {
                console.log(`[FRONTEND LOG] Updating #lateCounter from ${lateCounterElement.textContent} to ${lateCount}`);
                lateCounterElement.textContent = lateCount;
                console.log(`[FRONTEND LOG] #lateCounter updated to: ${lateCounterElement.textContent}`);
            }
            
            // Render student table with attendance data
            renderStudentTable(data.students);

            // Hide loading indicator
            const loadingIndicator = document.getElementById('classDetailLoading');
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            // Refresh the class overview in the background to keep it in sync
            console.log(`[FRONTEND LOG] Refreshing class overview in background after showing details`);
            refreshClassOverview();

            // --- Workaround to potentially force re-render ---
            // This might help in cases where the browser doesn't visually update
            // the table immediately after innerHTML replacement.
            const tbody = document.getElementById('class-detail-tbody');
            if (tbody) {
                // Temporarily add and remove a class or style
                tbody.style.display = 'none';
                // Use a small timeout to ensure the browser registers the style change
                setTimeout(() => {
                    tbody.style.display = '';
                }, 0);
            }
            // --- End workaround ---
        }
    } catch (error) {
        console.error('[FRONTEND LOG] Error loading class students:', error);
        const loadingIndicator = document.getElementById('classDetailLoading');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
        showFeedback('Error loading class students', 'error');
    }
}

// Function to refresh the student list in the class detail view
async function refreshClassStudentsList(classId) {
    console.log(`[FRONTEND LOG] refreshClassStudentsList called for class ID: ${classId}`);
    try {
        // Get today's date in YYYY-MM-DD format (local)
        const today = new Date();
        const dateStr = getLocalISODate(today);
        
        console.log(`[FRONTEND LOG] Fetching class students for class ID: ${classId} on date: ${dateStr} for refresh.`);
        // Fetch class students with attendance for today
        const response = await fetch(`/instructors/api/class-students/${classId}?date=${dateStr}`);
        if (!response.ok) {
            throw new Error('Failed to load class students for refresh');
        }
        
        const data = await response.json();
        console.log('[FRONTEND LOG] Response data from /instructors/api/class-students for refresh:', data);
        
        if (Array.isArray(data)) {
            // Update the allStudents global variable
            allStudents = data;
            console.log(`[FRONTEND LOG] Received ${allStudents.length} students for refresh.`);
            
            // Update current date when refreshing
            updateCurrentDate();
            
            // Render student table with attendance data
            renderStudentTable(data);
            console.log('[FRONTEND LOG] renderStudentTable called from refreshClassStudentsList.');
        }
    } catch (error) {
        console.error('[FRONTEND LOG] Error refreshing class students list:', error);
        showFeedback('Error refreshing class students list.', 'error');
    }
}

// Show student details
async function showStudentDetail(studentId, studentName, classId, className) {
    // Hide class overview and detail views
    document.getElementById('classOverview').style.display = 'none';
    document.getElementById('classDetailView').style.display = 'none';
    
    // Show student detail view
    const studentDetailView = document.getElementById('studentDetailView');
    studentDetailView.style.display = 'block';
    
    // Set student details
    const studentDetailTitle = document.getElementById('studentDetailTitle');
    studentDetailTitle.textContent = studentName;
    studentDetailTitle.dataset.studentId = studentId;
    
    // Set class details
    const studentDetailClass = document.getElementById('studentDetailClass');
    studentDetailClass.textContent = className;
    studentDetailClass.dataset.classId = classId;
    
    // Load student attendance
    await loadStudentAttendance(studentId, classId);
}

// Open update modal
function openUpdateModal(studentId, currentStatus, date = null) {
    currentStudentId = studentId;
    currentStatus = currentStatus;
    
    // Format the date properly
    if (date) {
        // If date is provided, parse it from the displayed format (e.g., "May 25 2025")
        const dateParts = date.split(' ');
        const month = new Date(Date.parse(dateParts[0] + " 1, 2000")).getMonth();
        const day = parseInt(dateParts[1]);
        const year = parseInt(dateParts[2]);
        
        // Create date string in YYYY-MM-DD format directly
        currentDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        
        console.log('Parsed date:', {
            original: date,
            parts: dateParts,
            month: month,
            day: day,
            year: year,
            final: currentDate
        });
    } else {
        // If no date provided, use today's date in YYYY-MM-DD format
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        currentDate = `${year}-${month}-${day}`;
        console.log('Using today\'s date:', currentDate);
    }
    
    const modal = document.getElementById('attendanceModal');
    const statusSelect = document.getElementById('attendanceStatus');
    
    statusSelect.value = currentStatus;
    modal.style.display = 'block';
}

// Update attendance
async function updateAttendance() {
    const status = document.getElementById('attendanceStatus').value;
    
    const data = {
        student_id: currentStudentId,
        class_id: currentClassId,
        date: currentDate,
        status: status
    };
    
    console.log('Sending attendance update data from modal:', data);
    
    try {
        const response = await fetch('/instructors/api/update-attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('Attendance update successful from modal. Refreshing UI...');
            document.getElementById('attendanceModal').style.display = 'none';
            
            // Format the display date
            const dateParts = currentDate.split('-');
            const displayDate = new Date(dateParts[0], dateParts[1] - 1, dateParts[2])
                .toLocaleDateString('en-US', {
                    month: 'long',
                    day: 'numeric',
                    year: 'numeric'
                }).replace(',', '');
            
            // Update local records
            if (!allAttendanceRecords) {
                allAttendanceRecords = {};
            }
            
            // Add or update the record in local data
            allAttendanceRecords[displayDate] = {
                status: status,
                attendance_id: result.attendance_id || null
            };
            
            console.log('Updated local records after modal update:', allAttendanceRecords);
            
            // Refresh the appropriate view
            if (document.getElementById('studentDetailView').style.display === 'block') {
                console.log('Refreshing Student Detail View after modal update...');
                // Set flag that class detail needs refresh when user goes back
                needsClassDetailRefresh = true;
                
                // Retrieve required parameters from the DOM before calling showStudentDetail
                const studentDetailTitle = document.getElementById('studentDetailTitle');
                const studentDetailClass = document.getElementById('studentDetailClass');
                const studentId = studentDetailTitle.dataset.studentId;
                const studentName = studentDetailTitle.textContent;
                const classId = parseInt(studentDetailClass.dataset.classId);
                const className = studentDetailClass.textContent;

                // Check if required data is available
                if (studentId && studentName && !isNaN(classId) && className) {
                    // Update the attendance counters immediately
                    const studentPresentCounterElement = document.getElementById('studentPresentCounter');
                    const studentAbsentCounterElement = document.getElementById('studentAbsentCounter');
                    const studentLateCounterElement = document.getElementById('studentLateCounter');

                    // Get current counts
                    let presentCount = parseInt(studentPresentCounterElement.textContent) || 0;
                    let absentCount = parseInt(studentAbsentCounterElement.textContent) || 0;
                    let lateCount = parseInt(studentLateCounterElement.textContent) || 0;

                    // Update counts based on the new status
                    const oldStatus = allAttendanceRecords[displayDate]?.status;
                    if (oldStatus) {
                        if (oldStatus === 'Present') presentCount--;
                        else if (oldStatus === 'Absent') absentCount--;
                        else if (oldStatus === 'Late') lateCount--;
                    }

                    if (status === 'Present') presentCount++;
                    else if (status === 'Absent') absentCount++;
                    else if (status === 'Late') lateCount++;

                    // Update the UI
                    studentPresentCounterElement.textContent = presentCount;
                    studentAbsentCounterElement.textContent = absentCount;
                    studentLateCounterElement.textContent = lateCount;

                    // Refresh the student detail view
                    showStudentDetail(studentId, studentName, classId, className);
                } else {
                    console.error('Error refreshing student detail view: Missing student or class data in DOM.', {
                        studentId, studentName, classId, className
                    });
                    showFeedback('Error refreshing student view after update.', 'error');
                }
            } else {
                console.log('Refreshing Class Detail View after modal update...');
                // Show loading while refreshing
                const loadingIndicator = document.getElementById('classDetailLoading');
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'block';
                }
                showClassDetail(currentClassId);
            }
            
            // Always refresh class overview with a small delay to ensure DB is updated
            console.log('Refreshing Class Overview after modal update...');
            setTimeout(async () => {
                try {
                    await refreshClassOverview();
                    console.log('Class overview refreshed successfully after attendance update');
                } catch (error) {
                    console.error('Error refreshing class overview after attendance update:', error);
                }
            }, 500); // 500ms delay to ensure database update is complete
             
            showFeedback('Attendance record updated successfully', 'success');
        } else {
            console.error('Error updating attendance from modal:', result.message);
            showFeedback('Error updating attendance: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('Error updating attendance from modal:', error);
        showFeedback('Error updating attendance. Please try again.', 'error');
    }
}

// Confirmation modal functions
function showConfirmation(title, message, callback) {
    const modal = document.getElementById('confirmationModal');

    if (!modal) {
        console.error('Confirmation modal not found');
        return;
    }

    const titleElement = modal.querySelector('.modal-title');
    const bodyElement = modal.querySelector('.modal-body p');

    if (titleElement) titleElement.textContent = title;
    if (bodyElement) bodyElement.textContent = message;

    confirmationCallback = callback;

    // Use Bootstrap modal
    const bsModal = new bootstrap.Modal(modal);

    // Attach event listener to confirm button when modal is shown
    modal.addEventListener('shown.bs.modal', function() {
        const confirmButton = document.getElementById('confirmAction');
        if (confirmButton) {
            confirmButton.onclick = function() {
                handleConfirmation(true);
            };
        }
    }, { once: true }); // Prevent multiple listeners

    bsModal.show();
}

function handleConfirmation(confirmed) {
    // Hide Bootstrap modal
    const modalElem = document.getElementById('confirmationModal');
    if (modalElem) {
        const modalInstance = bootstrap.Modal.getInstance(modalElem);
        if (modalInstance) {
            modalInstance.hide();
        }
    }

    if (confirmed && typeof confirmationCallback === 'function') {
        confirmationCallback();
    }

    confirmationCallback = null;
}

// Delete attendance
async function deleteAttendance(studentId, classId, date) {
    // Use custom confirmation modal instead of native confirm
    showConfirmation(
        'Delete Attendance',
        'Are you sure you want to delete this attendance record?',
        () => performDeleteAttendance(studentId, classId, date)
    );
}

// Perform the actual delete operation
async function performDeleteAttendance(studentId, classId, date) {
    console.log(`Attempting to delete attendance for student ${studentId} in class ${classId} on ${date}`);

    // Convert the display date format (e.g., "May 26 2025") to YYYY-MM-DD format
    let formattedDate;
    try {
        const dateParts = date.split(' ');
        const monthNames = ["January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November", "December"];
        const monthIndex = monthNames.indexOf(dateParts[0]);
        const day = dateParts[1];
        const year = dateParts[2];
        
        if (monthIndex === -1) {
            throw new Error('Invalid month name');
        }
        
        formattedDate = `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    } catch (error) {
        console.error('Error formatting date:', error);
        showFeedback('Error: Invalid date format', 'error');
        return;
    }

    try {
        const response = await fetch('/instructors/api/delete-attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                date: formattedDate
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to delete attendance record');
        }
        
        console.log('Attendance deleted successfully:', data);
        
        // Refresh attendance records
        await loadStudentAttendance(studentId, classId);
        
        showFeedback('Attendance record deleted successfully', 'success');
    } catch (error) {
        console.error('Error deleting attendance:', error);
        showFeedback(error.message || 'Error deleting attendance. Please try again.', 'error');
    }
}

// Load student attendance records
async function loadStudentAttendance(studentId, classId) {
    console.log('Attempting to load attendance for student', studentId, 'in class', classId);
    
    try {
        const currentDate = new Date();
        const month = currentDate.toLocaleString('default', { month: 'long' });
        const year = currentDate.getFullYear();
        
        console.log('Fetching attendance data from /instructors/api/student-attendance/' + studentId + '/' + classId + '?month=' + year + '-' + (currentDate.getMonth() + 1).toString().padStart(2, '0'));
        
        const response = await fetch(`/instructors/api/student-attendance/${studentId}/${classId}?month=${year}-${(currentDate.getMonth() + 1).toString().padStart(2, '0')}`);
        const data = await response.json();
        
        console.log('Response data from student attendance API:', data);
        
        if (data.success) {
            // Update attendance counters
            // Access counts from the nested attendance object
            const presentCount = data.attendance.presentCount || 0;
            const absentCount = data.attendance.absentCount || 0;
            const lateCount = data.attendance.lateCount || 0;
            
            console.log('Updating #studentPresentCounter from', document.getElementById('studentPresentCounter').textContent, 'to', presentCount);
            document.getElementById('studentPresentCounter').textContent = presentCount;
            console.log('#studentPresentCounter updated to:', document.getElementById('studentPresentCounter').textContent);
            
            console.log('Updating #studentAbsentCounter from', document.getElementById('studentAbsentCounter').textContent, 'to', absentCount);
            document.getElementById('studentAbsentCounter').textContent = absentCount;
            console.log('#studentAbsentCounter updated to:', document.getElementById('studentAbsentCounter').textContent);
            
            console.log('Updating #studentLateCounter from', document.getElementById('studentLateCounter').textContent, 'to', lateCount);
            document.getElementById('studentLateCounter').textContent = lateCount;
            console.log('#studentLateCounter updated to:', document.getElementById('studentLateCounter').textContent);
            
            // Process attendance records
            // Access records object from the nested attendance object
            const attendanceRecordsObject = data.attendance.records || {}; // Expect an object
            console.log('Raw attendance records object:', attendanceRecordsObject);
            
            // Convert records object to an array for easier processing and sorting
            const attendanceRecordsArray = Object.entries(attendanceRecordsObject).map(([date, record]) => ({
                date: date, // Keep the date string as is
                status: record.status,
                attendance_id: record.attendance_id // Include attendance_id if available
            }));
            
            // Sort records by date in chronological order (oldest first)
            attendanceRecordsArray.sort((a, b) => new Date(a.date) - new Date(b.date));
            
            console.log('Processed attendance records array:', attendanceRecordsArray);
            
            const processedData = {
                presentCount,
                absentCount,
                lateCount,
                month: data.attendance.month || month,
                year: data.attendance.year || year,
                records: attendanceRecordsArray // Use the array here
            };
            
            console.log('Attendance records processed for rendering:', processedData);
            
            // Render attendance records
            const tbody = document.getElementById('student-detail-tbody');
            tbody.innerHTML = '';
            
            if (Array.isArray(processedData.records) && processedData.records.length > 0) {
                console.log('Rendering attendance records:', processedData.records);
                processedData.records.forEach(record => {
                    console.log('Processing record:', record);
                    const row = document.createElement('tr');
                    
                    row.innerHTML = `
                        <td>${record.date}</td>
                        <td><span class="badge-status badge-${record.status.toLowerCase()}">${record.status}</span></td>
                        <td>
                            <button class="btn btn-sm btn-primary update-btn" data-date="${record.date}">
                                <i class="fas fa-edit"></i> Update
                            </button>
                            <button class="btn btn-sm btn-danger delete-btn" data-date="${record.date}">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </td>
                    `;
                    
                    tbody.appendChild(row);
                });
                
                // Add event listeners for update and delete buttons
                document.querySelectorAll('.update-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const date = btn.dataset.date;
                        // Find the record in the processed array
                        const record = processedData.records.find(r => r.date === date);
                        if (record) {
                            openUpdateModal(studentId, record.status, date);
                        }
                    });
                });
                
                document.querySelectorAll('.delete-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const date = btn.dataset.date;
                        deleteAttendance(studentId, classId, date);
                    });
                });
            } else {
                console.log('No attendance records found for this month.', processedData);
                tbody.innerHTML = '<tr><td colspan="3" class="text-center">No attendance records found for this month.</td></tr>';
            }
        } else {
            console.error('Error loading attendance:', data.message);
            showFeedback('Error loading attendance: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error loading attendance:', error);
        showFeedback('Error loading attendance. Please try again.', 'error');
    }
}

// Add manual attendance
async function addManualAttendance(event) {
    event.preventDefault();
    
    const studentId = document.getElementById('studentDetailTitle').dataset.studentId;
    const classId = document.getElementById('studentDetailClass').dataset.classId;
    const date = document.getElementById('attendanceDate').value;
    const status = document.getElementById('manualAttendanceStatus').value;
    
    if (!studentId || !classId || !date || !status) {
        showFeedback('Please fill in all fields', 'error');
        return;
    }
    
    try {
        const response = await fetch('/attendance/manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                date: date,
                status: status
            })
        });
        
        const data = await response.json();
        
        if (response.status === 409) {
            // Handle duplicate record
            showConfirmation(
                'Duplicate Record',
                'An attendance record already exists for this date. Would you like to update it?',
                () => updateManualAttendance(studentId, classId, date, status)
            );
            return;
        }
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to add attendance record');
        }
        
        // Clear form
        document.getElementById('attendanceDate').value = '';
        document.getElementById('manualAttendanceStatus').value = 'Present';
        
        // Refresh attendance records
        await loadStudentAttendance(studentId, classId);
        
        showFeedback('Attendance record added successfully');
    } catch (error) {
        console.error('Error adding attendance:', error);
        showFeedback(error.message, 'error');
    }
}

// Update manual attendance
async function updateManualAttendance(studentId, classId, date, status) {
    try {
        const response = await fetch('/attendance/update', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                date: date,
                status: status
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to update attendance record');
        }
        
        // Refresh attendance records
        await loadStudentAttendance(studentId, classId);
        
        showFeedback('Attendance record updated successfully');
    } catch (error) {
        console.error('Error updating attendance:', error);
        showFeedback(error.message, 'error');
    }
}

// Utility: Convert array of objects to CSV string
function arrayToCSV(data, columns) {
    // Quote header columns as well to handle spaces or special characters
    const header = columns.map(h => '"' + String(h).replace(/"/g, '""') + '"').join(',');
    const rows = data.map(row => columns.map(col => '"' + (row[col] !== undefined ? String(row[col]).replace(/"/g, '""') : '') + '"').join(','));
    return [header, ...rows].join('\r\n');
}

// Export current class attendance as CSV
function exportCurrentClassAttendance() {
    if (!allStudents || allStudents.length === 0) {
        showFeedback('No student data to export.', 'error');
        return;
    }
    // Define columns to export: Month, Day, ID, Name, Year Level, Status
    const columns = ['Month', 'Day', 'ID', 'Name', 'Year Level', 'Status'];
    // Prepare data (status fallback). Use today's month name and day number.
    const now = new Date();
    const monthName = now.toLocaleString('en-US', { month: 'long' });
    const dayNum = now.getDate();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const data = allStudents.map(s => ({
        'Month': monthName,
        'Day': dayNum,
        'ID': s.id,
        'Name': s.name,
        'Year Level': s.yearLevel || '',
        'Status': s.status || 'Absent'
    }));
    const csv = arrayToCSV(data, columns);
    const classObj = allClasses.find(c => c.id === currentClassId);
    const filename = classObj ? `attendance_${classObj.classCode || 'class'}_${mm}-${dd}.csv` : `attendance_current_class_${mm}-${dd}.csv`;
    downloadCSV(csv, filename);
}

// Export all classes attendance as CSV
function exportAllClassesAttendance() {
    if (!allClasses || allClasses.length === 0) {
        showFeedback('No class data to export.', 'error');
        return;
    }
    // Define columns to export
    const columns = ['classCode', 'description', 'term', 'date', 'enrolledCount', 'presentCount', 'absentCount', 'lateCount'];
    const data = allClasses.map(c => ({
        classCode: c.classCode,
        description: c.description,
        term: c.term || 'N/A',
        date: c.date,
        enrolledCount: c.enrolledCount,
        presentCount: c.presentCount,
        absentCount: c.absentCount,
        lateCount: c.lateCount
    }));
    const csv = arrayToCSV(data, columns);
    const filename = `attendance_all_classes_${getLocalISODate()}.csv`;
    downloadCSV(csv, filename);
}

// Utility: Download CSV file
function downloadCSV(csv, filename) {
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Add export button event listeners after DOMContentLoaded
function setupExportButtons() {
    const exportCurrentBtn = document.getElementById('exportCurrentClassBtn');
    if (exportCurrentBtn) {
        exportCurrentBtn.addEventListener('click', exportCurrentClassAttendance);
    }
    const exportAllBtn = document.getElementById('exportAllClassesBtn');
    if (exportAllBtn) {
        exportAllBtn.addEventListener('click', exportAllClassesAttendance);
    }
}

// Show feedback message
function showFeedback(message, type = 'success') {
    // Use the floating notification system
    if (window.showFloatingNotification) {
        const duration = type === 'error' || type === 'danger' ? 6000 : 4000;
        window.showFloatingNotification(message, type, duration, true);
    } else {
        // Fallback to the old system if floating notifications aren't available
        const feedback = document.getElementById('attendanceFeedback');
        if (!feedback) return;
        
        feedback.textContent = message;
        feedback.className = `alert alert-${type}`;
        feedback.style.display = 'block';
        
        // Hide feedback after 3 seconds
        setTimeout(() => {
            feedback.style.display = 'none';
        }, 3000);
    }
}