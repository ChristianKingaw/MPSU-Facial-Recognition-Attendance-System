/**
 * Classes Management JavaScript
 * Handles the UI interactions for managing classes
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Classes page initialized');
    
    // Fetch initial data
    fetchClasses();
    
    // Populate courses dropdown
    populateCourseDropdown();
    
    // Populate instructors dropdown
    populateInstructorDropdown();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up course change handler
    setupCourseChangeHandler();

    // Enhanced search functionality
    const searchInput = document.getElementById('searchInput');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const searchLoading = document.querySelector('.search-loading');
    const resultsCount = document.getElementById('resultsCount');
    let currentFilter = 'all';
    let searchTimeout;

    // Debounce function
    function debounce(func, wait) {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(searchTimeout);
                func(...args);
            };
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(later, wait);
        };
    }

    // Update active filter button
    function updateActiveFilter(filter) {
        filterButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });
        currentFilter = filter;
    }

    // Handle filter button clicks
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            updateActiveFilter(btn.dataset.filter);
            if (searchInput.value) {
                searchClasses(searchInput.value);
            }
        });
    });

    // Enhanced search function
    const searchClasses = debounce(function(query) {
        if (searchLoading) searchLoading.classList.add('active');
        
        query = query.toLowerCase().trim();
        
        if (query === '') {
            renderClassesTable();
            if (searchLoading) searchLoading.classList.remove('active');
            if (resultsCount) resultsCount.textContent = '0';
            return;
        }
        
        const filteredClasses = classes.filter(cls => {
            const instructorText = `${cls.instructorName || ''} ${cls.substituteInstructorName || ''}`.toLowerCase();
            if (currentFilter === 'all') {
                return (
                    (cls.classCode || '').toLowerCase().includes(query) ||
                    (cls.description || '').toLowerCase().includes(query) ||
                    (cls.schedule || '').toLowerCase().includes(query) ||
                    instructorText.includes(query)
                );
            } else if (currentFilter === 'instructorName') {
                return instructorText.includes(query);
            } else {
                const field = currentFilter === 'classCode' ? 'classCode' :
                            currentFilter === 'description' ? 'description' :
                            currentFilter === 'schedule' ? 'schedule' :
                            'instructorName';
                const value = (cls[field] || '').toLowerCase();
                return value.includes(query);
            }
        });
        
        if (resultsCount) resultsCount.textContent = filteredClasses.length;
        
        if (filteredClasses.length === 0) {
            const colspan = isInstructorPage ? 5 : 6;
            document.getElementById('classes-table-body').innerHTML = `
                <tr>
                    <td colspan="${colspan}" class="text-center">
                        No classes found matching "${query}" in ${currentFilter === 'all' ? 'any field' : currentFilter}
                    </td>
                </tr>
            `;
            updateClassCount(0);
        } else {
            renderClassesTable(filteredClasses, query);
        }
        
        if (searchLoading) searchLoading.classList.remove('active');
    }, 300);

    // Add input event listener
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchClasses(e.target.value);
        });
    }
});

// Global variables to track state
let classes = [];
let selectedClassId = null;
let currentView = 'classes'; // 'classes', 'class-detail', 'student-selection'
let courses = [];
let instructors = []; // Add a global variable for instructors
const isInstructorPage = !document.getElementById('btnAddClass');

/**
 * Set up all event listeners for interactive elements
 */
