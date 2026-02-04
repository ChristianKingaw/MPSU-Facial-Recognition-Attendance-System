/**
 * Schedule Builder
 * Handles building and parsing class schedules
 * Integrates with the class form to handle the schedule field
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Set up the schedule builder if it exists on the page
    setupScheduleBuilder();
});

// Global variables to store schedule state
let timeSlots = [];
let selectedDays = new Set();
let timeSlotCounter = 0;

/**
 * Setup the schedule builder interface
 * @param {string} existingSchedule - Optional existing schedule to parse and display
 */
function setupScheduleBuilder(existingSchedule = null) {
    console.log('setupScheduleBuilder called.');
    console.log('Setting up schedule builder...');
    
    // DOM element references
    const dayButtons = document.querySelectorAll('.checkbox-btn');
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    const addTimeBtn = document.getElementById('addTimeBtn');
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const startTimeInput = document.getElementById('startTime');
    const endTimeInput = document.getElementById('endTime');
    const scheduleField = document.getElementById('schedule');
    
    // Reset state
    timeSlots = [];
    selectedDays = new Set();
    timeSlotCounter = 0;
    
    // If these elements don't exist, we're not on a page with the schedule builder
    if (!dayButtons.length || !resetDaysBtn || !addTimeBtn || !scheduleDisplay || 
        !startTimeInput || !endTimeInput || !scheduleField) {
        console.log('Schedule builder elements not found on this page');
        return;
    }
    
    // Set up event listeners for day buttons
    dayButtons.forEach(button => {
        const checkbox = button.querySelector('input.day-checkbox');
        if (checkbox) {
            // Use change event instead of click for better reliability
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation(); // Prevent event bubbling
                const day = checkbox.dataset.day;
                
                if (checkbox.checked) {
                    button.classList.add('active');
                    selectedDays.add(day);
                } else {
                    button.classList.remove('active');
                    selectedDays.delete(day);
                }
                
                console.log('Selected days:', Array.from(selectedDays));
            });
            
            // Prevent the label click from interfering
            button.addEventListener('click', (e) => {
                if (e.target === button) {
                    e.preventDefault();
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            });
        }
    });
    
    // Reset days button
    resetDaysBtn.addEventListener('click', () => {
        dayButtons.forEach(btn => {
            const checkbox = btn.querySelector('input.day-checkbox');
            if (checkbox) {
                checkbox.checked = false;
            btn.classList.remove('active');
            }
        });
        selectedDays.clear();
        console.log('Days reset');
    });
    
    // Add time slot button
    // Prevent attaching multiple listeners
    if (!addTimeBtn.dataset.listenerAttached) {
        addTimeBtn.dataset.listenerAttached = 'true';
        addTimeBtn.addEventListener('click', () => {
            const startTime = startTimeInput.value.trim(); // Trim whitespace
            const endTime = endTimeInput.value.trim(); // Trim whitespace

            // Validation
            if (startTime === '' || endTime === '') {
                console.error('Validation failed: startTime=', startTime, '(' + typeof startTime + ')', 'endTime=', endTime, '(' + typeof endTime + ')');
                window.showWarningNotification('Please select both start and end times.');
                return;
            }

            if (selectedDays.size === 0) {
                window.showWarningNotification('Please select at least one day.');
                return;
            }
            
            // Convert times to minutes for proper comparison
            const [startHours, startMinutes] = startTime.split(':').map(Number);
            const [endHours, endMinutes] = endTime.split(':').map(Number);
            
            const startTotalMinutes = startHours * 60 + startMinutes;
            const endTotalMinutes = endHours * 60 + endMinutes;
            
            // Allow overnight slots (end time less than start time)
            const isOvernight = endTotalMinutes < startTotalMinutes;
            
            // If it's not overnight and end time is not after start time
            if (!isOvernight && endTotalMinutes <= startTotalMinutes) {
                window.showWarningNotification('End time must be after start time.');
                return;
            }

            // Add the time slot
            addTimeSlot({
                id: `slot_${timeSlotCounter++}`,
                days: Array.from(selectedDays),
                startTime: startTime,
                endTime: endTime,
                isOvernight: isOvernight
            });

            // Reset inputs
            startTimeInput.value = '';
            endTimeInput.value = '';
            dayButtons.forEach(btn => {
                const checkbox = btn.querySelector('input.day-checkbox');
                if (checkbox) {
                    checkbox.checked = false;
                    btn.classList.remove('active');
                }
            });
            selectedDays.clear();
        });
    }
    
    // Parse existing schedule if provided
    if (existingSchedule) {
        parseExistingSchedule(existingSchedule);
    } else {
        updateScheduleDisplay();
    }
}

