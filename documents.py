from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask import send_from_directory, abort, Response, jsonify
from models import db, Document, Paragraph, document_paragraph, Tag
from utils.file_utils import allowed_file, save_uploaded_file
from utils.paragraph_processor import process_paragraphs
from utils.pdf_extractor import extract_text_from_pdf, create_pdf_preview_info
from utils.docx_extractor import extract_text_from_docx, create_docx_preview_info
import os
import json
import uuid

# Create blueprint
bp = Blueprint('documents', __name__)

@bp.route('/')
def index():
    """Render home page."""
    return render_template('index.html')

@bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle document uploads."""
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
            # Process file using utility function
            result = process_uploaded_document(file)
            if result['success']:
                successful_uploads += 1
            else:
                flash(result['message'], 'error')
        
        if successful_uploads > 0:
            flash(f'{successful_uploads} file(s) uploaded and processed successfully', 'success')
        
        return redirect(url_for('documents.list'))
    
    return render_template('upload.html')

@bp.route('/documents')
def list():
    """Display list of all documents."""
    documents = Document.query.order_by(Document.upload_date.desc()).all()
    return render_template('documents.html', documents=documents)

@bp.route('/document/<int:id>')
def view(id):
    """View a specific document."""
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

@bp.route('/document/delete/<int:id>', methods=['POST'])
def delete(id):
    """Delete a document and remove any orphaned paragraphs."""
    document = Document.query.get_or_404(id)
    
    # Store original filename for flash message
    original_filename = document.original_filename
    
    # Get the stored filename to delete the physical file later
    filename = document.filename
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
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
            current_app.logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            current_app.logger.error(f"Error deleting file {file_path}: {str(e)}")
    
    flash(f'Document "{original_filename}" deleted successfully. {paragraphs_deleted} unique paragraphs were also removed.', 'success')
    return redirect(url_for('documents.list'))

@bp.route('/documents/delete-all', methods=['POST'])
def delete_all():
    """Delete all documents and paragraphs from the database and file system."""
    try:
        # Get all documents for file deletion
        documents = Document.query.all()
        
        # Count documents for flash message
        document_count = len(documents)
        
        # Delete all physical files
        deleted_files = 0
        for document in documents:
            # Delete document file
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], document.filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files += 1
                    current_app.logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    current_app.logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        # Get paragraph count for flash message
        paragraph_count = Paragraph.query.count()
        
        # Use a more efficient query approach - delete in the correct order
        db.session.execute(document_paragraph.delete())
        db.session.execute(db.delete(Document))
        db.session.execute(db.delete(Paragraph))
        
        db.session.commit()
        
        current_app.logger.info(f"Deleted all {document_count} documents, {deleted_files} files, and {paragraph_count} paragraphs")
        flash(f'Successfully deleted all {document_count} documents, {deleted_files} files, and {paragraph_count} paragraphs.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all documents: {str(e)}")
        flash(f'Error deleting all documents: {str(e)}', 'error')
    
    return redirect(url_for('documents.list'))

@bp.route('/download/<filename>')
def download_report(filename):
    """Download a generated report file."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@bp.route('/generate-preview/<int:document_id>/<int:page_number>')
def generate_preview(document_id, page_number):
    """Generate a preview image for a specific document page in memory."""
    document = Document.query.get_or_404(document_id)
    
    # Get the file type from preview info
    file_type = document.get_file_type_from_preview_info()
    
    # Get the full path to the document file
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], document.filename)
    
    # Generate the appropriate preview in memory
    if file_type == 'pdf':
        from utils.pdf_extractor import generate_page_preview
        img_data, mimetype = generate_page_preview(document, page_number, file_path)
    else:  # Default to docx
        from utils.docx_extractor import generate_section_preview
        img_data, mimetype = generate_section_preview(document, page_number, file_path)
    
    if not img_data:
        return abort(404)
        
    # Return the image data directly
    return Response(img_data, mimetype=mimetype)

