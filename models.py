from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

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
    
    # Many-to-many relationship with paragraphs
    paragraphs = db.relationship('Paragraph', secondary=document_paragraph, 
                                back_populates='documents')

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