/**
 * Add a time slot to the schedule
 * @param {Object} slot - Time slot with days, start time, and end time
 */
function addTimeSlot(slot) {
    timeSlots.push(slot);
    updateScheduleDisplay();
}

/**
 * Remove a time slot from the schedule
 * @param {string} slotId - The ID of the slot to remove
 */
function removeTimeSlot(slotId) {
    timeSlots = timeSlots.filter(slot => slot.id !== slotId);
    updateScheduleDisplay();
}

/**
 * Format a time string for display (12-hour format with AM/PM)
 * @param {string} timeString - Time in HH:MM format (24-hour)
 * @returns {string} Formatted time (12-hour format with AM/PM) for UI display
 */
function formatTimeForDisplay(timeString) {
    if (!timeString) return '';
    
    // Convert 24 hour time to 12 hour format with AM/PM
    const [hours, minutes] = timeString.split(':');
    const hour = parseInt(hours, 10);
    const suffix = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    
    return `${displayHour}:${minutes} ${suffix}`;
}

/**
 * Format a time string for storage (24-hour format)
 * @param {string} timeString - Time in HH:MM format
 * @returns {string} Formatted time (12-hour format with AM/PM) for the schedule string
 */
function formatTimeForSchedule(timeString) {
    if (!timeString) return '';
    
    // Convert 24 hour time to 12 hour format with AM/PM
    const [hours, minutes] = timeString.split(':');
    const hour = parseInt(hours, 10);
    const suffix = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    
    return `${displayHour}:${minutes} ${suffix}`;
}

/**
 * Update the schedule display in the UI
 */