@bp.route('/preview/<path:filename>')
def preview_image(filename):
    """
    Legacy route to maintain compatibility with existing templates.
    Now just redirects to generate_preview with appropriate parameters.
    """
    # Try to extract document_id and page_number from filename
    try:
        # Expected format example: "document_1_page_2.png"
        parts = filename.split('_')
        if len(parts) >= 4:
            doc_index = parts.index('document') if 'document' in parts else -1
            page_index = parts.index('page') if 'page' in parts else -1
            
            if doc_index >= 0 and page_index >= 0 and doc_index + 1 < len(parts) and page_index + 1 < len(parts):
                document_id = int(parts[doc_index + 1])
                page_number = int(parts[page_index + 1])
                return redirect(url_for('documents.generate_preview', document_id=document_id, page_number=page_number))
        
        # If we can't parse the filename, check if it's a base filename without page info
        if '_preview.' in filename:
            base_filename = filename.split('_preview.')[0]
            document = Document.query.filter_by(filename=base_filename).first()
            if document:
                return redirect(url_for('documents.generate_preview', document_id=document.id, page_number=1))
    except Exception as e:
        current_app.logger.error(f"Error parsing legacy preview filename {filename}: {str(e)}")
    
    # If we can't handle the request, return 404
    return abort(404)

@bp.route('/export')
def export():
    """Export documents to Excel report."""
    from utils.excel_exporter import generate_excel_report
    
    documents = Document.query.filter_by(status='processed').all()
    
    if not documents:
        flash('No processed documents to export', 'error')
        return redirect(url_for('documents.list'))
    
    try:
        report_filename = generate_excel_report(documents, current_app.config['UPLOAD_FOLDER'])
        flash('Excel report generated successfully', 'success')
        return redirect(url_for('documents.download_report', filename=report_filename))
    except Exception as e:
        current_app.logger.error(f"Error generating Excel report: {str(e)}")
        flash(f'Error generating Excel report: {str(e)}', 'error')
        return redirect(url_for('documents.list'))

# Helper function for processing uploaded documents
def process_uploaded_document(file):
    """
    Process an uploaded document file.
    
    Args:
        file: The uploaded file object
        
    Returns:
        dict: Result with success status and message
    """
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return {
            'success': False, 
            'message': f"Invalid file type for {file.filename}. Only PDF and DOCX files are allowed."
        }
    
    # Check file size
    if file.content_length and file.content_length > current_app.config['MAX_CONTENT_LENGTH']:
        return {
            'success': False,
            'message': f"File {file.filename} exceeds maximum size limit of {current_app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB"
        }
    
    try:
        # Generate a unique filename
        original_filename = secure_filename(file.filename)
        file_type = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{str(uuid.uuid4())}_{original_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save the file
        file.save(file_path)
        current_app.logger.info(f"File saved: {file_path}")
        
        # Create a new document record
        document = Document(
            filename=unique_filename,
            original_filename=original_filename,
            file_type=file_type,
            file_size=os.path.getsize(file_path)
        )
        
        # Extract text based on file type
        if file_type == 'pdf':
            text, page_count = extract_text_from_pdf(file_path)
            preview_info = create_pdf_preview_info(file_path)
        elif file_type == 'docx':
            text, page_count = extract_text_from_docx(file_path)
            preview_info = create_docx_preview_info(file_path, page_count)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        document.extracted_text = text
        document.page_count = page_count
        document.status = 'processed'
        
        # Save preview information as JSON
        if preview_info:
            document.preview_data = json.dumps(preview_info)
        
        # Save the document to get an ID before processing paragraphs
        db.session.add(document)
        db.session.commit()
        
        # Process paragraphs
        paragraph_count = process_paragraphs(text, document, db.session)
        document.paragraph_count = paragraph_count
        current_app.logger.info(f"Found {paragraph_count} paragraphs in {page_count} pages for document {document.original_filename}")
        db.session.commit()
        
        return {'success': True, 'message': 'Document processed successfully'}
        
    except Exception as e:
        current_app.logger.exception(f"Error processing file {file.filename}")
        
        # Create document with error status if not already created
        if 'document' not in locals():
            document = Document(
                filename=unique_filename if 'unique_filename' in locals() else "error",
                original_filename=original_filename if 'original_filename' in locals() else file.filename,
                file_type=file_type if 'file_type' in locals() else "",
                file_size=os.path.getsize(file_path) if 'file_path' in locals() and os.path.exists(file_path) else 0,
                status='error',
                error_message=str(e)
            )
            db.session.add(document)
        else:
            document.status = 'error'
            document.error_message = str(e)
        
        db.session.commit()
        
        return {'success': False, 'message': f"Error processing {file.filename}: {str(e)}"}
