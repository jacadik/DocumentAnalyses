from flask import render_template, request
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """
    Register custom error handlers for the Flask application.
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def page_not_found(error):
        """Handle 404 (Not Found) errors."""
        app.logger.info(f"404 error for {request.path} - {request.remote_addr}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 (Forbidden) errors."""
        app.logger.warning(f"403 error for {request.path} - {request.remote_addr}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """
        Handle 500 (Internal Server Error) errors.
        Use logger.exception to capture full traceback.
        """
        app.logger.exception(f"500 error for {request.path} - {request.remote_addr}")
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle 413 (Request Entity Too Large) errors."""
        app.logger.warning(f"413 error for {request.path} - File too large - {request.remote_addr}")
        return render_template('errors/413.html'), 413

def setup_logging(app, log_level=logging.INFO):
    """
    Set up application logging with appropriate handlers and formatters.
    
    Args:
        app: Flask application instance
        log_level: Desired logging level (default: INFO)
    """
    if app.debug:
        # In debug mode, just use the default Flask logger
        return
    
    from logging.handlers import RotatingFileHandler
    import os
    
    # Ensure log directory exists
    os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
    
    # Configure file handler with rotation to prevent huge log files
    file_handler = RotatingFileHandler(
        app.config['LOG_FILE'],
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    
    # Create formatter with more information for debugging
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Add handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(log_level)
    
    # Set SQLAlchemy logging to WARNING level to reduce noise
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    
    # Set Werkzeug logging to WARNING level in production
    if not app.debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    app.logger.info('Application starting up')

def log_form_errors(app, form, logger=None):
    """
    Log form validation errors.
    
    Args:
        app: Flask application instance
        form: Form with errors
        logger: Optional specific logger to use
    """
    logger = logger or app.logger
    
    for field, errors in form.errors.items():
        for error in errors:
            logger.warning(f"Form validation error in field '{field}': {error}")
