/**
 * Student Management System
 * Handles CRUD operations for student data
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM element references
    const elements = {
        // Tables and counters
        studentsTableBody: document.getElementById('studentsTableBody'),
        studentCounter: document.getElementById('studentCountBadge'),
        // Search and filter
        searchInput: document.getElementById('searchInput'),
        sortYearLevel: document.getElementById('sortYearLevel'),
        // Buttons
        btnEnrollStudent: document.getElementById('btnEnrollStudent'),
        // Modals
        enrollModal: document.getElementById('enrollModal'),
        picturesModal: document.getElementById('picturesModal'),
        editModal: document.getElementById('editModal'),
        editPicturesModal: document.getElementById('editPicturesModal'),
        confirmationModal: document.getElementById('confirmationModal'),
        // Modal close buttons
        closeEnrollModal: document.getElementById('closeEnrollModal'),
        closePicturesModal: document.getElementById('closePicturesModal'),
        closeEditModal: document.getElementById('closeEditModal'),
        closeEditPicturesModal: document.getElementById('closeEditPicturesModal'),
        // Modal confirmation buttons
        confirmYesBtn: document.getElementById('confirmYesBtn'),
        confirmNoBtn: document.getElementById('confirmNoBtn'),
        // Forms
        enrollStudentForm: document.getElementById('enrollStudentForm'),
        editStudentForm: document.getElementById('editStudentForm'),
        // Picture management
        uploadPicturesBtn: document.getElementById('uploadPicturesBtn'),
        editUploadPicturesBtn: document.getElementById('editUploadPicturesBtn'),
        picturesPreview: document.getElementById('picturesPreview'),
        editPicturesPreview: document.getElementById('editPicturesPreview'),
        savePicturesBtn: document.getElementById('savePicturesBtn'),
        saveEditPicturesBtn: document.getElementById('saveEditPicturesBtn'),
        studentImageForm: document.getElementById('student-image-form'),
        uploadButton: document.querySelector('#student-image-form button[type="submit"]')
    };

    // Application state
    const state = {
        students: [],
        filteredStudents: [],
        currentStudentId: null,
        uploadedPictures: [],
        editUploadedPictures: [],
        isUpdatingCounter: false,
        sortOrder: 'asc',
        currentYearLevelFilter: ''
    };

    const YEAR_LEVEL_LABELS = {
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4'
    };

    const YEAR_LEVEL_VALUES = {
        '1st Year': '1',
        '2nd Year': '2',
        '3rd Year': '3',
        '4th Year': '4',
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4'
    };
    
    // Map display value to backend format
    const YEAR_LEVEL_TO_BACKEND = {
        '1': '1st Year',
        '2': '2nd Year',
        '3': '3rd Year',
        '4': '4th Year'
    };
    
    // Map backend format to display value
    const YEAR_LEVEL_FROM_BACKEND = {
        '1st Year': '1',
        '2nd Year': '2',
        '3rd Year': '3',
        '4th Year': '4'
    };

    const DEFAULT_DEPARTMENT = 'BSIT';

    // Initialize Bootstrap modals
    let editModal, picturesModal, confirmationModal, enrollModal;

    // Fix confirmation modal classes
    const confirmationModalEl = document.getElementById('confirmationModal');
    if (confirmationModalEl) {
        confirmationModalEl.classList.remove('modal-overlay');
        confirmationModalEl.classList.add('modal', 'fade');
    }

    // Initialize the application
    init();

    // Add event listeners
    function addEventListeners() {
        // Open enroll student modal
        if (elements.btnEnrollStudent) {
            elements.btnEnrollStudent.addEventListener('click', () => {
                if (typeof enrollModal !== 'undefined' && enrollModal) {
                    enrollModal.show();
                } else {
                    console.error('Enroll modal not initialized.');
                }
            });
        }

        // Close modals - using data-bs-dismiss in HTML is preferred
        // if (elements.closeEnrollModal) {
        //     elements.closeEnrollModal.addEventListener('click', () => {
        //         if (typeof enrollModal !== 'undefined' && enrollModal) enrollModal.hide();
        //     });
        // }
        // if (elements.closePicturesModal) {
        //     elements.closePicturesModal.addEventListener('click', () => {
        //         if (typeof picturesModal !== 'undefined' && picturesModal) picturesModal.hide();
        //     });
        // }
        // if (elements.closeEditModal) {
        //     elements.closeEditModal.addEventListener('click', () => {
        //         if (typeof editModal !== 'undefined' && editModal) editModal.hide();
        //     });
        // }
        // if (elements.closeEditPicturesModal) {
        //     elements.closeEditPicturesModal.addEventListener('click', () => {
        //         if (typeof editPicturesModal !== 'undefined' && editPicturesModal) editPicturesModal.hide();
        //     });
        // }

        // Form submissions
        if (elements.enrollStudentForm) {
            elements.enrollStudentForm.addEventListener('submit', (e) => {
                e.preventDefault(); // Prevent default form submission
                handleEnrollSubmit(e);
            });

            // Remove the separate click listener since we're handling the form submit
            const enrollSubmitButton = elements.enrollStudentForm.querySelector('button[type="submit"]');
            if (enrollSubmitButton) {
                enrollSubmitButton.removeEventListener('click', handleEnrollButtonClick);
            }
        }
        if (elements.editStudentForm) {
            elements.editStudentForm.addEventListener('submit', handleEditStudent);
        }
        if (elements.studentImageForm) {
            elements.studentImageForm.addEventListener('submit', handleImageUpload);
        }

        // Search functionality
        if (elements.searchInput) {
            elements.searchInput.addEventListener('input', debounce(handleSearch, 300));
        }
        
        // Clear search
        const clearSearchBtn = document.getElementById('clearSearch');
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                elements.searchInput.value = '';
                clearSearchBtn.style.display = 'none';
                handleSearch();
            });
        }

        // Year level filter
        const yearLevelFilter = document.getElementById('yearLevelFilter');
        if (yearLevelFilter) {
            yearLevelFilter.addEventListener('change', (e) => {
                state.currentYearLevelFilter = e.target.value;
                handleSearch();
            });
        }

        // Sort by year level
        if (elements.sortYearLevel) {
            elements.sortYearLevel.addEventListener('click', () => {
                state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
                elements.sortYearLevel.classList.toggle('asc', state.sortOrder === 'asc');
                elements.sortYearLevel.classList.toggle('desc', state.sortOrder === 'desc');
                handleSearch();
            });
        }

        // Confirmation modal handlers - NOTE: These event listeners are now added directly to the buttons in the modal HTML
        // if (elements.confirmYesBtn) {
        //     elements.confirmYesBtn.addEventListener('click', confirmDeleteStudent);
        // }
        // if (elements.confirmNoBtn) {
        //     elements.confirmNoBtn.addEventListener('click', () => {
        //         hideModal(elements.confirmationModal);
        //     });
        // }

        // Table click delegation for actions
        if (elements.studentsTableBody) {
            console.log('Adding table action event listener');
            // Ensure only one listener is added
            elements.studentsTableBody.removeEventListener('click', handleTableActions);
            elements.studentsTableBody.addEventListener('click', handleTableActions);
        }

        // Remove direct event listeners for action buttons - Rely on delegated event listener above
        // const actionButtons = document.querySelectorAll('.btn-edit, .btn-action-modern.btn-edit, .btn-pictures, .btn-action-modern.btn-pictures, .btn-delete, .fas.fa-trash');
        // console.log('Found action buttons:', actionButtons.length);
        
        // actionButtons.forEach(btn => {
        //     btn.addEventListener('click', (e) => {
        //         e.preventDefault();
        //         e.stopPropagation();
        //         console.log('Action button clicked:', btn);
                
        //         if (!state.students || state.students.length === 0) {
        //             console.error('No students loaded in state');
        //             return;
        //         }
                
        //         const studentId = btn.dataset.studentId;
        //         if (!studentId) {
        //             console.error('No student ID found on button');
        //             return;
        //         }

        //         if (btn.classList.contains('btn-edit') || btn.classList.contains('btn-action-modern')) {
        //             console.log('Opening edit modal for student:', studentId);
        //             openEditModal(studentId);
        //         } else if (btn.classList.contains('btn-pictures')) {
        //             const student = state.students.find(s => s.id === studentId);
        //             if (student) {
        //                 console.log('Opening pictures modal for student:', studentId);
        //                 openPicturesModal(studentId, `${student.firstName} ${student.lastName}`);
        //             } else {
        //                 console.error('Student not found:', studentId);
        //             }
        //         } else if (btn.classList.contains('btn-delete') || btn.classList.contains('fa-trash')) {
        //             console.log('Opening delete confirmation for student:', studentId);
        //             openDeleteConfirmation(studentId);
        //         }
        //     });
        // });

        
        // Export Students
        const btnExportStudents = document.getElementById('btnExportStudents');
        if (btnExportStudents) {
            btnExportStudents.addEventListener('click', handleExportStudents);
        }
        
        // Import Students
        const btnImportStudents = document.getElementById('btnImportStudents');
        if (btnImportStudents) {
            btnImportStudents.addEventListener('click', () => {
                document.getElementById('importFileInput').click();
            });
        }
        
        // File input change handler
        const importFileInput = document.getElementById('importFileInput');
        if (importFileInput) {
            importFileInput.addEventListener('change', handleImportStudents);
        }
    }

    // Initialize the application
    async function init() {
        try {
            // Wait for DOM to be fully loaded
            if (document.readyState === 'loading') {
                await new Promise(resolve => {
                    document.addEventListener('DOMContentLoaded', resolve);
                });
            }

            // Initialize elements after DOM is loaded
            elements.studentsTableBody = document.getElementById('studentsTableBody');
            elements.studentCounter = document.getElementById('studentCountBadge');
            elements.searchInput = document.getElementById('searchInput');
            elements.sortYearLevel = document.getElementById('sortYearLevel');
            elements.btnEnrollStudent = document.getElementById('btnEnrollStudent');
            elements.enrollModal = document.getElementById('enrollModal');
            elements.picturesModal = document.getElementById('picturesModal');
            elements.editModal = document.getElementById('editModal');
            elements.editPicturesModal = document.getElementById('editPicturesModal');
            elements.confirmationModal = document.getElementById('confirmationModal');
            elements.confirmYesBtn = document.getElementById('confirmYesBtn');
            elements.confirmNoBtn = document.getElementById('confirmNoBtn');

            // Add event listeners for delete confirmation
            if (elements.confirmYesBtn) {
                elements.confirmYesBtn.addEventListener('click', confirmDeleteStudent);
            }
            if (elements.confirmNoBtn) {
                elements.confirmNoBtn.addEventListener('click', () => {
                    if (typeof confirmationModal !== 'undefined' && confirmationModal) {
                        confirmationModal.hide();
                    }
                });
            }

            // Log modal elements
            console.log('Modal elements found:', {
                enrollModal: elements.enrollModal,
                picturesModal: elements.picturesModal,
                editModal: elements.editModal,
                editPicturesModal: elements.editPicturesModal,
                confirmationModal: elements.confirmationModal
            });

            // Initialize Bootstrap modals
            initializeModals();
            
            // Load students before adding event listeners
            console.log('Loading students...');
            await fetchStudents();
            console.log('Students loaded:', state.students);
            
            addEventListeners();
            
            // Start real-time updates
            startRealTimeUpdates();
        } catch (error) {
            console.error('Initialization error:', error);
            showAlert('Failed to load students. Please try again.', 'danger');
        }
    }

    // Function to initialize modals (could be called on demand or during init)
    function initializeModals() {
        console.log('Initializing Bootstrap modal instances...');
        try {
            const editModalEl = document.getElementById('editModal');
            const picturesModalEl = document.getElementById('picturesModal');
            const confirmationModalEl = document.getElementById('confirmationModal');
            const enrollModalEl = document.getElementById('enrollModal');

            if (editModalEl) editModal = new bootstrap.Modal(editModalEl);
            else console.error('Edit modal element not found');

            if (picturesModalEl) picturesModal = new bootstrap.Modal(picturesModalEl);
            else console.error('Pictures modal element not found');

            if (confirmationModalEl) confirmationModal = new bootstrap.Modal(confirmationModalEl);
            else console.error('Confirmation modal element not found');
            
            if (enrollModalEl) enrollModal = new bootstrap.Modal(enrollModalEl);
            else console.error('Enroll modal element not found');

            console.log('Bootstrap modal instances initialized.');
        } catch (error) {
            console.error('Error initializing Bootstrap modal instances:', error);
        }
    }

    // Fetch students from the API
    async function fetchStudents() {
        try {
            const response = await fetch('/students/api/list');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.message || 'Failed to load students');
            }
            state.students = data.students.map(student => ({
                ...student,
                department: student.department || DEFAULT_DEPARTMENT,
                hasFaceImages: student.hasFaceImages || false
            }));
            state.filteredStudents = [...state.students];
            updateStudentCounter();
            renderStudentsTable(state.filteredStudents);
            console.log('Students loaded successfully:', state.students.length);
            return data.students;
        } catch (error) {
            console.error('Error fetching students:', error);
            throw error;
        }
    }

    // Render the students table
    function renderStudentsTable(students) {
        if (!elements.studentsTableBody) return;
        
        elements.studentsTableBody.innerHTML = '';
        
        if (students.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="5" class="text-center">No students found</td>
            `;
            elements.studentsTableBody.appendChild(row);
            return;
        }
        
        students.forEach(student => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>${student.lastName}, ${student.firstName}${student.middleName ? ' ' + student.middleName : ''}</td>
                <td>${student.id}</td>
                <td>${mapYearValueToLabel(student.yearLevel)}</td>
                <td class="${student.hasFaceImages ? 'text-success' : 'text-danger'}"><strong>${student.hasFaceImages ? 'Captured' : 'Not Captured'}</strong></td>
                <td>
                    <div class="action-buttons-container">
                        <button type="button" class="btn btn-sm btn-primary btn-edit" data-student-id="${student.id}" title="Edit Student">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button type="button" class="btn btn-sm btn-danger btn-delete" data-student-id="${student.id}" title="Delete Student">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                        <button type="button" class="btn btn-sm btn-primary btn-pictures" data-student-id="${student.id}" title="Capture Face">
                            <i class="fas fa-camera-retro"></i> Capture
                        </button>
                        <button type="button" class="btn btn-sm btn-secondary btn-view-photos" data-student-id="${student.id}" title="View Photos">
                            <i class="fas fa-eye"></i> View
                        </button>
                    </div>
                </td>
            `;
            
            elements.studentsTableBody.appendChild(row);
        });
    }

    // Handle table actions (edit, delete, pictures)
    function handleTableActions(e) {
        const target = e.target;
        console.log('Table action clicked: (Target)', target);

        if (!state.students || state.students.length === 0) {
            console.error('No students loaded in state');
            return;
        }

        // Find the closest button element that has a data-student-id
        const button = target.closest('button[data-student-id]');
        console.log('Table action clicked: (Button found)', button);

        if (!button) return;

        const studentId = button.dataset.studentId;
        if (!studentId) {
            console.error('No student ID found on button');
            return;
        }

        if (button.classList.contains('btn-edit')) {
            console.log('-- Handling Edit Button Click');
            console.log('Edit button clicked for student:', studentId);
            openEditModal(studentId);
        } else if (button.classList.contains('btn-delete')) {
            console.log('-- Handling Delete Button Click');
            console.log('Delete button clicked for student:', studentId);
            const student = state.students.find(s => s.id === studentId);
            if (student) {
                state.currentStudentId = studentId;
                const confirmationText = document.getElementById('confirmationText');
                if (confirmationText) {
                    confirmationText.textContent = `Are you sure you want to delete ${student.firstName} ${student.lastName}?`;
                }
                // Show the modal using the Bootstrap instance
                if (typeof confirmationModal !== 'undefined' && confirmationModal) {
                     confirmationModal.show();
                } else {
                    console.error('Confirmation modal not initialized.');
                }
            }
        } else if (button.classList.contains('btn-pictures')) {
            console.log('-- Handling Capture Button Click');
            console.log('Capture button clicked for student:', studentId);
            const student = state.students.find(s => s.id === studentId);
            if (student) {
                console.log('Calling captureStudentFace for student:', studentId);
                captureStudentFace(studentId, `${student.firstName} ${student.lastName}`);
            } else {
                console.error('Student not found:', studentId);
            }
        } else if (button.classList.contains('btn-view-photos')) {
            console.log('-- Handling View Photos Button Click');
            console.log('View photos button clicked for student:', studentId);
            const student = state.students.find(s => s.id === studentId);
            if (student) {
                console.log('Calling viewStudentPhotos for student:', studentId);
                viewStudentPhotos(studentId, `${student.firstName} ${student.lastName}`);
            } else {
                console.error('Student not found:', studentId);
            }
        }
    }

    // Open the edit modal for a student
    function openEditModal(studentId) {
        console.log('-- Inside openEditModal for student:', studentId);
        console.log('Opening edit modal for student:', studentId);
        const student = state.students.find(s => s.id === studentId);
        if (!student) {
            console.error('Student not found:', studentId);
            return;
        }
        
        state.currentStudentId = studentId;
        
        const editFirstNameInput = document.getElementById('editFirstName');
        const editMiddleNameInput = document.getElementById('editMiddleName');
        const editLastNameInput = document.getElementById('editLastName');
        const editStudentIdInput = document.getElementById('editStudentId');
        const editYearLevelSelect = document.getElementById('editYearLevel');
        const editDepartmentSelect = document.getElementById('editDepartment');

        if (!editFirstNameInput || !editLastNameInput || !editStudentIdInput || !editYearLevelSelect || !editDepartmentSelect) {
            console.error('Edit modal input elements not found:', {
                editFirstNameInput,
                editMiddleNameInput,
                editLastNameInput,
                editStudentIdInput,
                editYearLevelSelect,
                editDepartmentSelect
            });
            return;
        }

        editFirstNameInput.value = student.firstName || '';
        if (editMiddleNameInput) editMiddleNameInput.value = student.middleName || '';
        editLastNameInput.value = student.lastName || '';
        editStudentIdInput.value = student.id;
        editDepartmentSelect.value = student.department || DEFAULT_DEPARTMENT;
        const yearLevelValue = mapYearLabelToValue(student.yearLevel) || student.yearLevel || '1';
        editYearLevelSelect.value = yearLevelValue;
        
        const modalEl = document.getElementById('editModal');
        if (modalEl) {
            let modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (!modalInstance) {
                 console.warn('Edit modal instance not found, creating new one.');
                 modalInstance = new bootstrap.Modal(modalEl);
            }
            modalInstance.show();
            console.log('-- Called editModal.show() for student:', studentId);
        } else {
            console.error('Edit modal element not found.');
        }
    }

    // Open the student pictures modal
    async function openPicturesModal(studentId, studentName) {
        console.log('Calling openPicturesModal for student:', studentId);
        console.log('Opening pictures modal for student:', studentId);
        state.currentStudentId = studentId;

        const modalEl = document.getElementById('picturesModal');
        if (!modalEl) {
            console.error('Pictures modal element not found.');
            return;
        }

        let modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (!modalInstance) {
            console.warn('Pictures modal instance not found, creating new one.');
            modalInstance = new bootstrap.Modal(modalEl);
        }

        const studentNameDisplay = document.getElementById('student-name-display');
        if (studentNameDisplay) {
            studentNameDisplay.textContent = studentName;
        }

        const studentIdForImageInput = document.getElementById('student-id-for-image');
        if (studentIdForImageInput) {
            studentIdForImageInput.value = studentId;
        }

        const studentImageForm = document.getElementById('student-image-form');
        if (studentImageForm) {
            studentImageForm.reset();
        }

        try {
            const response = await fetch(`/instructors/api/student-images/${studentId}`);
            const data = await response.json();

            const container = document.getElementById('current-pictures-container');
            if (!container) {
                console.error('Image container not found');
                return;
            }

            container.innerHTML = '';

            if (data.success && Array.isArray(data.images)) {
                if (data.images.length === 0) {
                    container.innerHTML = `
                        <div class="picture-container picture-placeholder">
                            <i class="fas fa-camera fa-2x mb-2"></i>
                            <span>No images yet</span>
                        </div>
                    `;
                } else {
                    data.images.forEach(image => {
                        if (image.path) {
                            const imgContainer = document.createElement('div');
                            imgContainer.className = 'picture-container';
                            imgContainer.innerHTML = `
                                <img src="${image.path}" alt="Student" class="student-image">
                                <button type="button" class="btn btn-sm btn-danger delete-image-btn" data-image-id="${image.id}">
                                    <i class="fas fa-times"></i>
                                </button>
                            `;

                            const deleteBtn = imgContainer.querySelector('.delete-image-btn');
                            deleteBtn.addEventListener('click', () => deleteStudentImage(image.id));

                            container.appendChild(imgContainer);
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Error loading student images:', error);
            const container = document.getElementById('current-pictures-container');
            if (container) {
                container.innerHTML = `
                    <div class="text-center text-danger">
                        Error loading images. Please try again later.
                    </div>
                `;
            }
        }

        // Show the modal using the Bootstrap instance
        modalInstance.show();
        console.log('-- Called picturesModal.show() for student:', studentId);
    }

    // Delete a student image
    async function deleteStudentImage(imageId) {
        try {
            const response = await fetch(`/instructors/api/delete-student-image/${imageId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                const student = state.students.find(s => s.id === state.currentStudentId);
                if (student) {
                    await openPicturesModal(state.currentStudentId, `${student.firstName} ${student.lastName}`);
                }
                showAlert('Image deleted successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to delete image', 'danger');
            }
        } catch (error) {
            console.error('Error deleting image:', error);
            showAlert('An error occurred while deleting the image', 'danger');
        }
    }

    // Capture student face function
    function captureStudentFace(studentId, studentName) {
        // Find student data
        const student = state.students.find(s => s.id === studentId);
        if (!student) {
            alert('Student not found');
            return;
        }
        
        // Open camera modal for face capture
        openCameraModal(studentId, studentName);
    }

    // View student photos function
    async function viewStudentPhotos(studentId, studentName) {
        // Find student data
        const student = state.students.find(s => s.id === studentId);
        if (!student) {
            alert('Student not found');
            return;
        }

        console.log('Viewing photos for student:', studentId);

        const modalEl = document.getElementById('viewPhotosModal');
        if (!modalEl) {
            console.error('View photos modal element not found.');
            return;
        }

        let modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (!modalInstance) {
            modalInstance = new bootstrap.Modal(modalEl);
        }

        const studentNameDisplay = document.getElementById('view-student-name-display');
        if (studentNameDisplay) {
            studentNameDisplay.textContent = studentName;
        }

        // Load and display student photos
        try {
            console.log('Fetching photos for student:', studentId);
            const response = await fetch(`/instructors/api/student-images/${studentId}`);
            console.log('API response status:', response.status);
            
            if (!response.ok) {
                console.error('API response not ok:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('Error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('API response data:', data);

            const container = document.getElementById('view-photos-container');
            if (!container) {
                console.error('Photos container not found');
                return;
            }

            container.innerHTML = '';

            if (data.success && Array.isArray(data.images)) {
                console.log('Found', data.images.length, 'images');
                if (data.images.length === 0) {
                    container.innerHTML = `
                        <div class="text-center text-muted py-4">
                            <i class="fas fa-camera fa-3x mb-3"></i>
                            <p>No photos uploaded yet</p>
                            <small>Click "Capture" to add facial recognition photos</small>
                        </div>
                    `;
                } else {
                    const photosGrid = document.createElement('div');
                    photosGrid.className = 'row g-3';

                    data.images.forEach(image => {
                        console.log('Processing image:', image);
                        if (image.path) {
                            console.log('Image path:', image.path);
                            const colDiv = document.createElement('div');
                            colDiv.className = 'col-md-4 col-sm-6';

                            colDiv.innerHTML = `
                                <div class="photo-card position-relative">
                                    <img src="${image.path}" alt="Student photo" class="img-fluid rounded" onerror="console.error('Failed to load image:', '${image.path}')">
                                    <button type="button" class="btn btn-danger btn-sm delete-photo-btn position-absolute" 
                                            data-image-id="${image.id}" title="Delete photo">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </div>
                            `;

                            // Add delete functionality
                            const deleteBtn = colDiv.querySelector('.delete-photo-btn');
                            deleteBtn.addEventListener('click', () => deleteStudentPhoto(image.id, studentId));

                            photosGrid.appendChild(colDiv);
                        } else {
                            console.warn('Image missing path:', image);
                        }
                    });

                    container.appendChild(photosGrid);
                }
            } else {
                container.innerHTML = `
                    <div class="text-center text-danger">
                        Error loading photos. Please try again later.
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading student photos:', error);
            const container = document.getElementById('view-photos-container');
            if (container) {
                container.innerHTML = `
                    <div class="text-center text-danger">
                        Error loading photos. Please try again later.
                    </div>
                `;
            }
        }

        modalInstance.show();
    }

    // Delete student photo from view modal
    async function deleteStudentPhoto(imageId, studentId) {
        try {
            const response = await fetch(`/instructors/api/delete-student-image/${imageId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                showAlert('Photo deleted successfully', 'success');

                // Update face status based on remaining images
                const hasImages = data.remaining_images > 0;
                const student = state.students.find(s => s.id === studentId);
                if (student && student.hasFaceImages && !hasImages) {
                    student.hasFaceImages = false;
                    renderStudentsTable(state.filteredStudents);
                }

                // Refresh the photos display
                const student2 = state.students.find(s => s.id === studentId);
                if (student2) {
                    await viewStudentPhotos(studentId, `${student2.firstName} ${student2.lastName}`);
                }

            } else {
                showAlert(data.message || 'Failed to delete photo', 'danger');
            }
        } catch (error) {
            console.error('Error deleting photo:', error);
            showAlert('An error occurred while deleting the photo', 'danger');
        }
    }

    // Open camera modal for face capture
    async function openCameraModal(studentId, studentName) {
        console.log('Opening camera modal for student:', studentId);

        if (window.cameraInUse) {
            showAlert('Camera is already in use. Please close the current camera session first.', 'warning');
            return;
        }

        const modalEl = document.getElementById('cameraModal');
        if (!modalEl) {
            console.error('Camera modal element not found.');
            return;
        }

        let modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (!modalInstance) {
            modalInstance = new bootstrap.Modal(modalEl);
        }

        window.cameraInUse = true;

        const studentNameDisplay = document.getElementById('camera-student-name-display');
        if (studentNameDisplay) {
            studentNameDisplay.textContent = studentName;
        }

        const studentIdInput = document.getElementById('camera-student-id');
        if (studentIdInput) {
            studentIdInput.value = studentId;
        }

        // Initialize captured photos array
        window.capturedPhotos = [];

        // Reset modal state
        document.getElementById('captured-photos-container').style.display = 'none';
        document.getElementById('captured-photos-grid').innerHTML = '';
        document.getElementById('upload-all-btn').style.display = 'none';
        document.getElementById('photo-count').textContent = '0';

        // Start camera
        try {
            let constraints = {
                video: { facingMode: 'user' },
                audio: false
            };
            
            let stream = await navigator.mediaDevices.getUserMedia(constraints);

            const video = document.getElementById('camera-video');
            video.srcObject = stream;

            // Ensure camera is stopped on page unload
            window.addEventListener('beforeunload', () => {
                if (video.srcObject) {
                    video.srcObject.getTracks().forEach(track => track.stop());
                }
            });

            // Set up capture button
            document.getElementById('capture-btn').onclick = () => capturePhoto();
            document.getElementById('upload-all-btn').onclick = () => uploadAllPhotos();

            // Stop camera when modal closes
            modalEl.addEventListener('hidden.bs.modal', () => {
                stream.getTracks().forEach(track => track.stop());
                window.cameraInUse = false;
            });

        } catch (error) {
            console.error('Error accessing camera:', error);
            let message = 'Unable to access camera.';
            if (error.name === 'NotAllowedError') {
                message += ' Please check permissions.';
            } else if (error.name === 'NotFoundError') {
                message += ' No camera found.';
            } else if (error.name === 'NotReadableError') {
                // Try with back camera or without facing mode
                try {
                    let fallbackConstraints = {
                        video: { facingMode: 'environment' },
                        audio: false
                    };
                    let stream = await navigator.mediaDevices.getUserMedia(fallbackConstraints);
                    
                    const video = document.getElementById('camera-video');
                    video.srcObject = stream;

                    // Ensure camera is stopped on page unload
                    window.addEventListener('beforeunload', () => {
                        if (video.srcObject) {
                            video.srcObject.getTracks().forEach(track => track.stop());
                        }
                    });

                    // Set up capture button
                    document.getElementById('capture-btn').onclick = () => capturePhoto();
                    document.getElementById('upload-all-btn').onclick = () => uploadAllPhotos();

                    // Stop camera when modal closes
                    modalEl.addEventListener('hidden.bs.modal', () => {
                        stream.getTracks().forEach(track => track.stop());
                        window.cameraInUse = false;
                    });
                    
                    // Successfully opened with back camera, show modal
                    modalInstance.show();
                    return;
                } catch (fallbackError) {
                    console.error('Back camera failed, trying without facing mode:', fallbackError);
                    try {
                        let basicConstraints = {
                            video: true,
                            audio: false
                        };
                        let stream = await navigator.mediaDevices.getUserMedia(basicConstraints);
                        
                        const video = document.getElementById('camera-video');
                        video.srcObject = stream;

                        // Ensure camera is stopped on page unload
                        window.addEventListener('beforeunload', () => {
                            if (video.srcObject) {
                                video.srcObject.getTracks().forEach(track => track.stop());
                            }
                        });

                        // Set up capture button
                        document.getElementById('capture-btn').onclick = () => capturePhoto();
                        document.getElementById('upload-all-btn').onclick = () => uploadAllPhotos();

                        // Stop camera when modal closes
                        modalEl.addEventListener('hidden.bs.modal', () => {
                            stream.getTracks().forEach(track => track.stop());
                            window.cameraInUse = false;
                        });
                        
                        // Successfully opened with basic constraints, show modal
                        modalInstance.show();
                        return;
                    } catch (basicError) {
                        console.error('Basic camera access failed:', basicError);
                        message += ' Your camera is not functioning or not available in this browser.';
                    }
                }
            } else if (error.name === 'OverconstrainedError') {
                message += ' Camera constraints not supported.';
            } else {
                message += ' Please check your camera settings.';
            }
            showAlert(message, 'danger');
            window.cameraInUse = false;
            return;
        }

        modalInstance.show();
    }

    // Capture photo function
    function capturePhoto() {
        const video = document.getElementById('camera-video');
        const canvas = document.getElementById('camera-canvas');
        const ctx = canvas.getContext('2d');

        // Set canvas size to video size
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        // Draw video frame to canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Convert to blob and store
        canvas.toBlob((blob) => {
            const photoData = {
                blob: blob,
                dataUrl: canvas.toDataURL('image/jpeg', 0.9),
                timestamp: Date.now()
            };

            window.capturedPhotos.push(photoData);
            updatePhotoDisplay();
        }, 'image/jpeg', 0.9);
    }

    // Update photo display function
    function updatePhotoDisplay() {
        const container = document.getElementById('captured-photos-container');
        const grid = document.getElementById('captured-photos-grid');
        const count = document.getElementById('photo-count');

        if (window.capturedPhotos.length > 0) {
            container.style.display = 'block';
            document.getElementById('upload-all-btn').style.display = 'inline-block';
        } else {
            container.style.display = 'none';
            document.getElementById('upload-all-btn').style.display = 'none';
        }

        count.textContent = window.capturedPhotos.length;

        // Clear existing thumbnails
        grid.innerHTML = '';

        // Add thumbnails
        window.capturedPhotos.forEach((photo, index) => {
            const thumbnailDiv = document.createElement('div');
            thumbnailDiv.className = 'photo-thumbnail position-relative';
            thumbnailDiv.innerHTML = `
                <img src="${photo.dataUrl}" alt="Captured photo ${index + 1}" class="thumbnail-img">
                <button type="button" class="btn btn-sm btn-danger delete-photo-btn" data-index="${index}" title="Delete photo">
                    <i class="fas fa-times"></i>
                </button>
            `;

            // Add delete functionality
            const deleteBtn = thumbnailDiv.querySelector('.delete-photo-btn');
            deleteBtn.addEventListener('click', () => deletePhoto(index));

            grid.appendChild(thumbnailDiv);
        });
    }

    // Delete photo function
    function deletePhoto(index) {
        window.capturedPhotos.splice(index, 1);
        updatePhotoDisplay();
    }

    // Upload all photos function
    async function uploadAllPhotos() {
        const studentId = document.getElementById('camera-student-id').value;

        if (window.capturedPhotos.length === 0) {
            showAlert('No photos to upload', 'warning');
            return;
        }

        // Show loading state
        const uploadButton = document.getElementById('upload-all-btn');
        const originalText = uploadButton.innerHTML;
        uploadButton.disabled = true;
        uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading...';

        const formData = new FormData();
        formData.append('student_id', studentId);

        // Add all captured photos
        window.capturedPhotos.forEach((photo, index) => {
            formData.append('images', photo.blob, `capture_${index + 1}_${photo.timestamp}.jpg`);
        });

        try {
            console.log(`Uploading ${window.capturedPhotos.length} photos for student:`, studentId);

            const response = await fetch('/students/api/upload-images', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Server response:', result);

            if (result.success) {
                showAlert(`${window.capturedPhotos.length} photos uploaded successfully!`, 'success');

                // Update face status
                const student = state.students.find(s => s.id === studentId);
                if (student) {
                    student.hasFaceImages = true;
                    renderStudentsTable(state.filteredStudents);
                }

                // Close modal
                const modalInstance = bootstrap.Modal.getInstance(document.getElementById('cameraModal'));
                if (modalInstance) modalInstance.hide();

            } else {
                throw new Error(result.message || 'Error uploading photos');
            }
        } catch (error) {
            console.error('Error uploading photos:', error);
            showAlert(error.message || 'Error uploading photos. Please try again.', 'danger');
        } finally {
            // Reset button state
            uploadButton.disabled = false;
            uploadButton.innerHTML = originalText;
        }
    }

    // Open delete confirmation modal
    function openDeleteConfirmation(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (!student) return;
        state.currentStudentId = studentId;
        const confirmationText = document.getElementById('confirmationText');
        if (confirmationText) {
            confirmationText.textContent = `Are you sure you want to delete ${student.firstName} ${student.lastName}?`;
        }

        const modalEl = document.getElementById('confirmationModal');
        if (modalEl) {
            let modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (!modalInstance) {
                 console.warn('Confirmation modal instance not found, creating new one.');
                 modalInstance = new bootstrap.Modal(modalEl);
            }
            modalInstance.show();
             console.log('-- Called confirmationModal.show() for student:', studentId);
        } else {
            console.error('Confirmation modal element not found.');
        }
    }

    // Confirm delete student
    async function confirmDeleteStudent() {
        if (!state.currentStudentId) return;
        
        try {
            const response = await fetch(`/instructors/api/delete-student/${state.currentStudentId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Remove from the state
                state.students = state.students.filter(s => s.id !== state.currentStudentId);
                state.filteredStudents = state.filteredStudents.filter(s => s.id !== state.currentStudentId);
                
                // Update the UI and counter
                renderStudentsTable(state.filteredStudents);
                updateStudentCounter();
                
                showAlert('Student deleted successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to delete student', 'danger');
            }
            
            hideModal(elements.confirmationModal);
            state.currentStudentId = null;
            
        } catch (error) {
            console.error('Error deleting student:', error);
            showAlert('An error occurred while deleting the student', 'danger');
            hideModal(elements.confirmationModal);
        }
    }

    // Handle enroll form submission
    async function handleEnrollSubmit(e) {
        console.log('Enroll form submit event triggered.');

        const formData = new FormData(e.target);
        
        const firstName = (formData.get('firstName') || '').trim();
        const middleName = (formData.get('middleName') || '').trim();
        const lastName = (formData.get('lastName') || '').trim();
        const yearLevelValue = formData.get('yearLevel');
        const yearLevel = mapYearToBackendFormat(yearLevelValue);
        const department = formData.get('department') || DEFAULT_DEPARTMENT;
        const studentIdValue = (formData.get('studentId') || '').trim();

        if (!firstName || !lastName) {
            showAlert('First name and last name are required.', 'warning');
            return;
        }

        if (!studentIdValue) {
            showAlert('Please enter a Student ID.', 'warning');
            return;
        }
        
        const studentData = {
            firstName,
            middleName: middleName || null,
            lastName,
            id: studentIdValue,
            yearLevel,
            department
        };
        
        console.log('Submitting student data:', studentData);
        
        try {
            const response = await fetch('/students/api/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(studentData)
            });
            
            const result = await response.json();
            console.log('Server response:', result);
            
            if (result.success) {
                // Reset form and close modal
                e.target.reset();
                if (typeof enrollModal !== 'undefined' && enrollModal) {
                    enrollModal.hide();
                }
                
                // Add the new student to the state
                const newStudent = {
                    ...result.student,
                    department: (result.student && result.student.department) || department
                };
                state.students.push(newStudent);
                state.filteredStudents = [...state.students];
                
                // Update UI with the latest data
                renderStudentsTable(state.filteredStudents);
                updateStudentCounter();
                
                // Show success message
                showAlert('Student enrolled successfully', 'success');
            } else {
                throw new Error(result.message || 'Failed to enroll student');
            }
        } catch (error) {
            console.error('Error enrolling student:', error);
            showAlert(error.message || 'Error enrolling student. Please try again.', 'danger');
        }
    }

    // Handle edit student form submission
    async function handleEditStudent(e) {
        e.preventDefault();
        
        if (!state.currentStudentId) return;
        
        const form = e.target;
        const formData = new FormData(form);
        const firstName = (formData.get('firstName') || '').trim();
        const middleName = (formData.get('middleName') || '').trim();
        const lastName = (formData.get('lastName') || '').trim();
        const yearLevelValue = formData.get('yearLevel');
        const yearLevel = mapYearToBackendFormat(yearLevelValue);
        const department = formData.get('department') || DEFAULT_DEPARTMENT;
        
        if (!firstName || !lastName) {
            showAlert('First name and last name are required.', 'warning');
            return;
        }
        
        const updatedStudent = {
            firstName,
            middleName: middleName || null,
            lastName,
            yearLevel,
            department
        };
        
        try {
            const response = await fetch(`/instructors/api/update-student/${state.currentStudentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedStudent)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update in state
                const index = state.students.findIndex(s => s.id === state.currentStudentId);
                if (index !== -1) {
                    state.students[index] = {
                        ...state.students[index],
                        ...updatedStudent
                    };
                }
                
                const filteredIndex = state.filteredStudents.findIndex(s => s.id === state.currentStudentId);
                if (filteredIndex !== -1) {
                    state.filteredStudents[filteredIndex] = {
                        ...state.filteredStudents[filteredIndex],
                        ...updatedStudent
                    };
                }
                
                // Update UI
                renderStudentsTable(state.filteredStudents);
                
                // FIXED: Update counter after editing (in case student count changed somehow)
                updateStudentCounter();
                
                // Close modal
                hideModal(elements.editModal);
                state.currentStudentId = null;
                
                showAlert('Student updated successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to update student', 'danger');
            }
            
        } catch (error) {
            console.error('Error updating student:', error);
            showAlert('An error occurred while updating the student', 'danger');
        }
    }

    // Handle image upload
    async function handleImageUpload(e) {
        e.preventDefault();
        
        // Prevent duplicate uploads
        if (elements.uploadButton.disabled) {
            return;
        }
        
        const studentId = document.getElementById('student-id-for-image').value;
        const imageFiles = document.getElementById('student-image-upload').files;
        
        if (!studentId || imageFiles.length === 0) {
            showAlert('Please select at least one image to upload', 'warning');
            return;
        }

        // Validate file types and sizes
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png'];
        const maxSize = 5 * 1024 * 1024; // 5MB in bytes
        
        for (let file of imageFiles) {
            if (!allowedTypes.includes(file.type)) {
                showAlert(`Invalid file type for ${file.name}. Please upload JPG, JPEG, or PNG files.`, 'warning');
                return;
            }
            if (file.size > maxSize) {
                showAlert(`File ${file.name} is too large. Maximum size is 5MB.`, 'warning');
                return;
            }
        }
        
        // Show loading state
        elements.uploadButton.disabled = true;
        elements.uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading...';
        
        const formData = new FormData();
        formData.append('student_id', studentId);
        for (let file of imageFiles) {
            formData.append('images', file);
        }
        
        try {
            console.log('Uploading images for student:', studentId);
            console.log('Files to upload:', Array.from(imageFiles).map(f => ({
                name: f.name,
                type: f.type,
                size: f.size
            })));
            
            const response = await fetch('/students/api/upload-images', {
                method: 'POST',
                body: formData
            });
            
            console.log('Server response status:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Server response:', result);
            
            if (result.success) {
                // Show success message
                showAlert(result.message, 'success');
                
                // Reset the form
                elements.studentImageForm.reset();
                
                // Reload the images
                const student = state.students.find(s => s.id === studentId);
                if (student) {
                    await openPicturesModal(studentId, `${student.firstName} ${student.lastName}`);
                }
            } else {
                throw new Error(result.message || 'Error uploading images');
            }
        } catch (error) {
            console.error('Error uploading images:', error);
            showAlert(error.message || 'Error uploading images. Please try again.', 'danger');
        } finally {
            // Reset button state
            elements.uploadButton.disabled = false;
            elements.uploadButton.innerHTML = '<i class="fas fa-upload me-2"></i>Upload Images';
        }
    }

    // Debounce function to limit search frequency
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Handle search with improved functionality
    function handleSearch() {
        const searchTerm = elements.searchInput.value.toLowerCase().trim();
        const clearSearchBtn = document.getElementById('clearSearch');
        
        // Show/hide clear button
        if (clearSearchBtn) {
            clearSearchBtn.style.display = searchTerm ? 'flex' : 'none';
        }
        
        // Filter students based on search term and year level
        state.filteredStudents = state.students.filter(student => {
            const matchesSearch = 
                student.firstName.toLowerCase().includes(searchTerm) ||
                student.lastName.toLowerCase().includes(searchTerm) ||
                student.id.toLowerCase().includes(searchTerm) ||
                student.yearLevel.toLowerCase().includes(searchTerm) ||
                mapYearValueToLabel(student.yearLevel).toLowerCase().includes(searchTerm);
                
            const studentYearLevelDisplay = mapYearValueToLabel(student.yearLevel);
            const matchesYearLevel = !state.currentYearLevelFilter || 
                studentYearLevelDisplay === state.currentYearLevelFilter ||
                student.yearLevel === state.currentYearLevelFilter;
                
            return matchesSearch && matchesYearLevel;
        });
        
        // Sort filtered students
        if (state.sortOrder) {
            const yearLevelOrder = {
                '1st Year': 1,
                '2nd Year': 2,
                '3rd Year': 3,
                '4th Year': 4,
                '1': 1,
                '2': 2,
                '3': 3,
                '4': 4
            };
            
            state.filteredStudents.sort((a, b) => {
                const yearA = yearLevelOrder[a.yearLevel] || yearLevelOrder[mapYearValueToLabel(a.yearLevel)] || 0;
                const yearB = yearLevelOrder[b.yearLevel] || yearLevelOrder[mapYearValueToLabel(b.yearLevel)] || 0;
                return state.sortOrder === 'asc' ? yearA - yearB : yearB - yearA;
            });
        }
        
        // Update UI
        renderStudentsTable(state.filteredStudents);
        
        // Update counter with filtered count
        updateStudentCounter(state.filteredStudents.length);
        
        // Show no results message if needed
            if (state.filteredStudents.length === 0) {
            const noResultsMessage = searchTerm || state.currentYearLevelFilter ? 
                'No students found matching your search criteria' : 
                'No students found';
            elements.studentsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center">
                        <div class="no-results">
                            <i class="fas fa-search fa-2x mb-2"></i>
                            <p>${noResultsMessage}</p>
                        </div>
                    </td>
                </tr>
            `;
        }
    }

    // Update student counter to show filtered count
    function updateStudentCounter(count = null) {
        if (state.isUpdatingCounter) return; // Prevent infinite loops
        
        state.isUpdatingCounter = true;
        
        try {
            const counterElement = document.getElementById('studentCountBadge');
            if (counterElement) {
                const displayCount = count !== null ? count : state.filteredStudents.length;
                counterElement.textContent = displayCount;
                console.log(`Student counter updated to: ${displayCount}`);
            } else {
                console.warn('Student count badge element not found');
            }
        } catch (error) {
            console.error('Error updating student counter:', error);
        } finally {
            state.isUpdatingCounter = false;
        }
    }


    // Show modal
    function showModal(modal) {
        if (!modal) return;
        let modalInstance = bootstrap.Modal.getInstance(modal);
        if (!modalInstance) {
            modalInstance = new bootstrap.Modal(modal);
        }
        modalInstance.show();
    }

    // Hide modal
    function hideModal(modal) {
        if (!modal) return;
        let modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) {
            modalInstance.hide();
        }
    }

    // Show alert message using floating notifications
    function showAlert(message, type = 'info') {
        // Map the types to the floating notification functions
        if (type === 'success') {
            window.showSuccessNotification(message);
        } else if (type === 'danger' || type === 'error') {
            window.showErrorNotification(message);
        } else if (type === 'warning') {
            window.showWarningNotification(message);
        } else {
            window.showInfoNotification(message);
        }
    }

    function parseFullName(fullName) {
        if (!fullName) {
            return { firstName: '', lastName: '' };
        }

        const parts = fullName.split(',');
        if (parts.length === 1) {
            const tokens = fullName.trim().split(/\s+/);
            const lastName = tokens.shift() || '';
            const remaining = tokens.join(' ');
            return {
                firstName: remaining || lastName,
                lastName: lastName || ''
            };
        }

        const lastName = parts[0].trim();
        const firstName = parts.slice(1).join(',').trim();
        return {
            firstName,
            lastName
        };
    }

    function composeFullName(lastName, firstName) {
        const safeLast = lastName || '';
        const safeFirst = firstName || '';

        if (!safeLast && !safeFirst) {
            return '';
        }
        if (!safeLast) {
            return safeFirst;
        }
        if (!safeFirst) {
            return safeLast;
        }
        return `${safeLast}, ${safeFirst}`;
    }

    function mapYearValueToLabel(value) {
        if (!value) {
            return '';
        }
        // Convert backend format to display format
        if (YEAR_LEVEL_FROM_BACKEND[value]) {
            return YEAR_LEVEL_FROM_BACKEND[value];
        }
        return YEAR_LEVEL_LABELS[value] || value;
    }

    function mapYearLabelToValue(label) {
        if (!label) {
            return '';
        }
        return YEAR_LEVEL_VALUES[label] || '';
    }
    
    function mapYearToBackendFormat(value) {
        if (!value) {
            return '';
        }
        // Convert display format to backend format
        return YEAR_LEVEL_TO_BACKEND[value] || value;
    }

    // Make functions available globally
    window.openPicturesModal = function(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (student) {
            state.currentStudentId = studentId;
            openPicturesModal(studentId, `${student.firstName} ${student.lastName}`);
        }
    };

    window.editStudent = function(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (student) {
            state.currentStudentId = studentId;
            openEditModal(studentId);
        }
    };

    window.deleteStudent = function(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (student) {
            state.currentStudentId = studentId;
            openDeleteConfirmation(studentId);
        }
    };

    // Export students to XLSX
    async function handleExportStudents() {
        try {
            const response = await fetch('/students/api/export');
            
            if (!response.ok) {
                throw new Error('Export failed');
            }
            
            // Get the filename from the response headers
            const disposition = response.headers.get('Content-Disposition');
            let filename = 'students_export.xlsx';
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
            
            showToast('Students exported successfully', 'success');
        } catch (error) {
            console.error('Export error:', error);
            showToast('Failed to export students', 'error');
        }
    }

    // Import students from CSV
    async function handleImportStudents(event) {
        const file = event.target.files[0];
        if (!file) return;
        event.target.value = '';
        const fname = file.name.toLowerCase();
        const allowedExts = ['.csv', '.xlsx', '.xls'];
        if (!allowedExts.some(ext => fname.endsWith(ext))) {
            showToast('Invalid file type. Please select a CSV or Excel file (.csv, .xlsx, .xls).', 'danger');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch('/students/api/import', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                if (data.errors && data.errors.length > 0) {
                    // Show import conflict modal instead of alert/toast
                    showImportConflictModal(data.errors, file);
                } else {
                    await fetchStudents();
                    showToast('Students imported successfully.', 'success');
                }
            } else {
                showToast(data.message || 'Import failed.', 'danger');
            }
        } catch (error) {
            showToast('Import failed. Please try again.', 'danger');
        }
    }

    // Show import conflict modal
    function showImportConflictModal(errors, file) {
        const modalEl = document.getElementById('importConflictModal');
        const conflictList = document.getElementById('importConflictList');
        if (conflictList) {
            conflictList.innerHTML = '';
            errors.forEach(err => {
                const li = document.createElement('li');
                li.textContent = err;
                conflictList.appendChild(li);
            });
        }
        let modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
        modalInstance.show();
        // Button handlers
        document.getElementById('updateExistingBtn').onclick = async function() {
            modalInstance.hide();
            await importWithUpdateOption(file, true);
        };
        document.getElementById('addNewOnlyBtn').onclick = async function() {
            modalInstance.hide();
            await importWithUpdateOption(file, false);
        };
    }

    // Import with update option
    async function importWithUpdateOption(file, updateExisting) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch(`/students/api/import?update_existing=${updateExisting ? 'true' : 'false'}`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                await fetchStudents();
                showToast(updateExisting ? 'Students imported and updated.' : 'Only new students imported.', 'success');
            } else {
                showToast(data.message || 'Import failed.', 'danger');
            }
        } catch (error) {
            showToast('Import failed. Please try again.', 'danger');
        }
    }

    // Utility function to show toast notifications using floating notifications
    function showToast(message, type = 'info') {
        // Map the types to the floating notification functions
        if (type === 'success') {
            window.showSuccessNotification(message);
        } else if (type === 'danger' || type === 'error') {
            window.showErrorNotification(message);
        } else if (type === 'warning') {
            window.showWarningNotification(message);
        } else {
            window.showInfoNotification(message);
        }
    }

    // Start real-time updates for face status
    function startRealTimeUpdates() {
        setInterval(async () => {
            try {
                const response = await fetch('/students/api/list');
                if (!response.ok) return;
                const data = await response.json();
                if (!data.success) return;
                
                const updatedStudents = data.students.map(student => ({
                    ...student,
                    hasFaceImages: student.hasFaceImages || false
                }));
                
                // Check if face status changed
                let hasChanges = false;
                updatedStudents.forEach(updated => {
                    const existing = state.students.find(s => s.id === updated.id);
                    if (existing && existing.hasFaceImages !== updated.hasFaceImages) {
                        hasChanges = true;
                        existing.hasFaceImages = updated.hasFaceImages;
                    }
                });
                
                if (hasChanges) {
                    state.filteredStudents = [...state.students];
                    renderStudentsTable(state.filteredStudents);
                }
            } catch (error) {
                console.error('Error in real-time update:', error);
            }
        }, 5000); // Update every 5 seconds
    }

    // Make functions available globally
    window.fetchStudents = fetchStudents;
    window.init = init;
});
