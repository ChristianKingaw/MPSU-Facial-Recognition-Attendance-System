// Instructors Management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // DOM element references
    const elements = {
        searchInput: document.getElementById('searchInput'),
        clearSearchBtn: document.getElementById('clearSearch'),
        instructorCountBadge: document.getElementById('instructorCountBadge'),
        instructorsTableBody: document.querySelector('tbody'),
        btnAddInstructor: document.getElementById('btnAddInstructor')
    };

    // Application state
    const state = {
        instructors: [],
        filteredInstructors: []
    };

    // Initialize
    init();

    function init() {
        // Get initial instructors data from the page
        loadInstructorsFromPage();
        
        // Add event listeners
        addEventListeners();
        
        // Initialize display
        updateInstructorCount();
    }

    function loadInstructorsFromPage() {
        // Extract instructor data from existing table rows
        const rows = document.querySelectorAll('tbody tr');
        state.instructors = [];
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 6) { // Make sure it's not the "no instructors" row
                const instructor = {
                    id: cells[0].textContent.trim(),
                    name: cells[1].textContent.trim(),
                    username: cells[2].textContent.trim(),
                    email: cells[3].textContent.trim(),
                    department: cells[4].textContent.trim(),
                    classCount: cells[5].textContent.trim(),
                    row: row
                };
                state.instructors.push(instructor);
            }
        });
        
        state.filteredInstructors = [...state.instructors];
    }

    function addEventListeners() {
        // Search functionality
        if (elements.searchInput) {
            elements.searchInput.addEventListener('input', debounce(handleSearch, 300));
        }
        
        // Clear search
        if (elements.clearSearchBtn) {
            elements.clearSearchBtn.addEventListener('click', () => {
                elements.searchInput.value = '';
                elements.clearSearchBtn.style.display = 'none';
                handleSearch();
            });
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

    // Handle search with filtering
    function handleSearch() {
        const searchTerm = elements.searchInput.value.toLowerCase().trim();
        
        // Show/hide clear button
        if (elements.clearSearchBtn) {
            elements.clearSearchBtn.style.display = searchTerm ? 'flex' : 'none';
        }
        
        // Filter instructors based on search term and department
        state.filteredInstructors = state.instructors.filter(instructor => {
            const matchesSearch = 
                instructor.name.toLowerCase().includes(searchTerm) ||
                instructor.username.toLowerCase().includes(searchTerm) ||
                instructor.email.toLowerCase().includes(searchTerm) ||
                instructor.department.toLowerCase().includes(searchTerm);
                
            // Since we only have BSIT department, no need to filter by department
            // All instructors should show regardless of department filter
            return matchesSearch;
        });
        
        // Update display
        renderInstructorsTable();
        updateInstructorCount();
    }

    function renderInstructorsTable() {
        // Hide all instructor rows first
        state.instructors.forEach(instructor => {
            if (instructor.row) {
                instructor.row.style.display = 'none';
            }
        });
        
        // Show filtered instructors
        if (state.filteredInstructors.length > 0) {
            state.filteredInstructors.forEach(instructor => {
                if (instructor.row) {
                    instructor.row.style.display = '';
                }
            });
        } else {
            // Show no results message
            const searchTerm = elements.searchInput.value.trim();
            const noResultsMessage = searchTerm ? 
                'No instructors found matching your search criteria' : 
                'No instructors found';
            
            // Remove existing no-results row
            const existingNoResults = elements.instructorsTableBody.querySelector('.no-results-row');
            if (existingNoResults) {
                existingNoResults.remove();
            }
            
            // Add no results row
            const noResultsRow = document.createElement('tr');
            noResultsRow.className = 'no-results-row';
            noResultsRow.innerHTML = `
                <td colspan="7" class="text-center py-4">
                    <div class="no-results">
                        <i class="fas fa-search fa-2x mb-2"></i>
                        <p class="mb-0">${noResultsMessage}</p>
                    </div>
                </td>
            `;
            elements.instructorsTableBody.appendChild(noResultsRow);
        }
    }

    function updateInstructorCount() {
        if (elements.instructorCountBadge) {
            elements.instructorCountBadge.textContent = state.filteredInstructors.length;
        }
    }

    // Export Instructors functionality
    const exportBtn = document.getElementById('btnExportInstructors');
    if (exportBtn) {
        exportBtn.addEventListener('click', handleExportInstructors);
    }

    // Import Instructors functionality
    const importBtn = document.getElementById('btnImportInstructors');
    if (importBtn) {
        importBtn.addEventListener('click', function() {
            document.getElementById('importFileInput').click();
        });
    }

    // Handle file import
    const importFileInput = document.getElementById('importFileInput');
    if (importFileInput) {
        importFileInput.addEventListener('change', handleImportInstructors);
    }
});

// Export instructors to CSV
async function handleExportInstructors() {
    try {
        const response = await fetch('/instructors/export_csv');
        
        if (!response.ok) {
            throw new Error('Export failed');
        }
        
        // Get the filename from the response headers
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'instructors_export.csv';
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
        
        console.log('Instructors exported successfully');
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export instructors');
    }
}

// Import instructors from CSV
async function handleImportInstructors(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Reset the file input
    event.target.value = '';
    
    if (!file.name.toLowerCase().endsWith('.csv')) {
        alert('Please select a CSV file');
        return;
    }
    
    const formData = new FormData();
    formData.append('csvFile', file);
    formData.append('skipDuplicates', 'on'); // Default to skip duplicates
    
    try {
        const response = await fetch('/instructors/import_csv', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            console.log('Instructors imported successfully');
            // Reload the page to show updated instructor list
            window.location.reload();
        } else {
            throw new Error('Import failed');
        }
    } catch (error) {
        console.error('Import error:', error);
        alert('Failed to import instructors');
    }
}
