/**
 * Bootstrap Toast Notification System
 * Uses Bootstrap's built-in toast components for reliable notifications
 */

class BootstrapToastManager {
    constructor() {
        this.container = null;
        this.toastId = 0;
        this.init();
    }

    init() {
        // Create toast container
        this.container = document.createElement('div');
        this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
        this.container.style.zIndex = '9999';
        document.body.appendChild(this.container);
    }

    /**
     * Show a Bootstrap toast notification
     * @param {string} message - The message to display
     * @param {string} type - The notification type (success, error, warning, info)
     * @param {number} duration - How long to show the notification (in ms, 0 for persistent)
     * @returns {number} - The toast ID
     */
    show(message, type = 'success', duration = 4000) {
        const id = ++this.toastId;
        
        // Map types to Bootstrap classes and icons
        const typeConfig = {
            success: { bgClass: 'bg-success', icon: 'fas fa-check-circle', iconColor: 'text-white' },
            error: { bgClass: 'bg-danger', icon: 'fas fa-exclamation-circle', iconColor: 'text-white' },
            danger: { bgClass: 'bg-danger', icon: 'fas fa-exclamation-circle', iconColor: 'text-white' },
            warning: { bgClass: 'bg-warning', icon: 'fas fa-exclamation-triangle', iconColor: 'text-dark' },
            info: { bgClass: 'bg-info', icon: 'fas fa-info-circle', iconColor: 'text-white' }
        };
        
        const config = typeConfig[type] || typeConfig.info;
        const textColor = type === 'warning' ? 'text-dark' : 'text-white';
        
        // Create toast HTML
        const toastHtml = `
            <div class="toast ${config.bgClass} ${textColor}" role="alert" data-toast-id="${id}">
                <div class="toast-body d-flex align-items-center">
                    <i class="${config.icon} ${config.iconColor} me-2"></i>
                    <span class="flex-grow-1">${message}</span>
                    <button type="button" class="btn-close btn-close-white ms-2" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        // Add to container
        this.container.insertAdjacentHTML('beforeend', toastHtml);
        
        // Get the toast element
        const toastElement = this.container.querySelector(`[data-toast-id="${id}"]`);
        
        // Initialize Bootstrap toast
        const bsToast = new bootstrap.Toast(toastElement, {
            autohide: duration > 0,
            delay: duration
        });
        
        // Show the toast
        bsToast.show();
        
        // Clean up after toast is hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
        
        return id;
    }

    /**
     * Convenience methods for different notification types
     */
    success(message, duration = 4000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }
}

// Global instance
const toastManager = new BootstrapToastManager();

// Global convenience functions
window.showFloatingNotification = (message, type, duration, allowClose) => {
    return toastManager.show(message, type, duration);
};

window.showSuccessNotification = (message, duration) => {
    return toastManager.success(message, duration);
};

window.showErrorNotification = (message, duration) => {
    return toastManager.error(message, duration);
};

window.showWarningNotification = (message, duration) => {
    return toastManager.warning(message, duration);
};

window.showInfoNotification = (message, duration) => {
    return toastManager.info(message, duration);
};

// Clear all currently displayed floating notifications (toasts)
window.clearFloatingNotifications = () => {
    try {
        if (!toastManager || !toastManager.container) return;
        const toasts = Array.from(toastManager.container.querySelectorAll('.toast'));
        toasts.forEach(t => {
            try {
                // If Bootstrap has an instance, hide it first to trigger cleanup
                const bsToast = bootstrap && bootstrap.Toast ? bootstrap.Toast.getInstance(t) : null;
                if (bsToast && typeof bsToast.hide === 'function') {
                    bsToast.hide();
                }
            } catch (e) {
                // ignore
            }
            // Remove the element if still present
            if (t.parentNode) t.remove();
        });
    } catch (err) {
        console.error('Error clearing floating notifications:', err);
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BootstrapToastManager;
}