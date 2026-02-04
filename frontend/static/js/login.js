/**
 * Login Page JavaScript
 * Handles login/register form interactions and validation
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Login page initialized');
    
    // Initialize any login-specific functionality here
    initializeLoginPage();
});

/**
 * Initialize login page functionality
 */
function initializeLoginPage() {
    // Only add validation for register form
    setupRegisterFormValidation();
    
    // Auto-dismiss alerts after 5 seconds
    setupAutoAlerts();
    
    // Focus on first input field
    focusFirstInput();
}

/**
 * Setup validation only for register form
 */
function setupRegisterFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        // Only add validation to register form
        const isRegisterForm = form.querySelector('input[name="confirm_password"]');
        
        if (isRegisterForm) {
            form.addEventListener('submit', function(event) {
                validateRegisterForm(this, event);
            });
        }
    });
}

/**
 * Validate register form before submission
 */
function validateRegisterForm(form, event) {
    let isValid = true;
    
    // Add password confirmation validation for register form
    const password = form.querySelector('input[name="password"]');
    const confirmPassword = form.querySelector('input[name="confirm_password"]');
    
    if (password && confirmPassword && password.value !== confirmPassword.value) {
        isValid = false;
        confirmPassword.classList.add('is-invalid');
        
        // Show custom error message
        let errorDiv = confirmPassword.parentNode.querySelector('.password-mismatch-error');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'text-danger password-mismatch-error';
            errorDiv.textContent = 'Passwords do not match';
            confirmPassword.parentNode.appendChild(errorDiv);
        }
    } else if (confirmPassword) {
        confirmPassword.classList.remove('is-invalid');
        const errorDiv = confirmPassword.parentNode.querySelector('.password-mismatch-error');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
    
    if (!isValid) {
        event.preventDefault();
    }
}

/**
 * Setup auto-dismissing alerts
 */
function setupAutoAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert && alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });
}

/**
 * Focus on the first input field
 */
function focusFirstInput() {
    const firstInput = document.querySelector('input[type="text"], input[type="email"], input[type="password"]');
    if (firstInput) {
        firstInput.focus();
    }
}

/**
 * Show loading state on form submission
 */
function showLoadingState(button) {
    const originalText = button.textContent;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    
    // Re-enable button after 10 seconds as fallback
    setTimeout(() => {
        button.disabled = false;
        button.textContent = originalText;
    }, 10000);
}