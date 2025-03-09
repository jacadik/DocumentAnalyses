/**
 * Document Analyzer - Main JavaScript
 * This file contains shared functionality used across multiple pages
 */

// Use strict mode for better error catching and performance
'use strict';

// Main app namespace to avoid polluting global namespace
const DocumentAnalyzer = {
  // Configuration
  config: {
    activeNavClass: 'active',
    confirmSelectors: '[data-confirm]',
    tooltipSelectors: '[data-bs-toggle="tooltip"]',
    fileInputSelectors: '.custom-file-input'
  },
  
  // Initialization function
  init: function() {
    // Set the active navigation item based on current page
    this.setActiveNavItem();
    
    // Initialize confirm dialogs
    this.initConfirmDialogs();
    
    // Initialize Bootstrap tooltips
    this.initTooltips();
    
    // Initialize file input display enhancements
    this.initFileInputs();
    
    // Handle modal events and forms
    this.initModals();
    
    // Initialize any search inputs
    this.initSearchInputs();
    
    console.log('Document Analyzer JS initialized');
  },
  
  /**
   * Set the active navigation item based on current URL
   */
  setActiveNavItem: function() {
    // Get current path
    const currentPath = window.location.pathname.split('?')[0];
    
    // Find nav links
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
      const href = link.getAttribute('href');
      
      // Match for exact path or if current path starts with href (for subpaths)
      if (href === currentPath || 
          (href !== '/' && currentPath.startsWith(href))) {
        link.classList.add(this.config.activeNavClass);
        
        // Also add active class to parent if it's a dropdown
        const parentDropdown = link.closest('.nav-item.dropdown');
        if (parentDropdown) {
          const dropdownToggle = parentDropdown.querySelector('.dropdown-toggle');
          if (dropdownToggle) {
            dropdownToggle.classList.add(this.config.activeNavClass);
          }
        }
      }
    });
  },
  
  /**
   * Initialize confirmation dialogs using data attributes
   */
  initConfirmDialogs: function() {
    // Use event delegation for better performance
    document.addEventListener('click', event => {
      const confirmElement = event.target.closest(this.config.confirmSelectors);
      
      if (confirmElement && !event.defaultPrevented) {
        event.preventDefault();
        
        const message = confirmElement.dataset.confirm || 'Are you sure?';
        const confirmCallback = () => {
          // If it's a link, navigate to it
          if (confirmElement.tagName === 'A') {
            window.location.href = confirmElement.href;
          } 
          // If it's inside a form, submit the form
          else if (confirmElement.form) {
            confirmElement.form.submit();
          }
          // Otherwise trigger a custom event that can be listened for
          else {
            confirmElement.dispatchEvent(new CustomEvent('confirmation:confirmed'));
          }
        };
        
        this.showConfirmDialog(message, confirmCallback);
      }
    });
  },
  
  /**
   * Show a confirmation dialog
   * @param {string} message - The confirmation message
   * @param {function} confirmCallback - Function to call if confirmed
   */
  showConfirmDialog: function(message, confirmCallback) {
    // First try to use Bootstrap modal if available
    const confirmModal = document.getElementById('confirmationModal');
    
    if (confirmModal) {
      const messageEl = confirmModal.querySelector('.modal-body');
      const confirmBtn = confirmModal.querySelector('.btn-confirm');
      
      if (messageEl && confirmBtn) {
        // Set the message
        messageEl.textContent = message;
        
        // Set up confirmation action
        confirmBtn.addEventListener('click', () => {
          const bsModal = bootstrap.Modal.getInstance(confirmModal);
          bsModal.hide();
          confirmCallback();
        }, { once: true });
        
        // Show the modal
        const bsModal = new bootstrap.Modal(confirmModal);
        bsModal.show();
        return;
      }
    }
    
    // Fallback to native confirm dialog if no modal is available
    if (window.confirm(message)) {
      confirmCallback();
    }
  },
  
  /**
   * Initialize Bootstrap tooltips
   */
  initTooltips: function() {
    const tooltipTriggerList = document.querySelectorAll(this.config.tooltipSelectors);
    if (window.bootstrap && tooltipTriggerList.length > 0) {
      const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => {
        return new bootstrap.Tooltip(tooltipTriggerEl);
      });
    }
  },
  
  /**
   * Initialize custom file input elements
   */
  initFileInputs: function() {
    const fileInputs = document.querySelectorAll(this.config.fileInputSelectors);
    
    fileInputs.forEach(input => {
      input.addEventListener('change', function() {
        // Find associated label or create a display element
        let fileDisplayEl = document.querySelector('[for="' + this.id + '"] .file-name');
        
        if (!fileDisplayEl) {
          // No label found, check for a data-display attribute
          const displaySelector = this.dataset.display;
          if (displaySelector) {
            fileDisplayEl = document.querySelector(displaySelector);
          }
        }
        
        if (fileDisplayEl && this.files && this.files.length > 0) {
          if (this.files.length === 1) {
            fileDisplayEl.textContent = this.files[0].name;
          } else {
            fileDisplayEl.textContent = `${this.files.length} files selected`;
          }
        }
      });
    });
  },
  
  /**
   * Initialize modals functionality
   */
  initModals: function() {
    // Handle any data-* attributes for modals
    document.addEventListener('show.bs.modal', event => {
      const modal = event.target;
      const button = event.relatedTarget;
      
      // If we have a button that triggered the modal
      if (button && button.dataset) {
        // Find form in modal if exists
        const form = modal.querySelector('form');
        
        // Transfer any data-form-* attributes to the form action
        if (form && button.dataset.formAction) {
          form.action = button.dataset.formAction;
        }
        
        // Transfer any other data-modal-* attributes to modal elements
        Object.keys(button.dataset).forEach(key => {
          if (key.startsWith('modal')) {
            // Get the target field name (e.g., modalTitle -> title)
            const fieldName = key.charAt(5).toLowerCase() + key.substring(6);
            
            // Find element with that ID or with data-field attribute
            const targetEl = modal.querySelector('#' + fieldName) || 
                             modal.querySelector('[data-field="' + fieldName + '"]');
            
            if (targetEl) {
              // Set as HTML content if element has data-html attribute
              if (targetEl.dataset.html === 'true') {
                targetEl.innerHTML = button.dataset[key];
              } else {
                targetEl.textContent = button.dataset[key];
              }
              
              // If it's an input or select, set its value
              if (targetEl.tagName === 'INPUT' || targetEl.tagName === 'SELECT' || targetEl.tagName === 'TEXTAREA') {
                targetEl.value = button.dataset[key];
              }
            }
          }
        });
      }
    });
  },
  
  /**
   * Initialize search inputs on tables/lists
   */
  initSearchInputs: function() {
    const searchInputs = document.querySelectorAll('[data-search-target]');
    
    searchInputs.forEach(input => {
      input.addEventListener('input', function() {
        const targetId = this.dataset.searchTarget;
        const target = document.getElementById(targetId);
        
        if (!target) return;
        
        const searchTerm = this.value.toLowerCase();
        const items = target.querySelectorAll('[data-search-item]');
        
        items.forEach(item => {
          const text = item.textContent.toLowerCase();
          // Also check data-search-text for additional searchable content
          const additionalText = item.dataset.searchText ? item.dataset.searchText.toLowerCase() : '';
          
          if (text.includes(searchTerm) || additionalText.includes(searchTerm)) {
            item.style.display = '';
          } else {
            item.style.display = 'none';
          }
        });
        
        // Check if we need to show "no results" message
        const noResultsMsg = document.querySelector('[data-search-no-results="' + targetId + '"]');
        if (noResultsMsg) {
          const visibleItems = target.querySelectorAll('[data-search-item]:not([style*="display: none"])');
          noResultsMsg.style.display = visibleItems.length === 0 ? 'block' : 'none';
        }
      });
    });
  },
  
  /**
   * Get CSRF token from meta tag
   * @returns {string} CSRF token value or empty string if not found
   */
  getCSRFToken: function() {
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    return metaToken ? metaToken.getAttribute('content') : '';
  },
  
  /**
   * Helper to add CSRF token to form data
   * @param {FormData} formData - FormData object to add token to
   * @returns {FormData} The modified FormData object
   */
  addCSRFToFormData: function(formData) {
    const token = this.getCSRFToken();
    if (token) {
      formData.append('csrf_token', token);
    }
    return formData;
  },
  
  /**
   * Format file size into human-readable string
   * @param {number} bytes - File size in bytes
   * @returns {string} Formatted file size
   */
  formatFileSize: function(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },
  
  /**
   * Sanitize HTML to prevent XSS
   * @param {string} html - String that might contain HTML
   * @returns {string} Sanitized string
   */
  sanitizeHTML: function(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
  }
};

