import os
import uuid
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, Response, jsonify
from werkzeug.utils import secure_filename
from config import Config
from models import db, Document, Paragraph, document_paragraph, DocumentSimilarity, Tag
from utils.pdf_extractor import extract_text_from_pdf, create_pdf_preview_info, generate_page_preview
from utils.docx_extractor import extract_text_from_docx, create_docx_preview_info, generate_section_preview
from utils.excel_exporter import generate_excel_report
from utils.paragraph_processor import download_spacy_resources, process_paragraphs
from utils.similarity_analyzer import calculate_document_similarities, get_similarity_network_data


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
                            # Just create preview info without generating images
                            preview_info = create_pdf_preview_info(file_path)
                        elif file_type == 'docx':
                            text, page_count = extract_text_from_docx(file_path)
                            # Just create preview info without generating images
                            preview_info = create_docx_preview_info(file_path, page_count)
                        else:
                            raise ValueError(f"Unsupported file type: {file_type}")
                        
                        document.extracted_text = text
                        document.page_count = page_count
                        document.status = 'processed'
                        
                        # Save preview information as JSON (without generating any images)
                        if preview_info:
                            document.preview_data = json.dumps(preview_info)
                        
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
    
    @app.route('/generate-preview/<int:document_id>/<int:page_number>')
    def generate_preview(document_id, page_number):
        """Generate a preview image for a specific document page in memory."""
        document = Document.query.get_or_404(document_id)
        
        # Get the file type from preview info
        file_type = document.get_file_type_from_preview_info()
        
        # Get the full path to the document file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.filename)
        
        # Generate the appropriate preview in memory
        if file_type == 'pdf':
            img_data, mimetype = generate_page_preview(document, page_number, file_path)
        else:  # Default to docx
            img_data, mimetype = generate_section_preview(document, page_number, file_path)
        
        if not img_data:
            return abort(404)
            
        # Return the image data directly
        return Response(img_data, mimetype=mimetype)
    
    # Add a route to handle direct preview requests (legacy compatibility)
    @app.route('/preview/<path:filename>')
    def preview_image(filename):
        """
        Legacy route to maintain compatibility with existing templates.
        Now just redirects to generate_preview with appropriate parameters.
        """
        # Try to extract document_id and page_number from filename
        # This is a best-effort conversion from old format to new
        try:
            # Expected format example: "document_1_page_2.png"
            parts = filename.split('_')
            if len(parts) >= 4:
                doc_index = parts.index('document') if 'document' in parts else -1
                page_index = parts.index('page') if 'page' in parts else -1
                
                if doc_index >= 0 and page_index >= 0 and doc_index + 1 < len(parts) and page_index + 1 < len(parts):
                    document_id = int(parts[doc_index + 1])
                    page_number = int(parts[page_index + 1])
                    return redirect(url_for('generate_preview', document_id=document_id, page_number=page_number))
            
            # If we can't parse the filename, check if it's a base filename without page info
            # In this case, redirect to page 1
            # Example: "abc123_preview.png"
            if '_preview.' in filename:
                base_filename = filename.split('_preview.')[0]
                document = Document.query.filter_by(filename=base_filename).first()
                if document:
                    return redirect(url_for('generate_preview', document_id=document.id, page_number=1))
        except Exception as e:
            app.logger.error(f"Error parsing legacy preview filename {filename}: {str(e)}")
        
        # If we can't handle the request, return 404
        return abort(404)
    
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
    
    @app.route('/documents/delete-all', methods=['POST'])
    def delete_all_documents():
        """Delete all documents and paragraphs from the database and file system."""
        try:
            # Get all documents for file deletion
            documents = Document.query.all()
            
            # Count documents for flash message
            document_count = len(documents)
            
            # Delete all physical files only (no previews to delete)
            deleted_files = 0
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
            
            # Get paragraph count for flash message
            paragraph_count = Paragraph.query.count()
            
            # Delete all document-paragraph associations, documents, and paragraphs
            # Note: Using raw SQL for efficiency with large datasets
            db.session.execute(document_paragraph.delete())
            db.session.execute(db.delete(Document))
            db.session.execute(db.delete(Paragraph))
            
            db.session.commit()
            
            app.logger.info(f"Deleted all {document_count} documents, {deleted_files} files, and {paragraph_count} paragraphs")
            flash(f'Successfully deleted all {document_count} documents, {deleted_files} files, and {paragraph_count} paragraphs.', 'success')
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
        
        # Get similar documents
        similar_documents = document.get_similar_documents(min_score=0.3, limit=5)
        
        # Get all tags for the tag management modal
        all_tags = Tag.query.order_by(Tag.name).all()
        
        return render_template('view.html', 
                            document=document, 
                            current_page=current_page,
                            total_pages=total_pages,
                            similar_documents=similar_documents,
                            all_tags=all_tags)
    
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
    
    # Content Similarity Map and Document Comparison Routes
    @app.route('/similarity-map')
    def similarity_map():
        """Display document similarity map visualization."""
        documents = Document.query.filter_by(status='processed').all()
        
        # Count similarities to see if we need to calculate them
        similarity_count = DocumentSimilarity.query.count()
        
        # Get all document similarity relationships
        similarities = DocumentSimilarity.query.order_by(DocumentSimilarity.similarity_score.desc()).all()
        
        # Format data for D3.js visualization if we have similarities
        visualization_data = {}
        if similarity_count > 0:
            visualization_data = get_similarity_network_data(Document, DocumentSimilarity)
        
        return render_template('similarity_map.html', 
                              documents=documents,
                              similarities=similarities,
                              visualization_data=visualization_data,
                              similarity_count=similarity_count)

    @app.route('/calculate-similarities', methods=['POST'])
    def calculate_similarities():
        """Calculate and store document similarities."""
        try:
            min_similarity = float(request.form.get('min_similarity', 0.3))
            min_similarity = max(0.1, min(0.9, min_similarity))  # Constrain to reasonable range
            
            pairs_added = calculate_document_similarities(db, Document, DocumentSimilarity, min_similarity)
            
            if pairs_added is False:
                flash('Not enough documents to calculate similarities (need at least 2)', 'warning')
            else:
                flash(f'Similarity calculation complete. Found {pairs_added} significant document relationships.', 'success')
        except Exception as e:
            app.logger.error(f"Error calculating similarities: {str(e)}")
            flash(f'Error calculating similarities: {str(e)}', 'error')
        
        return redirect(url_for('similarity_map'))

    @app.route('/compare-documents/<int:doc1>/<int:doc2>')
    def compare_documents(doc1, doc2):
        """Compare two documents side by side."""
        # Get the documents
        document1 = Document.query.get_or_404(doc1)
        document2 = Document.query.get_or_404(doc2)
        
        # Get similarity score if available
        similarity = DocumentSimilarity.query.filter(
            ((DocumentSimilarity.source_id == doc1) & (DocumentSimilarity.target_id == doc2)) |
            ((DocumentSimilarity.source_id == doc2) & (DocumentSimilarity.target_id == doc1))
        ).first()
        
        similarity_score = similarity.similarity_score if similarity else 0
        
        # Find shared paragraphs
        shared_paragraphs = []
        doc1_paragraphs = set(document1.paragraphs)
        doc2_paragraphs = set(document2.paragraphs)
        shared_paragraphs = list(doc1_paragraphs.intersection(doc2_paragraphs))
        
        # Find unique paragraphs
        unique_to_doc1 = list(doc1_paragraphs - doc2_paragraphs)
        unique_to_doc2 = list(doc2_paragraphs - doc1_paragraphs)
        
        return render_template('compare_documents.html',
                              doc1=document1,
                              doc2=document2,
                              similarity_score=similarity_score,
                              shared_paragraphs=shared_paragraphs,
                              unique_to_doc1=unique_to_doc1,
                              unique_to_doc2=unique_to_doc2)

    # Tag Management Routes
    @app.route('/tags')
    def manage_tags():
        """Display tag management page."""
        tags = Tag.query.order_by(Tag.name).all()
        return render_template('tags.html', tags=tags)

    @app.route('/tags/create', methods=['POST'])
    def create_tag():
        """Create a new tag."""
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6c757d')
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Tag name is required', 'error')
            return redirect(url_for('manage_tags'))
        
        # Check if tag already exists
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            flash(f'Tag "{name}" already exists', 'error')
            return redirect(url_for('manage_tags'))
        
        # Create new tag
        tag = Tag(name=name, color=color, description=description)
        db.session.add(tag)
        db.session.commit()
        
        flash(f'Tag "{name}" created successfully', 'success')
        return redirect(url_for('manage_tags'))

    @app.route('/tags/edit/<int:id>', methods=['POST'])
    def edit_tag(id):
        """Edit an existing tag."""
        tag = Tag.query.get_or_404(id)
        
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6c757d')
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Tag name is required', 'error')
            return redirect(url_for('manage_tags'))
        
        # Check if name is taken by another tag
        existing = Tag.query.filter_by(name=name).first()
        if existing and existing.id != tag.id:
            flash(f'Tag name "{name}" is already in use', 'error')
            return redirect(url_for('manage_tags'))
        
        # Update tag
        tag.name = name
        tag.color = color
        tag.description = description
        db.session.commit()
        
        flash(f'Tag "{name}" updated successfully', 'success')
        return redirect(url_for('manage_tags'))

    @app.route('/tags/delete/<int:id>', methods=['POST'])
    def delete_tag(id):
        """Delete a tag."""
        tag = Tag.query.get_or_404(id)
        name = tag.name
        
        # Remove tag
        db.session.delete(tag)
        db.session.commit()
        
        flash(f'Tag "{name}" deleted successfully', 'success')
        return redirect(url_for('manage_tags'))

    @app.route('/document/<int:id>/tag', methods=['POST'])
    def tag_document(id):
        """Add or remove tags from a document."""
        document = Document.query.get_or_404(id)
        
        # Get selected tag IDs
        tag_ids = request.form.getlist('tag_ids', type=int)
        
        # Get all tags
        tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        
        # Clear existing tags and set new ones
        document.tags = tags
        db.session.commit()
        
        flash(f'Tags updated for "{document.original_filename}"', 'success')
        return redirect(url_for('view_document', id=document.id))

    @app.route('/paragraph/<int:id>/tag', methods=['POST'])
    def tag_paragraph(id):
        """Add or remove tags from a paragraph."""
        paragraph = Paragraph.query.get_or_404(id)
        
        # Get selected tag IDs
        tag_ids = request.form.getlist('tag_ids', type=int)
        
        # Get all tags
        tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        
        # Clear existing tags and set new ones
        paragraph.tags = tags
        db.session.commit()
        
        # Get the document ID for redirect
        document_id = request.form.get('document_id', type=int)
        
        flash('Paragraph tags updated successfully', 'success')
        if document_id:
            return redirect(url_for('view_document', id=document_id))
        else:
            return redirect(url_for('view_paragraphs'))

    @app.route('/api/paragraph/<int:id>/tags')
    def api_paragraph_tags(id):
        """API endpoint to get tags for a paragraph."""
        paragraph = Paragraph.query.get_or_404(id)
        
        # Get all tags and paragraph's tags
        all_tags = Tag.query.order_by(Tag.name).all()
        paragraph_tags = paragraph.get_tags()
        
        # Format as JSON
        return jsonify({
            'paragraph_id': paragraph.id,
            'paragraph_tags': [{'id': t.id, 'name': t.name, 'color': t.color} for t in paragraph_tags],
            'all_tags': [{'id': t.id, 'name': t.name, 'color': t.color, 'description': t.description} for t in all_tags]
        })
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
