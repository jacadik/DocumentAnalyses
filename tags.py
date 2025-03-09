from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from models import db, Tag, Document, Paragraph
from utils.query_helpers import check_tag_name_exists, get_documents_with_tag

# Create blueprint
bp = Blueprint('tags', __name__)

@bp.route('/')
def list():
    """Display tag management page."""
    tags = Tag.query.order_by(Tag.name).all()
    return render_template('tags.html', tags=tags)

@bp.route('/create', methods=['POST'])
def create():
    """Create a new tag."""
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#6c757d')
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Tag name is required', 'error')
        return redirect(url_for('tags.list'))
    
    # Check if tag already exists
    if check_tag_name_exists(name):
        flash(f'Tag "{name}" already exists', 'error')
        return redirect(url_for('tags.list'))
    
    # Create new tag
    tag = Tag(name=name, color=color, description=description)
    db.session.add(tag)
    
    try:
        db.session.commit()
        flash(f'Tag "{name}" created successfully', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error creating tag: {str(e)}")
        flash(f'Error creating tag: {str(e)}', 'error')
    
    return redirect(url_for('tags.list'))

@bp.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    """Edit an existing tag."""
    tag = Tag.query.get_or_404(id)
    
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#6c757d')
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Tag name is required', 'error')
        return redirect(url_for('tags.list'))
    
    # Check if name is taken by another tag
    if check_tag_name_exists(name, exclude_id=tag.id):
        flash(f'Tag name "{name}" is already in use', 'error')
        return redirect(url_for('tags.list'))
    
    # Update tag
    tag.name = name
    tag.color = color
    tag.description = description
    
    try:
        db.session.commit()
        flash(f'Tag "{name}" updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error updating tag: {str(e)}")
        flash(f'Error updating tag: {str(e)}', 'error')
    
    return redirect(url_for('tags.list'))

@bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    """Delete a tag."""
    tag = Tag.query.get_or_404(id)
    name = tag.name
    
    try:
        # Remove tag
        db.session.delete(tag)
        db.session.commit()
        flash(f'Tag "{name}" deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting tag: {str(e)}")
        flash(f'Error deleting tag: {str(e)}', 'error')
    
    return redirect(url_for('tags.list'))

@bp.route('/document/<int:id>', methods=['POST'])
def tag_document(id):
    """Add or remove tags from a document."""
    document = Document.query.get_or_404(id)
    
    # Get selected tag IDs
    tag_ids = request.form.getlist('tag_ids', type=int)
    
    # Get all tags
    tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
    
    # Clear existing tags and set new ones
    document.tags = tags
    
    try:
        db.session.commit()
        flash(f'Tags updated for "{document.original_filename}"', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error updating document tags: {str(e)}")
        flash(f'Error updating tags: {str(e)}', 'error')
    
    return redirect(url_for('documents.view', id=document.id))

@bp.route('/api/all')
def get_all_tags():
    """API endpoint to get all tags."""
    tags = Tag.query.order_by(Tag.name).all()
    
    tag_list = [{
        'id': tag.id,
        'name': tag.name,
        'color': tag.color,
        'description': tag.description,
        'document_count': len(tag.documents),
        'paragraph_count': len(tag.paragraphs)
    } for tag in tags]
    
    return jsonify({
        'tags': tag_list
    })

@bp.route('/api/<int:id>/documents')
def get_tag_documents(id):
    """API endpoint to get documents with this tag."""
    tag = Tag.query.get_or_404(id)
    documents = tag.documents.all()
    
    document_list = [{
        'id': doc.id,
        'filename': doc.original_filename,
        'file_type': doc.file_type,
        'page_count': doc.page_count,
        'paragraph_count': doc.paragraph_count
    } for doc in documents]
    
    return jsonify({
        'tag_id': tag.id,
        'tag_name': tag.name,
        'document_count': len(documents),
        'documents': document_list
    })
