/* Author: Wilson Xu */
/* Updated for Bootstrap 5 Migration */

/**
 * Dynamically adds a Bootstrap 5 alert message to the DOM.
 * @param {string} message - The message content (can include HTML).
 * @param {string} category - The alert category (e.g., 'success', 'danger', 'warning', 'info'). Corresponds to alert-* classes.
 */
function add_flash_message(message, category) {
    const container = document.getElementById('flash_message_container');
    if (!container) {
        console.error('Flash message container not found!');
        return; // Exit if container doesn't exist
    }

    // Create the alert element using Bootstrap 5 structure
    const alertDiv = document.createElement('div');
    // Add standard BS5 alert classes for styling and dismissibility
    alertDiv.className = `alert alert-${category} alert-dismissible fade show`;
    alertDiv.setAttribute('role', 'alert');

    // Set the inner HTML, including the BS5 close button
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Append the new alert to the container using vanilla JS
    container.appendChild(alertDiv);

    /*
    // Optional: Automatically dismiss the alert after a delay using BS5 JS API
    setTimeout(() => {
        // Get the Bootstrap Alert instance associated with the element
        const alertInstance = bootstrap.Alert.getOrCreateInstance(alertDiv);
        if (alertInstance) {
            alertInstance.close(); // Programmatically close the alert
        }
    }, 7000); // Example: Close after 7 seconds
    */
}

/**
 * Determine if text is selected in any input element.
 * (No changes needed for BS5 - uses standard JS and IE fallback)
 * @param {HTMLInputElement|HTMLTextAreaElement} input - The input element.
 * @returns {boolean} - True if text is selected, false otherwise.
 */
function isTextSelected(input) {
    // Standard browsers
    if (typeof input.selectionStart == "number") {
        return input.selectionStart == 0 && input.selectionEnd == input.value.length;
    }
    // Older IE
    else if (typeof document.selection != "undefined") {
        input.focus();
        return document.selection.createRange().text == input.value;
    }
    return false; // Default fallback
}

/**
 * Hides the flash message container using jQuery slideUp animation.
 * Kept as-is because jQuery is remaining for other plugins.
 */
function hide_flask_message_container() {
    // This function relies on jQuery for the animation.
    if (typeof $ !== 'undefined') {
        $('#flash_message_container').slideUp('fast');
    } else {
        // Fallback if jQuery wasn't loaded for some reason
        const container = document.getElementById('flash_message_container');
        if (container) {
            container.style.display = 'none';
        }
    }
}

// Use jQuery's document ready since jQuery is still loaded for plugins
$(document).ready(function() {
    // Initialize AlarmDecoder logic (assuming it doesn't depend on BS/jQuery UI elements)
    var decoder = new AlarmDecoder(); // Made variable local with var/const/let
    decoder.init();

    // Removed custom $('.alert').on('click/touchend') handlers.
    // Relying on the standard BS5 dismissal via the '.btn-close' button
    // generated in add_flash_message, which uses data-bs-dismiss="alert".

    // Removed conditional styling for '#wrap'.
    // The #wrap element is likely removed due to Flexbox sticky footer in base.html.
    // Test layout on iOS/Android and re-apply overflow styling ONLY IF necessary
    // and target the correct element (e.g., body or the main content wrapper).
    /*
    if( !isiPad && !isiPhone ) { // Keep conditional check if needed
        const mainContent = document.querySelector('.main-content-wrapper'); // Example: Target new main wrapper
        if (mainContent) {
            mainContent.style.overflowX = 'hidden';
        }
        // or document.body.style.overflowX = 'hidden';
    }
    */
});
