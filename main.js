// JavaScript for Document Analyzer

document.addEventListener('DOMContentLoaded', function() {
    // File input change handler to show selected files
    const fileInput = document.getElementById('file');
    const fileList = document.getElementById('fileList');
    
    if (fileInput && fileList) {
        fileInput.addEventListener('change', function() {
            const fileCount = this.files.length;
            
            if (fileCount > 0) {
                let html = '<div class="alert alert-info mt-3">';
                html += `<strong>Selected ${fileCount} file${fileCount === 1 ? '' : 's'}:</strong><ul>`;
                
                for (let i = 0; i < Math.min(fileCount, 10); i++) {
                    const file = this.files[i];
                    const fileSize = (file.size / 1024).toFixed(2);
                    html += `<li>${file.name} (${fileSize} KB)</li>`;
                }
                
                if (fileCount > 10) {
                    html += `<li>...and ${fileCount - 10} more files</li>`;
                }
                
                html += '</ul></div>';
                fileList.innerHTML = html;
            } else {
                fileList.innerHTML = '';
            }
        });
    }
    
    // Delete confirmation modal handler
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', function(event) {
            // Button that triggered the modal
            const button = event.relatedTarget;
            
            // Extract info from data attributes (if not in view.html where it's pre-populated)
            if (button.hasAttribute('data-doc-id') && button.hasAttribute('data-doc-name')) {
                const docId = button.getAttribute('data-doc-id');
                const docName = button.getAttribute('data-doc-name');
                
                // Find and update docName element if it exists
                const docNameEl = this.querySelector('#docName');
                if (docNameEl) {
                    docNameEl.textContent = docName;
                }
                
                // Update form action if it's in documents.html
                const deleteForm = this.querySelector('#deleteForm');
                if (deleteForm) {
                    deleteForm.action = '/document/delete/' + docId;
                }
            }
        });
    }
    
    // Enable tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});
