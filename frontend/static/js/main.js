// Utility Functions
function showAlert(message, type = 'success') {
    // Use the floating notification system
    if (window.showFloatingNotification) {
        const duration = type === 'error' || type === 'danger' ? 6000 : 4000;
        window.showFloatingNotification(message, type, duration, true);
    } else {
        // Fallback to the old system if floating notifications aren't available
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    }
}

// Form Validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;
    
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.classList.add('is-invalid');
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// API Functions
async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'FrC4sS3cUr3K3y2024!@#$%^&*()'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showAlert('An error occurred while communicating with the server', 'danger');
        throw error;
    }
}

// Session Management
function checkSession() {
    fetchAPI('/auth/check-auth')
        .then(data => {
            if (!data.authenticated) {
                window.location.href = '/auth/login';
            }
        })
        .catch(() => {
            window.location.href = '/auth/login';
        });
}

// Face Recognition
async function captureFace() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const context = canvas.getContext('2d');
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        
        return new Promise((resolve) => {
            video.onloadedmetadata = () => {
                video.play();
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/jpeg');
                resolve(imageData);
            };
        });
    } catch (error) {
        console.error('Error accessing camera:', error);
        showAlert('Error accessing camera. Please ensure you have granted camera permissions.', 'danger');
        throw error;
    }
}

// Attendance Functions
async function markAttendance(classId) {
    try {
        const faceImage = await captureFace();
        const response = await fetchAPI('/api/mark-attendance', {
            method: 'POST',
            body: JSON.stringify({
                class_id: classId,
                face_image: faceImage
            })
        });
        
        if (response.success) {
            showAlert('Attendance marked successfully!');
        } else {
            showAlert(response.message || 'Failed to mark attendance', 'danger');
        }
    } catch (error) {
        console.error('Attendance Error:', error);
        showAlert('Failed to mark attendance', 'danger');
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!validateForm(form.id)) {
                e.preventDefault();
                showAlert('Please fill in all required fields', 'danger');
            }
        });
    });
    
    // Session check
    if (document.body.dataset.requiresAuth === 'true') {
        checkSession();
    }
    
    // Face capture button
    const captureButton = document.getElementById('capture-face');
    if (captureButton) {
        captureButton.addEventListener('click', async () => {
            try {
                const faceImage = await captureFace();
                document.getElementById('face-image').value = faceImage;
                showAlert('Face captured successfully!');
            } catch (error) {
                console.error('Face Capture Error:', error);
            }
        });
    }
}); 