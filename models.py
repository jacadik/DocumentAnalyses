from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json
import os

db = SQLAlchemy()

# Association table for many-to-many relationship between documents and paragraphs
document_paragraph = db.Table('document_paragraph',
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
    db.Column('paragraph_id', db.Integer, db.ForeignKey('paragraph.id'), primary_key=True)
)

# Association table for document similarities
class DocumentSimilarity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)  # 0.0 to 1.0
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    source = db.relationship('Document', foreign_keys=[source_id], backref='outgoing_similarities')
    target = db.relationship('Document', foreign_keys=[target_id], backref='incoming_similarities')
    
    # Add a constraint to prevent duplicate pairs
    __table_args__ = (
        db.UniqueConstraint('source_id', 'target_id', name='unique_document_pair'),
    )

# Association table for many-to-many relationship between documents and tags
document_tag = db.Table('document_tag',
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

# Association table for many-to-many relationship between paragraphs and tags
paragraph_tag = db.Table('paragraph_tag',
    db.Column('paragraph_id', db.Integer, db.ForeignKey('paragraph.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(7), default="#6c757d")  # Default color as hex color code
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', secondary=document_tag, 
                               backref=db.backref('tags', lazy='dynamic'))
    paragraphs = db.relationship('Paragraph', secondary=paragraph_tag, 
                                backref=db.backref('tags', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Tag {self.name}>'

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
    
    # Store preview data as JSON
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
                    'document_page_count': self.page_count or 1,
                    'file_type': self.file_type
                }
            return None
        try:
            return json.loads(self.preview_data)
        except:
            return None
            
    def get_preview_filename(self, page=1):
        """
        For compatibility with existing templates, returns a filename
        that will be used with the preview_image route.
        
        This now constructs a filename that our preview_image route can parse
        to extract the document_id and page_number for on-demand generation.
        """
        preview_info = self.get_preview_info()
        if not preview_info:
            return None
            
        try:
            # Check if the requested page is valid
            if page < 1 or page > preview_info.get('document_page_count', 0):
                page = 1
                
            # Return a URL-friendly string that the preview_image route will understand
            return f"document_{self.id}_page_{page}.png"
        except:
            return None
    
    def get_preview_count(self):
        """Get the total number of pages available for preview."""
        preview_info = self.get_preview_info()
        if not preview_info:
            return 0
        return preview_info.get('document_page_count', 0)
        
    def get_file_type_from_preview_info(self):
        """Get the file type from preview info or fallback to the document's file_type."""
        preview_info = self.get_preview_info()
        if preview_info and 'file_type' in preview_info:
            return preview_info['file_type']
        return self.file_type
        
    def get_tags(self):
        """Get all tags associated with this document."""
        return self.tags.all()
        
    def get_similar_documents(self, min_score=0.3, limit=5):
        """Get documents similar to this one."""
        outgoing = db.session.query(Document, DocumentSimilarity.similarity_score)\
            .join(DocumentSimilarity, DocumentSimilarity.target_id == Document.id)\
            .filter(DocumentSimilarity.source_id == self.id, 
                    DocumentSimilarity.similarity_score >= min_score)\
            .order_by(DocumentSimilarity.similarity_score.desc())\
            .limit(limit).all()
            
        incoming = db.session.query(Document, DocumentSimilarity.similarity_score)\
            .join(DocumentSimilarity, DocumentSimilarity.source_id == Document.id)\
            .filter(DocumentSimilarity.target_id == self.id, 
                    DocumentSimilarity.similarity_score >= min_score)\
            .order_by(DocumentSimilarity.similarity_score.desc())\
            .limit(limit).all()
            
        # Combine and sort by similarity score
        similar_docs = outgoing + incoming
        similar_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Remove duplicates and limit to requested number
        seen_ids = set()
        result = []
        for doc, score in similar_docs:
            if doc.id != self.id and doc.id not in seen_ids:
                seen_ids.add(doc.id)
                result.append((doc, score))
                if len(result) >= limit:
                    break
                    
        return result

    def __repr__(self):
        return f'<Document {self.original_filename}>'

class Paragraph(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    hash = db.Column(db.String(64), nullable=False, unique=True)  # For efficient lookups
    
    # Many-to-many relationship with documents
    documents = db.relationship('Document', secondary=document_paragraph, 
                               back_populates='paragraphs')
    
    def get_tags(self):
        """Get all tags associated with this paragraph."""
        return self.tags.all()
    
    def __repr__(self):
        return f'<Paragraph {self.id}>'