function setupEventListeners() {
    console.log('Setting up event listeners...');
    
    // Add Class button
    const addClassBtn = document.getElementById('btnAddClass');
    const deleteAllBtn = document.getElementById('btnDeleteAllClasses');
    if (addClassBtn) {
        console.log('btnAddClass element found.');
        // Check user role to determine if button should be shown
        fetch('/auth/check-auth')
            .then(response => {
                if (!response.ok) {
                    console.error('Error checking user role: HTTP status', response.status);
                    return response.text().then(text => { throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`); });
                }
                return response.json();
            })
            .then(data => {
                console.log('User role check response data:', data);
                const isAdmin = data.user && data.user.role === 'admin';
                if (isAdmin) {
                    console.log('User is admin. Setting addClassBtn display to block.');
                    addClassBtn.style.display = 'block';
                    // Add click event listener to show the modal
                    addClassBtn.addEventListener('click', showAddClassModal);
                    if (deleteAllBtn) {
                        deleteAllBtn.style.display = 'inline-flex';
                        deleteAllBtn.addEventListener('click', onDeleteAllClick);
                    }
                } else {
                    console.log('User is not admin (role:', data.user ? data.user.role : undefined, '). Setting addClassBtn display to none.');
                    addClassBtn.style.display = 'none';
                    if (deleteAllBtn) deleteAllBtn.style.display = 'none';
                }
                 console.log('Final addClassBtn display after role check:', addClassBtn.style.display);
            })
            .catch(error => {
                console.error('Fetch error checking user role:', error);
                console.log('Setting addClassBtn display to none on fetch error.');
                // Ensure button is hidden on fetch errors
                addClassBtn.style.display = 'none';
                if (deleteAllBtn) deleteAllBtn.style.display = 'none';
                 console.log('Final addClassBtn display after fetch error:', addClassBtn.style.display);
            });
    } else {
        console.warn('btnAddClass element not found.');
    }
    
    // Search class input
    const searchClassInput = document.getElementById('searchClassInput');
    const searchClassBtn = document.getElementById('searchClassBtn');
    
    if (searchClassInput && searchClassBtn) {
        searchClassBtn.addEventListener('click', function() {
            searchClasses(searchClassInput.value);
        });
        
        searchClassInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                searchClasses(searchClassInput.value);
            }
        });
    }
    
    // Close class modal - handle custom close button if it exists
    const closeClassModalBtn = document.getElementById('close-class-modal');
    if (closeClassModalBtn) {
        closeClassModalBtn.addEventListener('click', closeClassModal);
    }
    
    // Let Bootstrap handle the standard close button naturally via data-bs-dismiss
    // Listen to Bootstrap's modal events for any cleanup if needed
    const addClassModal = document.getElementById('addClassModal');
    if (addClassModal) {
        addClassModal.addEventListener('hidden.bs.modal', function () {
            // Clean up form when modal is closed
            const form = document.getElementById('class-form');
            if (form) {
                form.reset();
            }
            // Clear any validation messages or errors
            const errorElements = form?.querySelectorAll('.is-invalid');
            errorElements?.forEach(el => el.classList.remove('is-invalid'));
            // Ensure interactive fields are returned to default (editable) state
            const courseSelect = document.getElementById('course');
            const descriptionInput = document.getElementById('description');
            const visibleDescriptionInput = document.getElementById('visibleDescription');
            if (courseSelect) courseSelect.disabled = false;
            if (descriptionInput) descriptionInput.readOnly = false;
            if (visibleDescriptionInput) visibleDescriptionInput.readOnly = false;
        });
    }
    
    // Class form submission
    const classForm = document.getElementById('class-form');
    console.log('Class form element:', classForm);
    if (classForm) {
        classForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveClass();
        });
    }
    
    // Confirmation modal buttons
    const confirmYesBtn = document.getElementById('confirm-yes');
    const confirmNoBtn = document.getElementById('confirm-no');
    const closeConfirmationModalBtn = document.getElementById('confirmation-modal').querySelector('.btn-close');
    
    if (confirmYesBtn) {
        confirmYesBtn.addEventListener('click', function() {
            const actionType = document.getElementById('confirmActionType');
            if (actionType && actionType.value === 'delete-all-classes') {
                fetch('/classes/api/delete-all', { method: 'DELETE' })
                    .then(response => response.json().then(data => ({ ok: response.ok, data })))
                    .then(({ ok, data }) => {
                        if (!ok) throw new Error(data.message || 'Failed to delete all classes');
                        closeConfirmationModal();
                        window.showSuccessNotification('All classes deleted successfully!');
                        fetchClasses();
                    })
                    .catch(err => {
                        console.error('Error deleting all classes:', err);
                        window.showErrorNotification(`Error deleting all classes: ${err.message}`);
                        closeConfirmationModal();
                    })
                    .finally(() => {
                        if (actionType) actionType.value = '';
                    });
            } else {
                confirmDeleteClass();
            }
        });
    }
    
    if (confirmNoBtn) {
        confirmNoBtn.addEventListener('click', closeConfirmationModal);
    }
    
    if (closeConfirmationModalBtn) {
        closeConfirmationModalBtn.addEventListener('click', closeConfirmationModal);
    }
    
    // Back to classes button
    const backToClassesBtn = document.getElementById('back-to-classes');
    if (backToClassesBtn) {
        backToClassesBtn.addEventListener('click', function() {
            showView('classes');
        });
    }
    
    // Enroll student button
    const enrollStudentBtn = document.getElementById('enroll-student-btn');
    if (enrollStudentBtn) {
        enrollStudentBtn.addEventListener('click', function() {
            showView('student-selection');
            getAllStudents();
        });
    }
    
    // Back to class detail button
    const backToClassDetailBtn = document.getElementById('back-to-class-detail');
    if (backToClassDetailBtn) {
        backToClassDetailBtn.addEventListener('click', function() {
            showView('class-detail');
        });
    }
    
    // Search student input
    const searchStudentInput = document.getElementById('searchStudentInput');
    const searchStudentBtn = document.getElementById('searchStudentBtn');
    
    if (searchStudentInput && searchStudentBtn) {
        searchStudentBtn.addEventListener('click', function() {
            searchStudents(searchStudentInput.value);
        });
        
        searchStudentInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                searchStudents(searchStudentInput.value);
            }
        });
    }
    
    // Add event listener for Reset Days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (typeof resetSelectedDays === 'function') {
                resetSelectedDays(); // Call the function from schedule-builder.js
            }
        });
    }

    // Export Classes
    const btnExportClasses = document.getElementById('btnExportClasses');
    if (btnExportClasses) {
        btnExportClasses.addEventListener('click', handleExportClasses);
    }

    // Import Classes
    const btnImportClasses = document.getElementById('btnImportClasses');
    if (btnImportClasses) {
        btnImportClasses.addEventListener('click', () => {
            document.getElementById('importClassFileInput').click();
        });
    }

    // File input change handler for import
    const importClassFileInput = document.getElementById('importClassFileInput');
    if (importClassFileInput) {
        importClassFileInput.addEventListener('change', handleImportClasses);
    }
}

/**
 * Set up the course change handler
 */
function setupCourseChangeHandler() {
    const courseSelect = document.getElementById('course');
    const classCodeInput = document.getElementById('classCode');
    const descriptionInput = document.getElementById('description'); // Get the hidden description input

    if (courseSelect && classCodeInput && descriptionInput) {
        courseSelect.addEventListener('change', function() {
            const selectedCourse = courseSelect.value;
            if (selectedCourse) {
                // Find the course details
                const course = courses.find(c => c.code === selectedCourse);
                if (course) {
                    // Auto-fill the class code (only if adding a new class)
                    // We will rely on the server to generate the section letter on save
                    if (!selectedClassId) {
                        // Clear the class code input initially, server will generate on save
                        classCodeInput.value = ''; // Clear for new class, server generates section
                    }

                    // Set the description for both the visible display (if any) and the hidden input
                    descriptionInput.value = course.description; // Populate the hidden input
                    // If you have a visible description field, update it here too
                    const visibleDescriptionElement = document.getElementById('visibleDescription'); // Assuming an ID for a visible description element
                    if (visibleDescriptionElement) {
                        // visibleDescription is an <input>, so set value not textContent
                        if ('value' in visibleDescriptionElement) {
                            visibleDescriptionElement.value = course.description;
                        } else {
                            visibleDescriptionElement.textContent = course.description;
                        }
                    }
                }
            } else {
                // If no course is selected, clear related fields
                classCodeInput.value = '';
                descriptionInput.value = '';
                const visibleDescriptionElement = document.getElementById('visibleDescription');
                if (visibleDescriptionElement) {
                    if ('value' in visibleDescriptionElement) {
                        visibleDescriptionElement.value = '';
                    } else {
                        visibleDescriptionElement.textContent = '';
                    }
                }
            }
        });
    }
}

/**
 * Fetch all classes from the API
 */
function fetchClasses() {
    const classesTableBody = document.getElementById('classes-table-body');
    if (!classesTableBody) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/classes/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Classes data:', data);
            classes = data;
            renderClassesTable();
            updateClassCount(classes.length);
        })
        .catch(error => {
            console.error('Error fetching classes:', error);
            const colspan = isInstructorPage ? 5 : 6;
            classesTableBody.innerHTML = `
                <tr>
                    <td colspan="${colspan}" class="text-center text-danger">
                        Error loading classes. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
            
            // Show a retry button
            const retryButton = document.createElement('button');
            retryButton.textContent = 'Retry';
            retryButton.className = 'btn btn-sm btn-primary mt-2';
            retryButton.addEventListener('click', () => {
                const colspan = isInstructorPage ? 5 : 6;
                classesTableBody.innerHTML = `<tr><td colspan="${colspan}" class="text-center">Loading classes...</td></tr>`;
                fetchClasses();
            });
            
            classesTableBody.querySelector('td').appendChild(retryButton);
        });
}

/**
 * Update the class count badge
 * @param {number} count - The number of classes to display
 */
function updateClassCount(count) {
    const classCountBadge = document.getElementById('classCountBadge');
    if (classCountBadge) {
        classCountBadge.textContent = count;
    }
}

/**
 * Highlight matching text in a string
 * @param {string} text - The text to search in
 * @param {string} query - The search query
 * @returns {string} - Text with highlighted matches
 */
function highlightText(text, query) {
    if (!query) return text;
    
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

/**
 * Render the classes table with optional search highlighting
 * @param {Array} classesToRender - Array of classes to render
 * @param {string} searchQuery - Optional search query for highlighting
 */
function renderClassesTable(classesToRender = classes, searchQuery = '') {
    const tbody = document.getElementById('classes-table-body');
    if (!tbody) return;
    
    if (!classesToRender || classesToRender.length === 0) {
        const colspan = isInstructorPage ? 4 : 6;
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center">No classes found</td></tr>`;
        updateClassCount(0);
        return;
    }
    
    // Update the count badge with the number of classes being displayed
    updateClassCount(classesToRender.length);
    
    tbody.innerHTML = classesToRender.map(cls => {
        const instructorName = cls.instructorName || 'Unassigned';
        const substituteName = cls.substituteInstructorName || 'None';
        const instructorTd = isInstructorPage ? '' : `<td>${highlightText(instructorName, searchQuery)}</td>`;
        const substituteTd = isInstructorPage ? '' : `<td>${highlightText(substituteName, searchQuery)}</td>`;
        const viewOnClick = isInstructorPage ? `window.location.href='/instructors/classes/${cls.id}'` : `window.location.href='/admin/classes/${cls.id}'`;
        const editBtn = isInstructorPage ? '' : `<button type="button" class="btn btn-sm btn-primary" onclick="editClass(${cls.id})" title="Edit Class">
                        <i class="fas fa-edit"></i> Edit
                    </button>`;
        const deleteBtn = isInstructorPage ? '' : `<button type="button" class="btn btn-sm btn-danger" onclick="deleteClass(${cls.id})" title="Delete Class">
                        <i class="fas fa-trash"></i> Delete
                    </button>`;
        
        return `
        <tr>
            <td>${highlightText(cls.classCode, searchQuery)}</td>
            <td>${highlightText(cls.description, searchQuery)}</td>
            <td>${highlightText(cls.schedule, searchQuery)}</td>
            ${instructorTd}
            ${substituteTd}
            <td>
                <div class="action-buttons-container">
                    <button type="button" class="btn btn-sm btn-secondary" onclick="${viewOnClick}" title="View Class">
                        <i class="fas fa-eye"></i> View
                    </button>
                    ${editBtn}
                    ${deleteBtn}
                </div>
            </td>
        </tr>
    `}).join('');
}

/**
 * Fetch courses for the dropdown
 */
function populateCourseDropdown() {
    const courseSelect = document.getElementById('course');
    if (!courseSelect) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/courses/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Courses data:', data);
            courses = data;
            
            // Clear existing options except the first one
            while (courseSelect.options.length > 1) {
                courseSelect.remove(1);
            }
            
            // Add course options
            courses.forEach(course => {
                const option = document.createElement('option');
                option.value = course.code;
                option.textContent = `${course.code} - ${course.description}`;
                courseSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error fetching courses:', error);
            
            // Add a placeholder option
            const option = document.createElement('option');
            option.disabled = true;
            option.textContent = 'Error loading courses';
            courseSelect.appendChild(option);
        });
}

/**
 * Fetch instructors for the dropdown
 */
function populateInstructorDropdown() {
    const instructorSelect = document.getElementById('instructorId');
    const substituteSelect = document.getElementById('substituteInstructorId');
    const targetSelects = [instructorSelect, substituteSelect].filter(Boolean);
    if (targetSelects.length === 0) return;

    console.log('Attempting to fetch instructors...');

    const timestamp = Date.now();
    fetch(`/api/instructors?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                console.error('HTTP error fetching instructors: Status', response.status);
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Instructors data received:', data);
            instructors = data;

            targetSelects.forEach(select => {
                while (select.options.length > 1) {
                    select.remove(1);
                }
            });

            if (instructors.length > 0) {
                instructors.forEach(instructor => {
                    const optionLabel = `${instructor.firstName} ${instructor.lastName}`;
                    targetSelects.forEach(select => {
                        const option = document.createElement('option');
                        option.value = instructor.id;
                        option.textContent = optionLabel;
                        select.appendChild(option);
                    });
                });
            } else {
                targetSelects.forEach(select => {
                    const option = document.createElement('option');
                    option.disabled = true;
                    option.textContent = 'No instructors found';
                    select.appendChild(option);
                });
                console.warn('No instructors found to populate dropdown.');
            }
        })
        .catch(error => {
            console.error('Error fetching instructors:', error);
            targetSelects.forEach(select => {
                const option = document.createElement('option');
                option.disabled = true;
                option.textContent = 'Error loading instructors';
                select.appendChild(option);
            });
        });
}

/**
 * Show the class detail view for a specific class
 * @param {number} classId - The ID of the class to show
 */
function showClassDetail(classId) {
    console.log('Showing detail for class ID:', classId);
    selectedClassId = classId;

    const selectedClass = classes.find(c => c.id === classId);
    if (!selectedClass) {
        console.error('Class not found:', classId);
        return;
    }

    const detailTitle = document.getElementById('class-detail-title');
    if (detailTitle) {
        detailTitle.textContent = `${selectedClass.classCode}: ${selectedClass.description}`;
    }

    showView('class-detail');
    getClassStudents(classId);
}

/**
 * Get students enrolled in a specific class
 * @param {number} classId - The ID of the class
 */
function getClassStudents(classId) {
    const enrolledStudentsList = document.getElementById('enrolled-students-list');
    if (!enrolledStudentsList) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    enrolledStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Loading enrolled students...</td></tr>`;
    
    fetch(`/classes/api/${classId}/students?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('Enrolled students:', students);
            
            if (students.length === 0) {
                enrolledStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students enrolled</td></tr>`;
                return;
            }
            
            enrolledStudentsList.innerHTML = '';
            
            students.forEach(student => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${student.firstName} ${student.lastName}</td>
                    <td>${student.id}</td>
                    <td>${student.yearLevel}</td>
                    <td>${student.phone}</td>
                    <td>
                        <div class="action-buttons-container">
                            <button class="btn btn-sm btn-outline-danger btn-unenroll" data-student-id="${student.id}" data-enrollment-id="${student.enrollmentId}">
                                <i class="fas fa-user-minus"></i> Unenroll
                            </button>
                        </div>
                    </td>
                `;
                
                enrolledStudentsList.appendChild(row);
                
                // Add unenroll button handler
                const unenrollBtn = row.querySelector('.btn-unenroll');
                if (unenrollBtn) {
                    unenrollBtn.addEventListener('click', function() {
                        const studentId = this.dataset.studentId;
                        const enrollmentId = parseInt(this.dataset.enrollmentId);
                        unenrollStudent(studentId, enrollmentId);
                    });
                }
            });
        })
        .catch(error => {
            console.error('Error fetching enrolled students:', error);
            enrolledStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error loading enrolled students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Get all students for the enrollment view
 */
function getAllStudents() {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Loading students...</td></tr>`;
    
    fetch(`/students/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('All students:', students);
            
            if (students.length === 0) {
                allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students found</td></tr>`;
                return;
            }
            
            // Get currently enrolled students
            const classId = selectedClassId;
            
            fetch(`/classes/api/${classId}/students?_=${timestamp}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(enrolledStudents => {
                    console.log('Enrolled students for comparison:', enrolledStudents);
                    
                    // Get IDs of enrolled students
                    const enrolledStudentIds = enrolledStudents.map(student => student.id);
                    
                    allStudentsList.innerHTML = '';
                    
                    // Show only students who are not already enrolled
                    students.filter(student => !enrolledStudentIds.includes(student.id))
                            .forEach(student => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${student.firstName} ${student.lastName}</td>
                            <td>${student.id}</td>
                            <td>${student.yearLevel}</td>
                            <td>${student.phone}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                                    <i class="fas fa-user-plus"></i> Enroll
                                </button>
                            </td>
                        `;
                        
                        allStudentsList.appendChild(row);
                        
                        // Add enroll button handler
                        const enrollBtn = row.querySelector('.btn-enroll');
                        if (enrollBtn) {
                            enrollBtn.addEventListener('click', function() {
                                const studentId = this.dataset.studentId;
                                enrollStudent(studentId);
                            });
                        }
                    });
                    
                    if (allStudentsList.children.length === 0) {
                        allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">All students are already enrolled in this class</td></tr>`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching enrolled students for comparison:', error);
                    // Continue showing all students if we can't get enrollment data
                    showAllStudents(students);
                });
        })
        .catch(error => {
            console.error('Error fetching all students:', error);
            allStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error loading students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Search students in the all students list
 * @param {string} query - The search query
 */
function searchStudents(query) {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    query = query.toLowerCase().trim();
    
    if (query === '') {
        getAllStudents();
        return;
    }
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Searching students...</td></tr>`;
    
    fetch(`/students/api/search?query=${encodeURIComponent(query)}&_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('Search results:', students);
            
            if (students.length === 0) {
                allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students found matching "${query}"</td></tr>`;
                return;
            }
            
            // Get currently enrolled students
            const classId = selectedClassId;
            
            fetch(`/classes/api/${classId}/students?_=${timestamp}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(enrolledStudents => {
                    console.log('Enrolled students for comparison:', enrolledStudents);
                    
                    // Get IDs of enrolled students
                    const enrolledStudentIds = enrolledStudents.map(student => student.id);
                    
                    allStudentsList.innerHTML = '';
                    
                    // Show only students who are not already enrolled
                    students.filter(student => !enrolledStudentIds.includes(student.id))
                            .forEach(student => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${student.firstName} ${student.lastName}</td>
                            <td>${student.id}</td>
                            <td>${student.yearLevel}</td>
                            <td>${student.phone}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                                    <i class="fas fa-user-plus"></i> Enroll
                                </button>
                            </td>
                        `;
                        
                        allStudentsList.appendChild(row);
                        
                        // Add enroll button handler
                        const enrollBtn = row.querySelector('.btn-enroll');
                        if (enrollBtn) {
                            enrollBtn.addEventListener('click', function() {
                                const studentId = this.dataset.studentId;
                                enrollStudent(studentId);
                            });
                        }
                    });
                    
                    if (allStudentsList.children.length === 0) {
                        allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No matching students available for enrollment</td></tr>`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching enrolled students for comparison:', error);
                    // Continue showing all students if we can't get enrollment data
                    showAllStudents(students);
                });
        })
        .catch(error => {
            console.error('Error searching students:', error);
            allStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error searching students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Show all students without filtering based on enrollment
 * @param {Array} students - The students to display
 */
function showAllStudents(students) {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    allStudentsList.innerHTML = '';
    
    students.forEach(student => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${student.firstName} ${student.lastName}</td>
            <td>${student.id}</td>
            <td>${student.yearLevel}</td>
            <td>${student.phone}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                    <i class="fas fa-user-plus"></i> Enroll
                </button>
            </td>
        `;
        
        allStudentsList.appendChild(row);
        
        // Add enroll button handler
        const enrollBtn = row.querySelector('.btn-enroll');
        if (enrollBtn) {
            enrollBtn.addEventListener('click', function() {
                const studentId = this.dataset.studentId;
                enrollStudent(studentId);
            });
        }
    });
}

/**
 * Enroll a student in the selected class
 * @param {string} studentId - The ID of the student to enroll
 */
function enrollStudent(studentId) {
    if (!selectedClassId) {
        console.error('No class selected for enrollment');
        return;
    }
    
    console.log(`Enrolling student ${studentId} in class ${selectedClassId}`);
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/classes/api/${selectedClassId}/enroll`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            studentId: studentId
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Enrollment successful:', data);
        
        // Clear previous floating notifications, then show a success message
        if (typeof window.clearFloatingNotifications === 'function') {
            window.clearFloatingNotifications();
        }
        window.showSuccessNotification('Student enrolled successfully!');
        
        // Refresh the class detail view
        showClassDetail(selectedClassId);
    })
    .catch(error => {
        console.error('Error enrolling student:', error);
        window.showErrorNotification(`Error enrolling student: ${error.message}`);
    });
}

/**
 * Unenroll a student from the selected class
 * @param {string} studentId - The ID of the student to unenroll
 * @param {number} enrollmentId - The ID of the enrollment record
 */
function unenrollStudent(studentId, enrollmentId) {
    if (!selectedClassId) {
        console.error('No class selected for unenrollment');
        return;
    }
    
    if (!confirm(`Are you sure you want to unenroll this student from the class?`)) {
        return;
    }
    
    console.log(`Unenrolling student ${studentId} from class ${selectedClassId} with enrollment ID ${enrollmentId}`);
    
    // Using the endpoint that takes an enrollment ID
    fetch(`/classes/api/${selectedClassId}/unenroll/${enrollmentId}`, {
        method: 'DELETE',
        headers: {
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Unenrollment successful:', data);
        
        // Clear previous floating notifications, then show a success message
        if (typeof window.clearFloatingNotifications === 'function') {
            window.clearFloatingNotifications();
        }
        window.showSuccessNotification('Student unenrolled successfully!');
        
        // Refresh the class detail view
        showClassDetail(selectedClassId);
    })
    .catch(error => {
        console.error('Error unenrolling student:', error);
        window.showErrorNotification(`Error unenrolling student: ${error.message}`);
    });
}

/**
 * Show the modal for adding a new class
 */
function showAddClassModal() {
    console.log('Showing add class modal');
    const classForm = document.getElementById('class-form');
    const modalTitle = document.getElementById('class-modal-title');
    const classIdInput = document.getElementById('classId');
    const courseSelect = document.getElementById('course');
    const descriptionInput = document.getElementById('description');
    const visibleDescriptionInput = document.getElementById('visibleDescription');
    
    if (classForm && modalTitle && classIdInput && courseSelect) {
        classForm.reset();
        modalTitle.textContent = 'Add New Class';
        classIdInput.value = ''; // Clear classId for new class
        selectedClassId = null; // Clear selected class ID
        courseSelect.disabled = false; // Enable course selection for new class
        // Ensure description and visible description are editable for new classes
        if (descriptionInput) descriptionInput.readOnly = false;
        if (visibleDescriptionInput) visibleDescriptionInput.readOnly = false;

        // Ensure schedule builder is reset for adding a new class (no auto-filled slots)
        if (typeof resetScheduleBuilder === 'function') {
            try {
                resetScheduleBuilder();
            } catch (err) {
                console.error('Error resetting schedule builder for add modal:', err);
            }
        }
    
        // Use Bootstrap's modal API to show the modal (get existing instance or create if needed)
        const modalElement = document.getElementById('addClassModal');
        let addClassModal = bootstrap.Modal.getInstance(modalElement);
        if (!addClassModal) {
            addClassModal = new bootstrap.Modal(modalElement);
        }
        addClassModal.show();
        
        // Set initial focus (optional)
        const firstInput = document.getElementById('course');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
}

/**
 * Edit an existing class
 * @param {number} classId - The ID of the class to edit
 */
function editClass(classId) {
    console.log('Editing class ID:', classId);
    
    const classToEdit = classes.find(c => c.id === classId);
    if (!classToEdit) {
        console.error('Class not found:', classId);
        return;
    }
    
    // Set up the form with existing values
    const classForm = document.getElementById('class-form');
    const classIdInput = document.getElementById('classId');
    const classCodeInput = document.getElementById('classCode');
    const courseSelect = document.getElementById('course');
    const descriptionInput = document.getElementById('description');
    const visibleDescriptionInput = document.getElementById('visibleDescription');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdSelect = document.getElementById('instructorId');
    const substituteInstructorSelect = document.getElementById('substituteInstructorId');
    const modalTitle = document.getElementById('class-modal-title');
    
    if (classForm && classIdInput && classCodeInput && courseSelect && 
        descriptionInput && visibleDescriptionInput && 
        scheduleInput && instructorIdSelect && modalTitle) {
        // Extract course code from class code (before the dash)
        const courseCode = classToEdit.classCode.split('-')[0];
        
        classIdInput.value = classToEdit.id;
        classCodeInput.value = classToEdit.classCode;
        
        // Set the course dropdown
        for (let i = 0; i < courseSelect.options.length; i++) {
            if (courseSelect.options[i].value === courseCode) {
                courseSelect.selectedIndex = i;
                break;
            }
        }

        // Ensure the course select reflects the existing course.
        // Try setting value directly (covers cases where options exist but loop didn't match).
        if (courseSelect.value !== courseCode) {
            courseSelect.value = courseCode;
        }
        // If still not matched (options may not have been populated), add a fallback option so the UI shows the correct course
        if (courseSelect.value !== courseCode) {
            const fallbackOption = document.createElement('option');
            fallbackOption.value = courseCode;
            fallbackOption.textContent = `${courseCode} - ${classToEdit.description || ''}`;
            courseSelect.appendChild(fallbackOption);
            courseSelect.value = courseCode;
        }

        // Prevent changing course when editing — course is fixed once created
        // Keep the select disabled so user can't change it, but the value remains readable by JS when saving.
        courseSelect.disabled = true;
        
        descriptionInput.value = classToEdit.description;
        visibleDescriptionInput.value = classToEdit.description;
        // Make description fields read-only to prevent edits after creation
        if (descriptionInput) descriptionInput.readOnly = true;
        if (visibleDescriptionInput) visibleDescriptionInput.readOnly = true;
        
        // Set up the schedule builder with existing schedule
        if (typeof setupScheduleBuilder === 'function') {
            // Reset the schedule builder first, then parse and display the existing schedule
            if (typeof resetScheduleBuilder === 'function') {
                resetScheduleBuilder();
            }
            setupScheduleBuilder(classToEdit.schedule); // Pass the existing schedule to setup
        } else {
            scheduleInput.value = classToEdit.schedule;
        }
        
        // Ensure the schedule input is set to the saved data
        scheduleInput.value = classToEdit.schedule;
        
        // *** Set the instructor dropdown based on the class data ***
        for (let i = 0; i < instructorIdSelect.options.length; i++) {
            // Note: instructorId from classToEdit is an integer, option value is string
            if (parseInt(instructorIdSelect.options[i].value) === classToEdit.instructorId) {
                instructorIdSelect.selectedIndex = i;
                break;
            }
        }
        if (substituteInstructorSelect) {
            substituteInstructorSelect.value = classToEdit.substituteInstructorId
                ? classToEdit.substituteInstructorId.toString()
                : '';
        }
        // *** End of instructor dropdown setting ***
        
        modalTitle.textContent = 'Edit Class';
        selectedClassId = classId;

        // Use Bootstrap's modal API to show the modal (get existing instance or create if needed)
        const modalElement = document.getElementById('addClassModal');
        let addClassModal = bootstrap.Modal.getInstance(modalElement);
        if (!addClassModal) {
            addClassModal = new bootstrap.Modal(modalElement);
        }
        addClassModal.show();

        // Set initial focus (optional)
        const firstInput = document.getElementById('course');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
}

/**
 * Save a class (create or update)
 */
function saveClass() {
    console.log('Saving class');

    // Get form values
    const classId = document.getElementById('classId').value;
    const courseSelect = document.getElementById('course');
    const classCodeInput = document.getElementById('classCode');
    const descriptionInput = document.getElementById('description');
    const visibleDescriptionInput = document.getElementById('visibleDescription');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdSelect = document.getElementById('instructorId');
    const substituteInstructorSelect = document.getElementById('substituteInstructorId');

    console.log('Form values:', {
        classId,
        course: courseSelect.value,
        classCode: classCodeInput.value,
        description: descriptionInput.value,
        schedule: scheduleInput.value,
        instructorId: instructorIdSelect.value
    });

    // Validate required fields
    if (!courseSelect.value) {
        alert('Please select a course');
        courseSelect.focus();
        return;
    }

    const courseCode = courseSelect.value;
    let classCode = classCodeInput.value.trim();
    const description = descriptionInput.value.trim();
    const schedule = scheduleInput.value.trim();
    const instructorId = instructorIdSelect.value;
    const substituteInstructorId = substituteInstructorSelect ? substituteInstructorSelect.value : '';

    console.log('Trimmed values:', {
        courseCode,
        classCode,
        description,
        schedule,
        instructorId,
        substituteInstructorId
    });

    if (instructorId && substituteInstructorId && instructorId === substituteInstructorId) {
        alert('Instructor and substitute instructor must be different people.');
        return;
    }

    // Validate other required fields
    if (!classCode || !description || !schedule) {
        console.log('Validation failed:', {
            classCode: !classCode,
            description: !description,
            schedule: !schedule
        });
        alert('Please fill in all required fields');
        return;
    }

    // If this is a new class (no classId), directly use the manually entered classCode
    if (!classId) {
        saveClassWithData(classCode); // Use the already trimmed classCode from the input
    } else {
        // If it's an existing class, use the existing classId and the potentially updated classCode
        saveClassWithData(classCode); 
    }

    function saveClassWithData(finalClassCode) {
        // Find the selected course to get its ID (try case-insensitive match)
        const selectedValue = (courseSelect.value || '').toString().trim();
        let selectedCourse = courses.find(c => (c.code || '').toString().trim().toLowerCase() === selectedValue.toLowerCase());

        // If not found, try parsing the classCode for a course prefix and match that
        if (!selectedCourse && finalClassCode) {
            const parsedCourseCode = finalClassCode.split('-')[0].trim();
            selectedCourse = courses.find(c => (c.code || '').toString().trim().toLowerCase() === parsedCourseCode.toLowerCase());
        }

        if (!selectedCourse) {
            // As a last resort, attempt to use the select's value directly if it looks like a course code
            if (selectedValue) {
                // Create a minimal selectedCourse object without an id — backend will validate and may reject if missing
                selectedCourse = { id: null, code: selectedValue, description: visibleDescriptionInput ? visibleDescriptionInput.value : '' };
            }
        }

        if (!selectedCourse) {
            alert('Please select a valid course');
            return;
        }

        const classData = {
            classCode: finalClassCode,
            description: description,
            schedule: schedule,
            instructorId: instructorId,
            substituteInstructorId: substituteInstructorId,
            courseId: selectedCourse.id
        };

        console.log('Class data to save:', classData);
        console.log('Selected course:', selectedCourse);

        // Determine if this is a create or update operation
        const isUpdate = !!classId;
        const url = isUpdate 
            ? `/classes/api/update/${classId}`
            : '/classes/api/create';
        const method = isUpdate ? 'PUT' : 'POST';

        console.log('Making request to:', url, 'with method:', method);

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(classData)
        })
        .then(response => {
            console.log('Response status:', response.status);
            return response.json().then(data => {
                console.log('Response data:', data);
                if (!response.ok) {
                    throw new Error(data.error || data.message || `HTTP error! Status: ${response.status}`);
                }
                return data;
            });
        })
        .then(data => {
            console.log('Class saved successfully:', data);
            closeClassModal();
            window.showSuccessNotification(isUpdate ? 'Class updated successfully!' : 'Class created successfully!');
            fetchClasses();
        })
        .catch(error => {
            console.error('Error saving class:', error);
            window.showErrorNotification(`Error saving class: ${error.message}`);
        });
    }
}

/**
 * Delete a class
 * @param {number} classId - The ID of the class to delete
 */
function deleteClass(classId) {
    console.log('Deleting class ID:', classId);
    
    const classToDelete = classes.find(c => c.id === classId);
    if (!classToDelete) {
        console.error('Class not found:', classId);
        return;
    }
    
    // Set up the confirmation modal
    const confirmationText = document.getElementById('confirmation-text');
    
    if (confirmationText) {
        confirmationText.innerHTML = `
            Are you sure you want to delete class <strong>${classToDelete.classCode}</strong>?<br>
            This will remove all enrollments and attendance records for this class.
        `;
    }
    
    // Store the class ID for the confirmation handler
    selectedClassId = classId;
    
    // Show the confirmation modal using Bootstrap's modal API
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmation-modal'));
    confirmationModal.show();
}

/**
 * Confirm and execute class deletion
 */
function confirmDeleteClass() {
    if (!selectedClassId) {
        console.error('No class selected for deletion');
        return;
    }
    
    console.log('Confirming deletion of class ID:', selectedClassId);
    
    fetch(`/classes/api/delete/${selectedClassId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Class deleted successfully:', data);
        
        // Close the confirmation modal
        closeConfirmationModal();
        
        // Show a success message
        window.showSuccessNotification('Class deleted successfully!');
        
        // Refresh the classes list
        fetchClasses();
    })
    .catch(error => {
        console.error('Error deleting class:', error);
        window.showErrorNotification(`Error deleting class: ${error.message}`);
        
        // Close the confirmation modal
        closeConfirmationModal();
    });
}

/**
 * Handle Delete All Classes click (admin only)
 */
function onDeleteAllClick() {
    // Reuse the confirmation modal
    const confirmationText = document.getElementById('confirmation-text');
    if (confirmationText) {
        confirmationText.innerHTML = `
            <div class="text-danger"><strong>Danger:</strong> This will permanently delete <strong>ALL classes</strong>, including sessions, enrollments, and attendance records.</div>
            <div>Are you absolutely sure you want to proceed?</div>
        `;
    }
    // Mark special action type
    const actionType = document.getElementById('confirmActionType');
    if (actionType) actionType.value = 'delete-all-classes';
    selectedClassId = null;
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmation-modal'));
    confirmationModal.show();
}

// (No global confirm override; handled in setupEventListeners)

/**
 * Close the class modal
 */
function closeClassModal() {
    // Use Bootstrap's modal API to hide the modal
    const addClassModal = bootstrap.Modal.getInstance(document.getElementById('addClassModal'));
    if (addClassModal) {
        addClassModal.hide();
    }
}

/**
 * Close the confirmation modal
 */
function closeConfirmationModal() {
    // Use Bootstrap's modal API to hide the modal
    const confirmationModal = bootstrap.Modal.getInstance(document.getElementById('confirmation-modal'));
    if (confirmationModal) {
        confirmationModal.hide();
    }
}

/**
 * Show the specified view and hide others
 * @param {string} viewName - The name of the view to show
 */
function showView(viewName) {
    currentView = viewName;
    
    const classesView = document.getElementById('classes-view');
    const classDetailView = document.getElementById('class-detail-view');
    const studentSelectionView = document.getElementById('student-selection-view');
    
    if (classesView && classDetailView && studentSelectionView) {
        classesView.classList.add('d-none');
        classDetailView.classList.add('d-none');
        studentSelectionView.classList.add('d-none');
        
        switch (viewName) {
            case 'classes':
                classesView.classList.remove('d-none');
                break;
            case 'class-detail':
                classDetailView.classList.remove('d-none');
                break;
            case 'student-selection':
                studentSelectionView.classList.remove('d-none');
                break;
        }
    }
}

/**
 * Export classes to Excel
 */
async function handleExportClasses() {
    try {
        const response = await fetch('/classes/api/export-classes');

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Export failed');
        }

        // Get the filename from the response headers
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'classes_export.xlsx';
        if (disposition && disposition.indexOf('filename=') !== -1) {
            filename = disposition.split('filename=')[1].replace(/"/g, '');
        }

        // Create blob and download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        window.showSuccessNotification('Classes exported successfully');
    } catch (error) {
        console.error('Export error:', error);
        window.showErrorNotification(`Failed to export classes: ${error.message}`);
    }
}

/**
 * Import classes from XLSX
 */
async function handleImportClasses(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Clear the input
    event.target.value = '';

    // Check file type
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
        window.showErrorNotification('Please select an XLSX file');
        return;
    }

    try {
        // Create FormData to send the file
        const formData = new FormData();
        formData.append('file', file);

        // Send file to backend
        const response = await fetch('/classes/api/import-classes', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            // Refresh the classes list
            fetchClasses();
            window.showSuccessNotification(`Successfully imported ${data.imported || 0} classes`);

            if (data.errors && data.errors.length > 0) {
                console.warn('Import warnings:', data.errors);
                // Could show a modal with warnings if needed
            }
        } else {
            throw new Error(data.message || 'Import failed');
        }
    } catch (error) {
        console.error('Import error:', error);
        window.showErrorNotification(`Failed to import classes: ${error.message}`);
    }
}


