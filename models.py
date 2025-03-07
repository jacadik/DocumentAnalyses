from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

# Association table for many-to-many relationship between documents and paragraphs
document_paragraph = db.Table('document_paragraph',
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
    db.Column('paragraph_id', db.Integer, db.ForeignKey('paragraph.id'), primary_key=True)
)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # Stored filename (UUID-based)
    original_filename = db.Column(db.String(255), nullable=False)  # Original uploaded filename
    file_type = db.Column(db.String(10), nullable=False)  # pdf or docx
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    extracted_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, processed, error
    error_message = db.Column(db.Text, nullable=True)
    page_count = db.Column(db.Integer, default=0)  # Number of pages in the document
    paragraph_count = db.Column(db.Integer, default=0)  # Number of paragraphs identified
    
    # Store preview data as JSON instead of a single path
    preview_data = db.Column(db.Text, nullable=True)  # JSON storage for preview info
    
    # Keep this for backwards compatibility
    preview_image_path = db.Column(db.String(255), nullable=True)  # Legacy field
    
    # Many-to-many relationship with paragraphs
    paragraphs = db.relationship('Paragraph', secondary=document_paragraph, 
                                back_populates='documents')

    def get_preview_info(self):
        """Return preview information as a dictionary."""
        if not self.preview_data:
            # Fallback to legacy preview_image_path if preview_data is not set
            if self.preview_image_path:
                return {
                    'base_filename': self.preview_image_path.split('_preview.')[0],
                    'total_pages': 1,
                    'preview_format': self.preview_image_path
                }
            return None
        try:
            return json.loads(self.preview_data)
        except:
            return None
            
    def get_preview_filename(self, page=1):
        """Get the filename for a specific preview page."""
        preview_info = self.get_preview_info()
        if not preview_info:
            return None
            
        try:
            # Legacy compatibility: if preview_format is a full filename (not a format string)
            if '{' not in preview_info.get('preview_format', ''):
                return preview_info.get('preview_format')
                
            # Check if the requested page exists
            if page < 1 or page > preview_info.get('total_pages', 0):
                page = 1
                
            # Generate the filename using the format string
            return preview_info['preview_format'].format(
                base=preview_info['base_filename'],
                page=page
            )
        except:
            return None
    
    def get_preview_count(self):
        """Get the total number of preview pages available."""
        preview_info = self.get_preview_info()
        if not preview_info:
            return 0
        return preview_info.get('total_pages', 0)

    def __repr__(self):
        return f'<Document {self.original_filename}>'

class Paragraph(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    hash = db.Column(db.String(64), nullable=False, unique=True)  # For efficient lookups
    
    # Many-to-many relationship with documents
    documents = db.relationship('Document', secondary=document_paragraph, 
                               back_populates='paragraphs')
    
    def __repr__(self):
        return f'<Paragraph {self.id}>'