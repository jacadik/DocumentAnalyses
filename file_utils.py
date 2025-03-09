import os
from werkzeug.utils import secure_filename
import uuid
import logging

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions):
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename (str): The name of the file to check
        allowed_extensions (set): Set of allowed file extensions
        
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_file_size(file, max_size):
    """
    Validate that a file is within the maximum allowed size.
    
    Args:
        file: The uploaded file object
        max_size (int): Maximum file size in bytes
        
    Returns:
        tuple: (is_valid, message)
    """
    # Try to get file size either from content_length or by reading the file
    file_size = None
    
    # Check if content_length is available
    if hasattr(file, 'content_length') and file.content_length:
        file_size = file.content_length
    
    # If not, try to get size by reading and seeking back
    if not file_size:
        position = file.tell()
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(position)  # Restore file position
    
    # If we still don't have a size, try a partial read
    if not file_size:
        # Read up to max_size + 1 to check if it exceeds
        data = file.read(max_size + 1)
        file_size = len(data)
        file.seek(0)  # Reset file position
    
    if file_size > max_size:
        return False, f"File exceeds maximum size of {max_size/(1024*1024):.1f}MB"
    
    return True, "File size is valid"

def save_uploaded_file(file, upload_folder, allowed_extensions, max_size=16*1024*1024):
    """
    Save an uploaded file with validation.
    
    Args:
        file: The uploaded file object
        upload_folder (str): Directory to save the file
        allowed_extensions (set): Set of allowed file extensions
        max_size (int): Maximum allowed file size in bytes
        
    Returns:
        tuple: (success, result_dict)
    """
    # Check if file has allowed extension
    if not allowed_file(file.filename, allowed_extensions):
        return False, {
            "error": "invalid_type",
            "message": f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        }
    
    # Check file size
    is_valid_size, size_message = validate_file_size(file, max_size)
    if not is_valid_size:
        return False, {
            "error": "file_too_large",
            "message": size_message
        }
    
    try:
        # Generate a unique filename
        original_filename = secure_filename(file.filename)
        file_type = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{str(uuid.uuid4())}_{original_filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        
        # Save the file
        file.save(file_path)
        logger.info(f"File saved: {file_path}")
        
        # Return success and file details
        return True, {
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "file_type": file_type,
            "file_path": file_path,
            "file_size": os.path.getsize(file_path)
        }
    except Exception as e:
        logger.exception(f"Error saving file {file.filename}: {str(e)}")
        return False, {
            "error": "save_error",
            "message": f"Error saving file: {str(e)}"
        }

def sanitize_path(base_dir, filename):
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        base_dir (str): Base directory that should contain the file
        filename (str): Filename to sanitize
        
    Returns:
        tuple: (is_safe, sanitized_path)
    """
    # Get just the basename (no directories)
    safe_name = os.path.basename(filename)
    
    # Construct full path
    full_path = os.path.join(base_dir, safe_name)
    
    # Normalize path (resolve ".." and symlinks)
    normalized_path = os.path.normpath(os.path.realpath(full_path))
    normalized_base = os.path.normpath(os.path.realpath(base_dir))
    
    # Check if path is within base directory
    if not normalized_path.startswith(normalized_base):
        return False, None
        
    return True, full_path

def list_files_in_directory(directory, extensions=None):
    """
    List files in a directory with optional extension filtering.
    
    Args:
        directory (str): Directory to list files from
        extensions (list): List of allowed extensions (without dot)
        
    Returns:
        list: List of filenames matching criteria
    """
    try:
        files = []
        for filename in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, filename)):
                if extensions:
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ""
                    if ext in extensions:
                        files.append(filename)
                else:
                    files.append(filename)
        return files
    except Exception as e:
        logger.error(f"Error listing files in directory {directory}: {str(e)}")
        return []
