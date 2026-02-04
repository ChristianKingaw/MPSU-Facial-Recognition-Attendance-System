document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('manualAttendanceForm');
    const dateInput = document.getElementById('attendanceDate');
    
    // Set max date to today (local date to avoid timezone/UTC shift)
    const _today = new Date();
    const _todayLocal = `${_today.getFullYear()}-${String(_today.getMonth() + 1).padStart(2, '0')}-${String(_today.getDate()).padStart(2, '0')}`;
    dateInput.max = _todayLocal;
    
    function showFeedback(message, type = 'success') {
        // Use the floating notification system
        if (window.showFloatingNotification) {
            const duration = type === 'error' || type === 'danger' ? 6000 : 4000;
            window.showFloatingNotification(message, type, duration, true);
        } else {
            // Fallback to the old system if floating notifications aren't available
            const feedback = document.getElementById('attendanceFeedback');
            if (feedback) {
                feedback.textContent = message;
                feedback.style.display = 'block';
                feedback.style.color = type === 'error' ? '#dc3545' : '#198754';
                
                // Hide feedback after 5 seconds
                setTimeout(() => {
                    feedback.style.display = 'none';
                }, 5000);
            }
        }
    }
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const studentDetailTitle = document.getElementById('studentDetailTitle');
        const studentDetailClass = document.getElementById('studentDetailClass');
        
        const studentId = studentDetailTitle.dataset.studentId;
        const classId = studentDetailClass.dataset.classId;
        
        if (!studentId || !classId) {
            showFeedback('Error: Missing student or class information', 'error');
            console.error('Manual Attendance Error: Student ID or Class ID missing.');
            return;
        }
        
        const date = document.getElementById('attendanceDate').value;
        const status = document.getElementById('manualAttendanceStatus').value;
        
        if (!date || !status) {
            showFeedback('Please select a date and status.', 'error');
            console.error('Manual Attendance Error: Date or Status missing.');
            return;
        }
        
        const formData = {
            student_id: studentId,
            class_id: classId,
            date: date,
            status: status
        };
        
        console.log('Attempting to add manual attendance with data:', formData);
        
        try {
            const response = await fetch('/attendance/manual', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            console.log('Response from /attendance/manual:', data);
            
            if (response.status === 409) {
                // Handle duplicate record - Ask user to update
                if (confirm('An attendance record already exists for this date. Would you like to update it?')) {
                    console.log('User confirmed update. Calling updateManualAttendance...');
                    await updateManualAttendance(studentId, classId, date, status);
                } else {
                    showFeedback('Attendance addition cancelled.', 'info');
                }
                return; // Stop processing after handling 409
            }
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to add attendance record');
            }
            
            // Success
            showFeedback(data.message || 'Attendance record added successfully', 'success');
            
            // Clear form
            document.getElementById('attendanceDate').value = '';
            document.getElementById('manualAttendanceStatus').value = 'Present';
            
            // Refresh attendance records in the student detail view
            await loadStudentAttendance(studentId, classId);
            
            // Refresh class overview after manual attendance change
            await loadClassOverview();

            // Refresh the student list in the class detail view without changing sections
            await refreshClassStudentsList(parseInt(classId)); // Ensure classId is an integer
            
        } catch (error) {
            console.error('Error adding manual attendance:', error);
            showFeedback(`Error adding attendance record: ${error.message}`, 'error');
        }
    });
});

// Function to update manual attendance record
async function updateManualAttendance(studentId, classId, date, status) {
    console.log('Attempting to update manual attendance with data:', {
        student_id: studentId,
        class_id: classId,
        date: date,
        status: status
    });
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
        console.log('Response from /attendance/update:', data);

        if (!response.ok) {
            throw new Error(data.error || 'Failed to update attendance record');
        }

        // Refresh attendance records
        await loadStudentAttendance(studentId, classId);
        
        // Refresh class overview after manual attendance change
        await loadClassOverview();

        // Refresh the student list in the class detail view without changing sections
        await refreshClassStudentsList(parseInt(classId)); // Ensure classId is an integer
        
        showFeedback('Attendance record updated successfully');
    } catch (error) {
        console.error('Error updating manual attendance:', error);
        showFeedback(`Error updating attendance record: ${error.message}`, 'error');
    }
} 