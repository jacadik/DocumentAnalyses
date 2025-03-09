"""
CSRF protection helpers for the application.
"""
from functools import wraps
from flask import request, abort, current_app
from flask_wtf.csrf import validate_csrf, CSRFError, generate_csrf
import logging

logger = logging.getLogger(__name__)

def csrf_protect():
    """
    Decorator to provide CSRF protection for non-WTForms routes.
    
    Example usage:
    
    @app.route('/delete/<id>', methods=['POST'])
    @csrf_protect()
    def delete(id):
        # Protected route code
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                # Get token from form data, JSON, or headers
                csrf_token = None
                
                if request.is_json:
                    csrf_token = request.json.get('csrf_token')
                elif request.form:
                    csrf_token = request.form.get('csrf_token')
                else:
                    csrf_token = request.headers.get('X-CSRFToken')
                
                try:
                    validate_csrf(csrf_token)
                except CSRFError as e:
                    logger.warning(f"CSRF validation failed: {str(e)}")
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_csrf_token():
    """
    Get a CSRF token.
    
    Returns:
        str: CSRF token
    """
    return generate_csrf()

def setup_csrf_protection(app):
    """
    Set up CSRF protection for the application.
    
    Args:
        app: Flask application instance
    """
    # Add a context processor to make CSRF token available in all templates
    @app.context_processor
    def csrf_token_processor():
        def csrf_token_field():
            return '<input type="hidden" name="csrf_token" value="' + get_csrf_token() + '">'
        
        return {
            'csrf_token': get_csrf_token,
            'csrf_token_field': csrf_token_field
        }
    
    # Handle CSRF errors
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        logger.warning(f"CSRF Error: {str(e)}")
        return render_template('errors/403.html', error=str(e)), 403

# Function to validate CSRF token in AJAX requests
def validate_ajax_csrf(request, token_name='csrf_token'):
    """
    Validate CSRF token in AJAX requests.
    
    Args:
        request: Flask request object
        token_name: Name of the CSRF token parameter
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    # Get token from different possible locations
    token = None
    
    if request.is_json:
        token = request.json.get(token_name)
    elif request.form:
        token = request.form.get(token_name)
    elif request.headers.get('X-CSRFToken'):
        token = request.headers.get('X-CSRFToken')
    
    if not token:
        return False
    
    try:
        validate_csrf(token)
        return True
    except CSRFError:
        return False
