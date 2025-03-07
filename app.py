import os
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from config import Config
from models import db, Document, Paragraph
from utils.pdf_extractor import extract_text_from_pdf
from utils.docx_extractor import extract_text_from_docx
from utils.excel_exporter import generate_excel_report
from utils.paragraph_processor import process_paragraphs


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Ensure necessary directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
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
    
    with app.app_context():
        db.create_all()
    
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
                            text = extract_text_from_pdf(file_path)
                        elif file_type == 'docx':
                            text = extract_text_from_docx(file_path)
                        else:
                            raise ValueError(f"Unsupported file type: {file_type}")
                        
                        document.extracted_text = text
                        document.status = 'processed'
                        
                        # Save the document to get an ID before processing paragraphs
                        db.session.add(document)
                        db.session.commit()
                        
                        # Process paragraphs
                        paragraph_count = process_paragraphs(text, document, db.session)
                        app.logger.info(f"Found {paragraph_count} paragraphs in document {document.original_filename}")
                        db.session.commit()
                        
                        app.logger.info(f"Processed {paragraph_count} paragraphs for {original_filename}")
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
    
    @app.route('/document/<int:id>')
    def view_document(id):
        document = Document.query.get_or_404(id)
        return render_template('view.html', document=document)
    
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
