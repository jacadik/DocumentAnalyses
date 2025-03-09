import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file
import io
from utils.file_utils import sanitize_path, list_files_in_directory

# Create blueprint
bp = Blueprint('logs', __name__)

@bp.route('/')
def list():
    """Display list of log files."""
    log_dir = current_app.config['LOG_FOLDER']
    
    # Use file_utils to safely list log files
    log_files = list_files_in_directory(log_dir, extensions=['log'])
    
    # Sort log files by modification time (newest first)
    log_files.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
    
    # Read current log file
    current_log_path = current_app.config['LOG_FILE']
    try:
        with open(current_log_path, 'r') as f:
            log_contents = f.readlines()
    except FileNotFoundError:
        log_contents = ["No log file found."]
    except Exception as e:
        current_app.logger.error(f"Error reading log file: {str(e)}")
        log_contents = [f"Error reading log file: {str(e)}"]
    
    return render_template('logs.html', log_files=log_files, log_contents=log_contents)

@bp.route('/<path:filename>')
def view(filename):
    """View a specific log file."""
    log_dir = current_app.config['LOG_FOLDER']
    
    # Sanitize path to prevent directory traversal
    is_safe, log_path = sanitize_path(log_dir, filename)
    
    if not is_safe:
        current_app.logger.warning(f"Attempted path traversal detected: {filename}")
        abort(403)  # Forbidden
    
    if not os.path.exists(log_path):
        flash('Log file not found', 'error')
        return redirect(url_for('logs.list'))
    
    try:
        with open(log_path, 'r') as f:
            log_contents = f.readlines()
    except Exception as e:
        current_app.logger.error(f"Error reading log file {log_path}: {str(e)}")
        log_contents = [f"Error reading log file: {str(e)}"]
    
    return render_template('view_log.html', filename=filename, log_contents=log_contents)

@bp.route('/download/<path:filename>')
def download(filename):
    """Download a log file."""
    log_dir = current_app.config['LOG_FOLDER']
    
    # Sanitize path to prevent directory traversal
    is_safe, log_path = sanitize_path(log_dir, filename)
    
    if not is_safe:
        current_app.logger.warning(f"Attempted path traversal detected: {filename}")
        abort(403)  # Forbidden
    
    if not os.path.exists(log_path):
        flash('Log file not found', 'error')
        return redirect(url_for('logs.list'))
    
    return send_file(
        log_path,
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )

@bp.route('/api/latest')
def latest_logs():
    """API endpoint to get the latest log entries."""
    log_path = current_app.config['LOG_FILE']
    limit = request.args.get('limit', default=100, type=int)
    level = request.args.get('level', default=None, type=str)
    
    try:
        # Read the log file
        with open(log_path, 'r') as f:
            log_lines = f.readlines()
        
        # Filter by level if specified
        if level:
            log_lines = [line for line in log_lines if f" {level.upper()}: " in line]
        
        # Get the last N lines
        latest_entries = log_lines[-limit:] if limit > 0 else log_lines
        
        # Parse log entries into a more structured format
        parsed_entries = []
        for line in latest_entries:
            try:
                # Parse based on expected format: "2023-01-01 12:34:56 INFO: message [in file.py:line]"
                parts = line.split(' ', 3)
                timestamp = f"{parts[0]} {parts[1]}"
                level_with_colon = parts[2]
                message_with_location = parts[3]
                
                # Split level from colon
                level = level_with_colon.strip(':')
                
                # Extract location if present
                location = ""
                message = message_with_location
                if " [in " in message_with_location and message_with_location.endswith("]"):
                    message, location = message_with_location.rsplit(" [in ", 1)
                    location = f"[in {location}"
                
                parsed_entries.append({
                    'timestamp': timestamp,
                    'level': level,
                    'message': message.strip(),
                    'location': location.strip()
                })
            except Exception:
                # If parsing fails, include the raw line
                parsed_entries.append({
                    'timestamp': '',
                    'level': 'UNKNOWN',
                    'message': line.strip(),
                    'location': ''
                })
        
        return {
            'success': True,
            'entries': parsed_entries,
            'total_count': len(log_lines),
            'returned_count': len(parsed_entries)
        }
    except Exception as e:
        current_app.logger.error(f"Error fetching log entries: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'entries': []
        }
