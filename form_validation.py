"""
Form validation utilities.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, FileField, MultipleFileField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
import os
from werkzeug.utils import secure_filename

class DocumentUploadForm(FlaskForm):
    """Form for uploading documents."""
    file = MultipleFileField('Files', validators=[DataRequired()])
    
    def validate_file(self, field):
        """Validate uploaded files."""
        # Check if any files were uploaded
        if not field.data or all(not f.filename for f in field.data):
            raise ValidationError('No files selected.')
        
        # Check each file
        for file in field.data:
            # Skip empty files
            if not file.filename:
                continue
            
            # Get file extension
            ext = os.path.splitext(file.filename)[1].lower()
            
            # Check if extension is allowed
            if ext not in ['.pdf', '.docx']:
                raise ValidationError(f'File "{file.filename}" has an invalid extension. Allowed: .pdf, .docx')
            
            # Check if file size is too large (16MB limit)
            max_size = 16 * 1024 * 1024
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            
            if size > max_size:
                raise ValidationError(f'File "{file.filename}" is too large. Maximum size is 16MB.')

class TagForm(FlaskForm):
    """Form for tag management."""
    name = StringField('Tag Name', validators=[
        DataRequired(), 
        Length(min=1, max=50, message='Tag name must be between 1 and 50 characters.')
    ])
    color = StringField('Color', default='#6c757d')
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=200, message='Description must be 200 characters or less.')
    ])

def validate_file_extension(filename, allowed_extensions):
    """
    Validate file extension.
    
    Args:
        filename (str): Filename to validate
        allowed_extensions (list): List of allowed extensions
        
    Returns:
        bool: True if extension is allowed, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_filename(filename):
    """
    Validate filename to prevent potential security issues.
    
    Args:
        filename (str): Filename to validate
        
    Returns:
        bool: True if filename is valid, False otherwise
    """
    # Generate a secure filename
    secure_name = secure_filename(filename)
    
    # If the secure name is empty or different from original, it might have had unsafe characters
    return secure_name and secure_name == filename
