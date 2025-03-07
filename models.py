from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

    def __repr__(self):
        return f'<Document {self.original_filename}>'
