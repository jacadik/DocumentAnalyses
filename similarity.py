from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from models import db, Document, DocumentSimilarity, Paragraph
from utils.similarity_analyzer import calculate_document_similarities, get_similarity_network_data

# Create blueprint
bp = Blueprint('similarity', __name__)

@bp.route('/map')
def map():
    """Display document similarity map visualization."""
    documents = Document.query.filter_by(status='processed').all()
    
    # Count similarities to see if we need to calculate them
    similarity_count = DocumentSimilarity.query.count()
    
    # Get all document similarity relationships
    similarities = DocumentSimilarity.query.order_by(DocumentSimilarity.similarity_score.desc()).all()
    
    # Format data for visualization if we have similarities
    visualization_data = {}
    if similarity_count > 0:
        visualization_data = get_similarity_network_data(Document, DocumentSimilarity)
    
    return render_template('similarity_map.html', 
                          documents=documents,
                          similarities=similarities,
                          visualization_data=visualization_data,
                          similarity_count=similarity_count)

@bp.route('/calculate', methods=['POST'])
def calculate():
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
        current_app.logger.exception(f"Error calculating similarities: {str(e)}")
        flash(f'Error calculating similarities: {str(e)}', 'error')
    
    return redirect(url_for('similarity.map'))

@bp.route('/compare/<int:doc1>/<int:doc2>')
def compare(doc1, doc2):
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
    
    # Find shared paragraphs more efficiently
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

@bp.route('/api/network-data')
def network_data():
    """API endpoint to get similarity network data for visualization."""
    min_similarity = float(request.args.get('min_similarity', 0.3))
    
    visualization_data = get_similarity_network_data(
        Document, 
        DocumentSimilarity,
        min_similarity=min_similarity
    )
    
    return jsonify(visualization_data)

@bp.route('/api/document-similarity/<int:doc_id>')
def document_similarity(doc_id):
    """API endpoint to get similarity data for a specific document."""
    document = Document.query.get_or_404(doc_id)
    min_score = float(request.args.get('min_score', 0.3))
    limit = int(request.args.get('limit', 5))
    
    # Use the model method to get similar documents
    similar_docs = document.get_similar_documents(min_score=min_score, limit=limit)
    
    # Format for JSON response
    result = []
    for doc, score in similar_docs:
        result.append({
            'id': doc.id,
            'filename': doc.original_filename,
            'file_type': doc.file_type,
            'similarity_score': score,
            'similarity_percent': round(score * 100, 1)
        })
    
    return jsonify({
        'document_id': doc_id,
        'similar_documents': result
    })
