import os
import uuid
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from config import Config
from models import db, Document, Paragraph, document_paragraph
from utils.pdf_extractor import extract_text_from_pdf, generate_pdf_preview
from utils.docx_extractor import extract_text_from_docx, generate_docx_preview
from utils.excel_exporter import generate_excel_report
from utils.paragraph_processor import download_spacy_resources, process_paragraphs


def fix_database_schema(app):
    """Ensure the database schema is updated properly."""
    with app.app_context():
        # First, check if the column exists
        try:
            db.session.execute(db.text("SELECT preview_data FROM document LIMIT 1"))
            app.logger.info("preview_data column already exists")
            db.session.commit()
            return True
        except Exception:
            # Column doesn't exist, let's create it
            app.logger.info("preview_data column doesn't exist, attempting to add it")
            db.session.rollback()
            
            try:
                # Different approach for SQLite
                db.session.execute(db.text("ALTER TABLE document ADD COLUMN preview_data TEXT"))
                db.session.commit()
                app.logger.info("Added preview_data column successfully")
                return True
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error adding preview_data column: {str(e)}")
                
                # If direct ALTER TABLE fails, try the more complex approach
                try:
                    # This is a more involved way to add a column in SQLite
                    # 1. Rename the existing table
                    db.session.execute(db.text("ALTER TABLE document RENAME TO document_old"))
                    
                    # 2. Create a new table with the desired schema
                    db.session.execute(db.text("""
                        CREATE TABLE document (
                            id INTEGER NOT NULL, 
                            filename VARCHAR(255) NOT NULL, 
                            original_filename VARCHAR(255) NOT NULL, 
                            file_type VARCHAR(10) NOT NULL, 
                            file_size INTEGER NOT NULL, 
                            upload_date DATETIME, 
                            extracted_text TEXT, 
                            status VARCHAR(20), 
                            error_message TEXT, 
                            page_count INTEGER, 
                            paragraph_count INTEGER,
                            preview_image_path VARCHAR(255),
                            preview_data TEXT,
                            PRIMARY KEY (id)
                        )
                    """))
                    
                    # 3. Copy data from old table to new table
                    db.session.execute(db.text("""
                        INSERT INTO document 
                        (id, filename, original_filename, file_type, file_size, 
                         upload_date, extracted_text, status, error_message, 
                         page_count, paragraph_count, preview_image_path)
                        SELECT 
                        id, filename, original_filename, file_type, file_size, 
                        upload_date, extracted_text, status, error_message, 
                        page_count, paragraph_count, preview_image_path
                        FROM document_old
                    """))
                    
                    # 4. Drop the old table
                    db.session.execute(db.text("DROP TABLE document_old"))
                    
                    # 5. Commit changes
                    db.session.commit()
                    app.logger.info("Successfully rebuilt document table with preview_data column")
                    return True
                except Exception as rebuild_error:
                    db.session.rollback()
                    app.logger.error(f"Failed to rebuild table: {str(rebuild_error)}")
                    return False


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Ensure necessary directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PREVIEW_FOLDER'], exist_ok=True)  # Create preview folder
    os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(app.instance_path)), exist_ok=True)
    
    # Initialize database
    db.init_app(app)
    
    # Setup logging
    if not app.debug:
        file_handler = RotatingFileHandler(app.config['LOG_FILE'], maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Document Analyzer starting up')
    
    # Fix database schema before continuing
    fix_database_schema(app)
    
    with app.app_context():
        # Add new columns to the existing database table if they don't exist
        try:
            db.session.execute(db.text("ALTER TABLE document ADD COLUMN page_count INTEGER DEFAULT 0"))
            app.logger.info("Added new column: page_count")
        except Exception as e:
            db.session.rollback()
            app.logger.info(f"Column page_count not added: {str(e)}")
            
        try:
            db.session.execute(db.text("ALTER TABLE document ADD COLUMN paragraph_count INTEGER DEFAULT 0"))
            app.logger.info("Added new column: paragraph_count")
        except Exception as e:
            db.session.rollback()
            app.logger.info(f"Column paragraph_count not added: {str(e)}")
        
        # Create any missing tables
        db.create_all()
        
        # Download spaCy resources
        try:
            download_spacy_resources()
        except Exception as e:
            app.logger.error(f"Error downloading spaCy resources: {str(e)}")
            app.logger.warning("Paragraph processing may have reduced functionality")
    
    # Helper function to check allowed file extensions
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    
    # Routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/upload', methods=['GET', 'POST'])
    def upload():
        if request.method == 'POST':
            # Check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part', 'error')
                return redirect(request.url)
            
            files = request.files.getlist('file')
            
            if not files or files[0].filename == '':
                flash('No selected file', 'error')
                return redirect(request.url)
            
            successful_uploads = 0
            for file in files:
                if file and allowed_file(file.filename):
                    # Generate a unique filename
                    original_filename = secure_filename(file.filename)
                    file_type = original_filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"{str(uuid.uuid4())}_{original_filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    # Save the file
                    file.save(file_path)
                    app.logger.info(f"File saved: {file_path}")
                    
                    # Create a new document record
                    document = Document(
                        filename=unique_filename,
                        original_filename=original_filename,
                        file_type=file_type,
                        file_size=os.path.getsize(file_path)
                    )
                    
                    # Extract text based on file type
                    try:
                        if file_type == 'pdf':
                            text, page_count = extract_text_from_pdf(file_path)
                            # Generate PDF preview for multiple pages
                            preview_info = generate_pdf_preview(file_path, app.config['PREVIEW_FOLDER'])
                        elif file_type == 'docx':
                            text, page_count = extract_text_from_docx(file_path)
                            # Generate DOCX preview for multiple sections
                            preview_info = generate_docx_preview(file_path, app.config['PREVIEW_FOLDER'])
                        else:
                            raise ValueError(f"Unsupported file type: {file_type}")
                        
                        document.extracted_text = text
                        document.page_count = page_count
                        document.status = 'processed'
                        
                        # Save preview information as JSON
                        if preview_info:
                            # Store in preview_data column
                            document.preview_data = json.dumps(preview_info)
                            
                            # For backwards compatibility also store the first page in preview_image_path
                            first_page_filename = preview_info['preview_format'].format(
                                base=preview_info['base_filename'],
                                page=1
                            )
                            document.preview_image_path = first_page_filename
                        
                        # Save the document to get an ID before processing paragraphs
                        db.session.add(document)
                        db.session.commit()
                        
                        # Process paragraphs
                        paragraph_count = process_paragraphs(text, document, db.session)
                        document.paragraph_count = paragraph_count
                        app.logger.info(f"Found {paragraph_count} paragraphs in {page_count} pages for document {document.original_filename}")
                        db.session.commit()
                        
                        successful_uploads += 1
                    except Exception as e:
                        app.logger.error(f"Error processing file {original_filename}: {str(e)}")
                        document.status = 'error'
                        document.error_message = str(e)
                        db.session.add(document)
                        db.session.commit()
                else:
                    flash(f'Invalid file type for {file.filename}. Only PDF and DOCX files are allowed.', 'error')
            
            if successful_uploads > 0:
                flash(f'{successful_uploads} file(s) uploaded and processed successfully', 'success')
            
            return redirect(url_for('documents'))
        
        return render_template('upload.html')
    
    @app.route('/documents')
    def documents():
        documents = Document.query.order_by(Document.upload_date.desc()).all()
        return render_template('documents.html', documents=documents)
    
    @app.route('/document/delete/<int:id>', methods=['POST'])
    def delete_document(id):
        """Delete a document and remove any orphaned paragraphs."""
        document = Document.query.get_or_404(id)
        
        # Store original filename for flash message
        original_filename = document.original_filename
        
        # Get the stored filename to delete the physical file later
        filename = document.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Delete preview images if they exist
        preview_info = document.get_preview_info()
        if preview_info:
            total_pages = preview_info.get('total_pages', 0)
            for page in range(1, total_pages + 1):
                preview_filename = document.get_preview_filename(page)
                if preview_filename:
                    preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
                    if os.path.exists(preview_path):
                        try:
                            os.remove(preview_path)
                            app.logger.info(f"Deleted preview image: {preview_path}")
                        except Exception as e:
                            app.logger.error(f"Error deleting preview image {preview_path}: {str(e)}")
        
        # First, record all paragraphs associated with this document before deletion
        paragraphs_to_check = list(document.paragraphs)
        
        # Remove the document from the database (will remove associations in junction table)
        db.session.delete(document)
        db.session.commit()
        
        # Now check if any of those paragraphs need to be deleted
        paragraphs_deleted = 0
        for paragraph in paragraphs_to_check:
            # Reload the paragraph to get its current associations
            paragraph = Paragraph.query.get(paragraph.id)
            if paragraph and not paragraph.documents:
                # If paragraph has no document associations, delete it
                db.session.delete(paragraph)
                paragraphs_deleted += 1
        
        db.session.commit()
        
        # Delete the physical file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                app.logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                app.logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        flash(f'Document "{original_filename}" deleted successfully. {paragraphs_deleted} unique paragraphs were also removed.', 'success')
        return redirect(url_for('documents'))
    
    @app.route('/documents/delete-all', methods=['POST'])
    def delete_all_documents():
        """Delete all documents and paragraphs from the database and file system."""
        try:
            # Get all documents for file deletion
            documents = Document.query.all()
            
            # Count documents for flash message
            document_count = len(documents)
            
            # Delete all physical files and preview images
            deleted_files = 0
            deleted_previews = 0
            for document in documents:
                # Delete document file
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files += 1
                        app.logger.info(f"Deleted file: {file_path}")
                    except Exception as e:
                        app.logger.error(f"Error deleting file {file_path}: {str(e)}")
                
                # Delete preview images
                preview_info = document.get_preview_info()
                if preview_info:
                    total_pages = preview_info.get('total_pages', 0)
                    for page in range(1, total_pages + 1):
                        preview_filename = document.get_preview_filename(page)
                        if preview_filename:
                            preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
                            if os.path.exists(preview_path):
                                try:
                                    os.remove(preview_path)
                                    deleted_previews += 1
                                    app.logger.info(f"Deleted preview image: {preview_path}")
                                except Exception as e:
                                    app.logger.error(f"Error deleting preview image {preview_path}: {str(e)}")
            
            # Get paragraph count for flash message
            paragraph_count = Paragraph.query.count()
            
            # Delete all document-paragraph associations, documents, and paragraphs
            # Note: Using raw SQL for efficiency with large datasets
            db.session.execute(document_paragraph.delete())
            db.session.execute(db.delete(Document))
            db.session.execute(db.delete(Paragraph))
            
            db.session.commit()
            
            app.logger.info(f"Deleted all {document_count} documents, {deleted_files} files, {deleted_previews} previews, and {paragraph_count} paragraphs")
            flash(f'Successfully deleted all {document_count} documents, {deleted_files} files, {deleted_previews} preview images, and {paragraph_count} paragraphs.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error deleting all documents: {str(e)}")
            flash(f'Error deleting all documents: {str(e)}', 'error')
        
        return redirect(url_for('documents'))
    
    @app.route('/document/<int:id>')
    def view_document(id):
        document = Document.query.get_or_404(id)
        
        # Get the current page from query parameters (default to page 1)
        current_page = request.args.get('page', 1, type=int)
        
        # Get total preview pages available
        total_pages = document.get_preview_count()
        
        # Validate current_page
        if current_page < 1 or current_page > total_pages:
            current_page = 1
        
        return render_template('view.html', 
                            document=document, 
                            current_page=current_page,
                            total_pages=total_pages)
    
    # Add a route to serve preview images
    @app.route('/preview/<filename>')
    def preview_image(filename):
        return send_from_directory(app.config['PREVIEW_FOLDER'], filename)
    
    @app.route('/paragraphs')
    def view_paragraphs():
        paragraphs = Paragraph.query.all()
        # Get paragraphs that appear in multiple documents
        shared_paragraphs = [p for p in paragraphs if len(p.documents) > 1]
        # Sort by number of documents (most shared first)
        shared_paragraphs.sort(key=lambda p: len(p.documents), reverse=True)
        return render_template('paragraphs.html', 
                               paragraphs=paragraphs, 
                               shared_paragraphs=shared_paragraphs)
    
    @app.route('/export')
    def export():
        documents = Document.query.filter_by(status='processed').all()
        
        if not documents:
            flash('No processed documents to export', 'error')
            return redirect(url_for('documents'))
        
        try:
            report_filename = generate_excel_report(documents, app.config['UPLOAD_FOLDER'])
            flash('Excel report generated successfully', 'success')
            return redirect(url_for('download_report', filename=report_filename))
        except Exception as e:
            app.logger.error(f"Error generating Excel report: {str(e)}")
            flash(f'Error generating Excel report: {str(e)}', 'error')
            return redirect(url_for('documents'))
    
    @app.route('/export_paragraphs')
    def export_paragraphs():
        documents = Document.query.filter_by(status='processed').all()
        
        if not documents:
            flash('No processed documents to export', 'error')
            return redirect(url_for('view_paragraphs'))
        
        try:
            report_filename = generate_excel_report(documents, app.config['UPLOAD_FOLDER'])
            flash('Excel report with paragraphs generated successfully', 'success')
            return redirect(url_for('download_report', filename=report_filename))
        except Exception as e:
            app.logger.error(f"Error generating Excel report: {str(e)}")
            flash(f'Error generating Excel report: {str(e)}', 'error')
            return redirect(url_for('view_paragraphs'))
    
    @app.route('/download/<filename>')
    def download_report(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    
    @app.route('/logs')
    def logs():
        log_dir = app.config['LOG_FOLDER']
        log_files = [f for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
        
        # Read current log file
        try:
            with open(app.config['LOG_FILE'], 'r') as f:
                log_contents = f.readlines()
        except FileNotFoundError:
            log_contents = ["No log file found."]
        
        return render_template('logs.html', log_files=log_files, log_contents=log_contents)
    
    @app.route('/logs/<filename>')
    def view_log(filename):
        log_dir = app.config['LOG_FOLDER']
        log_path = os.path.join(log_dir, filename)
        
        if not os.path.exists(log_path):
            flash('Log file not found', 'error')
            return redirect(url_for('logs'))
        
        try:
            with open(log_path, 'r') as f:
                log_contents = f.readlines()
        except Exception as e:
            log_contents = [f"Error reading log file: {str(e)}"]
        
        return render_template('view_log.html', filename=filename, log_contents=log_contents)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
