from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from models import db, Document, Paragraph, Tag
from utils.query_helpers import get_shared_paragraphs, get_paragraphs_with_counts, get_document_paragraph_counts
from utils.excel_exporter import generate_excel_report

# Create blueprint
bp = Blueprint('paragraphs', __name__)

@bp.route('/')
def list():
    """View paragraph analysis page."""
    # Get paragraphs and document counts using optimized query
    paragraphs_with_counts = get_paragraphs_with_counts()
    
    # Split into paragraphs and counts
    paragraphs = [p for p, _ in paragraphs_with_counts]
    
    # Get shared paragraphs (more efficiently)
    shared_paragraphs = get_shared_paragraphs(order_by_count=True)
    
    return render_template('paragraphs.html', 
                           paragraphs=paragraphs, 
                           shared_paragraphs=shared_paragraphs)

@bp.route('/export')
def export():
    """Export paragraphs to Excel."""
    documents = Document.query.filter_by(status='processed').all()
    
    if not documents:
        flash('No processed documents to export', 'error')
        return redirect(url_for('paragraphs.list'))
    
    try:
        report_filename = generate_excel_report(documents, current_app.config['UPLOAD_FOLDER'])
        flash('Excel report with paragraphs generated successfully', 'success')
        return redirect(url_for('documents.download_report', filename=report_filename))
    except Exception as e:
        current_app.logger.exception(f"Error generating Excel report: {str(e)}")
        flash(f'Error generating Excel report: {str(e)}', 'error')
        return redirect(url_for('paragraphs.list'))

@bp.route('/<int:id>/tag', methods=['POST'])
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
        return redirect(url_for('documents.view', id=document_id))
    else:
        return redirect(url_for('paragraphs.list'))

@bp.route('/<int:id>/tags')
def get_paragraph_tags(id):
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

@bp.route('/find-similar', methods=['POST'])
def find_similar():
    """Find paragraphs similar to the provided text."""
    from utils.similarity_analyzer import find_similar_paragraphs
    
    # Get text from request
    text = request.form.get('text', '')
    min_similarity = float(request.form.get('min_similarity', 0.7))
    
    if not text or len(text.strip()) < 10:
        return jsonify({
            'success': False,
            'message': 'Please provide more text for analysis',
            'results': []
        })
        
    # Find similar paragraphs
    results = find_similar_paragraphs(text, Paragraph, min_similarity, limit=10)
    
    # Format results for JSON response
    formatted_results = []
    for para, score in results:
        # Get document names
        doc_names = [doc.original_filename for doc in para.documents]
        
        formatted_results.append({
            'id': para.id,
            'content': para.content,
            'similarity': float(score),
            'similarity_percent': round(float(score) * 100, 1),
            'documents': doc_names,
            'document_count': len(doc_names)
        })
    
    return jsonify({
        'success': True,
        'message': f'Found {len(results)} similar paragraphs',
        'results': formatted_results
    })