// Initialize DocumentAnalyzer when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  DocumentAnalyzer.init();
});

// Reusable utility for drag and drop file upload
const FileUploader = {
  init: function(options) {
    this.options = Object.assign({
      dropZoneSelector: '.upload-area',
      fileInputSelector: 'input[type="file"]',
      fileListSelector: '#fileList',
      maxFiles: 10,
      maxFileSize: 16 * 1024 * 1024, // 16MB default
      allowedTypes: ['.pdf', '.docx']
    }, options);
    
    this.dropZone = document.querySelector(this.options.dropZoneSelector);
    this.fileInput = document.querySelector(this.options.fileInputSelector);
    this.fileList = document.querySelector(this.options.fileListSelector);
    
    if (this.dropZone && this.fileInput) {
      this.setupEventListeners();
    }
  },
  
  setupEventListeners: function() {
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      this.dropZone.addEventListener(eventName, this.preventDefaults, false);
      document.body.addEventListener(eventName, this.preventDefaults, false);
    });
    
    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
      this.dropZone.addEventListener(eventName, this.highlight.bind(this), false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      this.dropZone.addEventListener(eventName, this.unhighlight.bind(this), false);
    });
    
    // Handle dropped files
    this.dropZone.addEventListener('drop', this.handleDrop.bind(this), false);
    
    // Handle browse button click
    this.dropZone.addEventListener('click', () => {
      this.fileInput.click();
    });
    
    // Handle file input change
    this.fileInput.addEventListener('change', this.handleFiles.bind(this), false);
    
    // Make accessible for keyboard users
    this.dropZone.setAttribute('tabindex', '0');
    this.dropZone.setAttribute('role', 'button');
    this.dropZone.setAttribute('aria-label', 'Drop files here or click to browse');
    
    // Handle keyboard events for accessibility
    this.dropZone.addEventListener('keydown', (e) => {
      // Trigger click on Enter or Space
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.fileInput.click();
      }
    });
  },
  
  preventDefaults: function(e) {
    e.preventDefault();
    e.stopPropagation();
  },
  
  highlight: function() {
    this.dropZone.classList.add('active-drag');
    this.dropZone.setAttribute('aria-live', 'polite');
    this.dropZone.setAttribute('aria-relevant', 'additions');
  },
  
  unhighlight: function() {
    this.dropZone.classList.remove('active-drag');
  },
  
  handleDrop: function(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    this.handleFiles(files);
  },
  
  handleFiles: function(files) {
    // If event was triggered from file input
    if (!files.length && this.fileInput.files) {
      files = this.fileInput.files;
    }
    
    if (!files.length) return;
    
    // Validate files
    let validFiles = [];
    let errors = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      // Check file type
      if (!this.options.allowedTypes.includes(fileExtension)) {
        errors.push(`File "${file.name}" has invalid type. Allowed: ${this.options.allowedTypes.join(', ')}`);
        continue;
      }
      
      // Check file size
      if (file.size > this.options.maxFileSize) {
        errors.push(`File "${file.name}" exceeds maximum size of ${DocumentAnalyzer.formatFileSize(this.options.maxFileSize)}`);
        continue;
      }
      
      validFiles.push(file);
      
      // Check max files
      if (validFiles.length >= this.options.maxFiles) {
        if (files.length > this.options.maxFiles) {
          errors.push(`Only the first ${this.options.maxFiles} valid files will be uploaded`);
        }
        break;
      }
    }
    
    // Update file list UI
    this.updateFileList(validFiles, errors);
    
    // Update file input
    if (validFiles.length > 0) {
      // We can't directly set files, so we need to use the DataTransfer API
      const dt = new DataTransfer();
      validFiles.forEach(file => dt.items.add(file));
      this.fileInput.files = dt.files;
      
      // Dispatch change event to trigger any listeners
      this.fileInput.dispatchEvent(new Event('change'));
    }
  },
  
  updateFileList: function(files, errors = []) {
    if (!this.fileList) return;
    
    let html = '';
    
    if (files.length > 0) {
      html += '<div class="alert alert-info mt-3">';
      html += `<strong><i class="bi bi-file-earmark"></i> Selected ${files.length} file${files.length === 1 ? '' : 's'}:</strong>`;
      html += '<ul class="list-group mt-2">';
      
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileSize = DocumentAnalyzer.formatFileSize(file.size);
        const fileType = file.name.split('.').pop().toUpperCase();
        const icon = fileType === 'PDF' ? 'bi-file-earmark-pdf' : 'bi-file-earmark-word';
        
        html += `
        <li class="list-group-item d-flex justify-content-between align-items-center">
          <div>
            <i class="bi ${icon} me-2 text-primary"></i>
            ${DocumentAnalyzer.sanitizeHTML(file.name)}
            <span class="badge bg-secondary ms-2">${fileType}</span>
          </div>
          <span class="text-muted">${fileSize}</span>
        </li>`;
      }
      
      html += '</ul></div>';
    }
    
    // Show errors if any
    if (errors.length > 0) {
      html += '<div class="alert alert-danger mt-3">';
      html += '<strong><i class="bi bi-exclamation-triangle"></i> Errors:</strong>';
      html += '<ul class="mb-0 mt-2">';
      
      for (let i = 0; i < errors.length; i++) {
        html += `<li>${DocumentAnalyzer.sanitizeHTML(errors[i])}</li>`;
      }
      
      html += '</ul></div>';
    }
    
    this.fileList.innerHTML = html;
    
    // Announce to screen readers
    const ariaLive = document.querySelector('[role="status"]');
    if (ariaLive) {
      ariaLive.textContent = files.length > 0 
        ? `Selected ${files.length} files. ${errors.length > 0 ? errors.length + ' errors occurred.' : ''}` 
        : '';
    }
  }
};
