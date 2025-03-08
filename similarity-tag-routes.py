# Add these route imports to app.py
from flask import jsonify
from models import DocumentSimilarity, Tag
from utils.similarity_analyzer import calculate_document_similarities, get_similarity_network_data

# Add to app.py in the routes section

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

# Routes for tag management
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

# Update the view_document route to include similar documents and all tags
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
