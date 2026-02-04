// enroll-init.js - Initialization script for the enrollment page
// This script ensures that the init function from students.js is loaded and available
// before trying to use it. It helps prevent errors if the function is loaded asynchronously
// or from an external script

// Wait for students.js to be loaded
window.addEventListener('load', async function() {
    // Wait for init function to be available
    let attempts = 0;
    const maxAttempts = 10;

    while (!window.init && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 100));
        attempts++;
    }

    if (window.init) {
        // Use the global initialization function
        await window.init();
    } else {
        console.error('init function not found');
    }
});