function updateScheduleDisplay() {
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleField = document.getElementById('schedule');
    
    if (!scheduleDisplay || !scheduleField) {
        console.error('Schedule display or hidden schedule field not found.'); // Added error log
        return;
    }
    
    console.log('Current timeSlots:', timeSlots); // Log current time slots
    
    if (timeSlots.length === 0) {
        console.log('No time slots, clearing schedule field'); // Log when clearing
        scheduleDisplay.innerHTML = '<span class="text-muted">No time slots added</span>';
        scheduleField.value = '';
        return;
    }
    
    // Create the schedule display
    scheduleDisplay.innerHTML = '';
    
    timeSlots.forEach(slot => {
        const slotElement = document.createElement('div');
        slotElement.className = 'schedule-slot';
        slotElement.innerHTML = `
            <span class="days">${slot.days.join(', ')}</span>
            <span class="time">${formatTimeForDisplay(slot.startTime)} - ${formatTimeForDisplay(slot.endTime)}</span>
            <button type="button" class="btn-remove-slot" data-slot-id="${slot.id}">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        scheduleDisplay.appendChild(slotElement);
        
        // Add event listener for remove button
        const removeButton = slotElement.querySelector('.btn-remove-slot');
        removeButton.addEventListener('click', () => {
            removeTimeSlot(slot.id);
        });
    });
    
    // Update the hidden input field with formatted schedule
    const formattedSchedule = formatSchedule(); // Get the formatted schedule
    console.log('Formatted schedule:', formattedSchedule); // Log formatted schedule
    scheduleField.value = formattedSchedule; // Set the value
    console.log('Schedule display updated. Hidden schedule field value:', scheduleField.value); // Updated log
}

/**
 * Format the schedule for storage in the hidden input field
 * @returns {string} Formatted schedule string (e.g., 'MWF 10:00 AM-12:00 PM, TTH 1:00 PM-2:30 PM')
 */
function formatSchedule() {
    if (timeSlots.length === 0) return '';
    
    // Define the standard order of days for consistent formatting
    const dayOrder = { 'M': 0, 'T': 1, 'W': 2, 'Th': 3, 'F': 4, 'S': 5, 'Su': 6 };
    
    // Format each time slot and join with commas
    return timeSlots.map(slot => {
        // Sort days according to standard order
        const sortedDays = slot.days.sort((a, b) => dayOrder[a] - dayOrder[b]);
        const days = sortedDays.join('');
        
        // Format times using formatTimeForSchedule
        const startTimeFormatted = formatTimeForSchedule(slot.startTime);
        const endTimeFormatted = formatTimeForSchedule(slot.endTime);
        
        return `${days} ${startTimeFormatted}-${endTimeFormatted}`;
    }).join(', ');
}

/**
 * Parse an existing schedule string and set up the UI
 * @param {string} scheduleString - Schedule in the format 'M 9:00 AM-10:30 AM, W 1:00 PM-2:30 PM'
 */
function parseExistingSchedule(scheduleString) {
    if (!scheduleString) return;
    
    console.log('Parsing existing schedule:', scheduleString);
    
    // Reset timeSlots
    timeSlots = [];
    
    // Split by commas to get individual slots
    const slots = scheduleString.split(',').map(s => s.trim()).filter(s => s);
    
    slots.forEach((slot, index) => {
        try {
             // Regex to flexibly capture days and time range, handling different day formats and spacing
            const parts = slot.match(/^([A-Za-z]+)\s+(\d{1,2}:\d{2})\s*(AM|PM)?\s*-\s*(\d{1,2}:\d{2})\s*(AM|PM)$/i);
            
            if (parts) {
                const dayString = parts[1].toUpperCase(); // Ensure uppercase for consistency
                const startTimePart = parts[2];
                const startAmpm = parts[3] ? parts[3].toUpperCase() : '';
                const endTimePart = parts[4];
                const endAmpm = parts[5] ? parts[5].toUpperCase() : '';
                
                // Construct 12-hour strings for parsing
                const startTimeStr = `${startTimePart}${startAmpm ? ' ' + startAmpm : ''}`.trim();
                const endTimeStr = `${endTimePart}${endAmpm ? ' ' + endAmpm : ''}`.trim();
                
                // Parse days - handle common combinations like Th, Su
                const days = [];
                let i = 0;
                while(i < dayString.length) {
                    if (i + 1 < dayString.length && (dayString.substring(i, i+2) === 'TH' || dayString.substring(i, i+2) === 'SU')) {
                        days.push(dayString.substring(i, i+2));
                        i += 2;
                    } else if (dayString[i].match(/[MTWFS]/)) {
                         days.push(dayString[i]);
                         i += 1;
                    } else {
                         console.warn('Unknown day character during parsing:', dayString[i]);
                         i += 1; // Skip unknown character
                    }
                }
                
                // Parse times - convert from 12-hour to 24-hour format
                const startTime = parse12HourTime(startTimeStr);
                const endTime = parse12HourTime(endTimeStr);
                
                if (startTime && endTime) {
                    // Add the parsed slot to timeSlots
                    addTimeSlot({ // Note: addTimeSlot already calls updateScheduleDisplay
                        id: `slot_${timeSlotCounter++}`,
                        days: days,
                        startTime: startTime,
                        endTime: endTime
                    });
                } else {
                     console.error(`Failed to parse time for slot: ${slot}. Parsed Start Time: ${startTime}, Parsed End Time: ${endTime}`); // Added error log
                }
            } else {
                 console.error(`Failed to match schedule format for slot: ${slot}. No parts matched regex.`); // Added error log
            }
        } catch (error) {
            console.error(`Error parsing schedule slot: ${slot}`, error);
        }
    });
    
    // No need to call updateScheduleDisplay here, addTimeSlot does it
    // updateScheduleDisplay();
}

/**
 * Parse a 12-hour time format string to 24-hour format
 * @param {string} timeStr - Time in 12-hour format (e.g., '9:00 AM', '12:00 PM')
 * @returns {string} Time in 24-hour format (e.g., '09:00', '12:00') or empty string on failure
 */
function parse12HourTime(timeStr) {
    try {
        timeStr = timeStr.trim();
        
        // Use a regex that is more flexible with spacing around AM/PM
        const parts = timeStr.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
        
        if (!parts || parts.length !== 4) {
             console.error('Invalid 12-hour time format:', timeStr); // Added error log
            return ''; // Indicate parsing failure
        }
        
        let hours = parseInt(parts[1], 10);
        const minutes = parts[2];
        const ampm = parts[3].toUpperCase();
        
        // Convert to 24-hour format
        if (ampm === 'PM' && hours < 12) {
            hours += 12;
        } else if (ampm === 'AM' && hours === 12) {
            hours = 0; // 12:xx AM is 00:xx in 24-hour format
        }
        
        // Format with leading zeros
        return `${hours.toString().padStart(2, '0')}:${minutes}`;
    } catch (error) {
        console.error('Error parsing 12-hour time:', timeStr, error); // Added error log
        return ''; // Indicate parsing failure
    }
}

/**
 * Resets the schedule builder UI and internal state.
 */
function resetScheduleBuilder() {
    console.log('Resetting schedule builder...');
    
    // Clear time slots array
    timeSlots = [];
    
    // Clear selected days set and uncheck day checkboxes
    selectedDays.clear();
    const dayCheckboxes = document.querySelectorAll('.day-checkbox');
    dayCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
        const label = checkbox.closest('.checkbox-btn');
        if(label) label.classList.remove('active');
    });
    
    // Clear schedule display
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    if (scheduleDisplay) {
        scheduleDisplay.innerHTML = '<span class="text-muted">No time slots added</span>';
    }
    
    // Clear the hidden schedule input
    const scheduleField = document.getElementById('schedule');
    if (scheduleField) {
        scheduleField.value = '';
    }
    
    // Reset time inputs to default values
    const startTime = document.getElementById('startTime');
    const endTime = document.getElementById('endTime');
    if (startTime) startTime.value = '10:00'; // Set to a default time
    if (endTime) endTime.value = '12:00'; // Set to a default time
    
    timeSlotCounter = 0; // Reset the counter
    console.log('Schedule builder reset.');
}

// Make the setup function available globally
window.setupScheduleBuilder = setupScheduleBuilder;

// Make the reset function available globally
window.resetScheduleBuilder = resetScheduleBuilder;

/**
 * Check for potential schedule conflicts
 * @param {Array} timeSlots - Array of time slots to check
 * @returns {Promise<{hasConflict: boolean, message: string}>}
 */
async function checkScheduleConflicts(timeSlots) {
    if (!timeSlots.length) {
        return { hasConflict: false, message: '' };
    }

    try {
        const response = await fetch('/classes/api/check-conflicts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                schedule: formatSchedule()
            })
        });

        const data = await response.json();
        return {
            hasConflict: !data.success,
            message: data.message || ''
        };
    } catch (error) {
        console.error('Error checking schedule conflicts:', error);
        return { hasConflict: false, message: 'Error checking schedule conflicts' };
    }
}

// Add validation before form submission
document.addEventListener('DOMContentLoaded', function() {
    const classForm = document.getElementById('classForm');
    if (classForm) {
        classForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Validate time slots
            if (timeSlots.length === 0) {
                showError('Please add at least one time slot');
                return;
            }

            // Validate each time slot
            for (const slot of timeSlots) {
                if (slot.days.length === 0) {
                    showError('Each time slot must have at least one day selected');
                    return;
                }
                if (!slot.startTime || !slot.endTime) {
                    showError('Each time slot must have valid start and end times');
                    return;
                }
            }

            // Check for conflicts
            try {
                const { hasConflict, message } = await checkScheduleConflicts(timeSlots);
                if (hasConflict) {
                    if (confirm(`Schedule Conflict Detected:\n\n${message}\n\nDo you want to proceed anyway?`)) {
                        classForm.submit();
                    }
                } else {
                    classForm.submit();
                }
            } catch (error) {
                showError('Error checking schedule conflicts. Please try again.');
                console.error('Schedule conflict check error:', error);
            }
        });
    }
});

// Helper function to show error messages
function showError(message) {
    const errorDiv = document.getElementById('scheduleError') || createErrorDiv();
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Scroll to error message
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Helper function to create error div if it doesn't exist
function createErrorDiv() {
    const errorDiv = document.createElement('div');
    errorDiv.id = 'scheduleError';
    errorDiv.className = 'alert alert-danger mt-3';
    errorDiv.style.display = 'none';
    
    const form = document.getElementById('classForm');
    form.insertBefore(errorDiv, form.firstChild);
    
    return errorDiv;
}