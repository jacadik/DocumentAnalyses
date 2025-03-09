from sqlalchemy import func, and_, or_
from models import db, Document, Paragraph, document_paragraph, Tag, DocumentSimilarity

def get_shared_paragraphs(order_by_count=True):
    """
    Get paragraphs that appear in multiple documents, more efficiently.
    
    Args:
        order_by_count (bool): Whether to order by document count
    
    Returns:
        list: List of Paragraph objects with count > 1
    """
    # First, create a subquery to count documents per paragraph
    paragraph_counts = db.session.query(
        document_paragraph.c.paragraph_id,
        func.count(document_paragraph.c.document_id).label('doc_count')
    ).group_by(document_paragraph.c.paragraph_id).subquery()
    
    # Then join with Paragraph table and filter for count > 1
    query = Paragraph.query.join(
        paragraph_counts,
        Paragraph.id == paragraph_counts.c.paragraph_id
    ).filter(paragraph_counts.c.doc_count > 1)
    
    # Order by count if requested
    if order_by_count:
        query = query.order_by(paragraph_counts.c.doc_count.desc())
    
    return query.all()

def get_paragraphs_with_counts():
    """
    Get all paragraphs with their document counts.
    
    Returns:
        list: List of (Paragraph, count) tuples
    """
    # Create a subquery to count documents per paragraph
    paragraph_counts = db.session.query(
        document_paragraph.c.paragraph_id,
        func.count(document_paragraph.c.document_id).label('doc_count')
    ).group_by(document_paragraph.c.paragraph_id).subquery()
    
    # Join with Paragraph table and select both paragraph and count
    results = db.session.query(
        Paragraph, 
        paragraph_counts.c.doc_count
    ).join(
        paragraph_counts,
        Paragraph.id == paragraph_counts.c.paragraph_id
    ).order_by(paragraph_counts.c.doc_count.desc()).all()
    
    return results

def check_tag_name_exists(name, exclude_id=None):
    """
    Check if a tag name exists, optionally excluding a specific tag.
    
    Args:
        name (str): Tag name to check
        exclude_id (int): Optional tag ID to exclude from check
        
    Returns:
        bool: True if tag name exists, False otherwise
    """
    query = Tag.query.filter(Tag.name == name)
    
    if exclude_id:
        query = query.filter(Tag.id != exclude_id)
    
    return query.first() is not None

def get_documents_with_tag(tag_id):
    """
    Get all documents with a specific tag.
    
    Args:
        tag_id (int): Tag ID to filter by
        
    Returns:
        list: List of Document objects
    """
    tag = Tag.query.get(tag_id)
    if not tag:
        return []
    
    return tag.documents.all()

def get_similar_documents(document_id, min_score=0.3, limit=5):
    """
    Get documents similar to the specified document.
    
    Args:
        document_id (int): Document ID to find similar documents for
        min_score (float): Minimum similarity score (0.0-1.0)
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of (Document, score) tuples
    """
    # Get similarities where document is source
    outgoing = db.session.query(Document, DocumentSimilarity.similarity_score)\
        .join(DocumentSimilarity, DocumentSimilarity.target_id == Document.id)\
        .filter(
            DocumentSimilarity.source_id == document_id, 
            DocumentSimilarity.similarity_score >= min_score
        )\
        .order_by(DocumentSimilarity.similarity_score.desc())
        
    # Get similarities where document is target
    incoming = db.session.query(Document, DocumentSimilarity.similarity_score)\
        .join(DocumentSimilarity, DocumentSimilarity.source_id == Document.id)\
        .filter(
            DocumentSimilarity.target_id == document_id, 
            DocumentSimilarity.similarity_score >= min_score
        )\
        .order_by(DocumentSimilarity.similarity_score.desc())
        
    # Combine results, sort by score, remove duplicates
    combined_results = []
    seen_ids = set()
    
    for doc, score in outgoing.all() + incoming.all():
        if doc.id != document_id and doc.id not in seen_ids:
            seen_ids.add(doc.id)
            combined_results.append((doc, score))
            
            if len(combined_results) >= limit:
                break
    
    # Sort by score (highest first)
    combined_results.sort(key=lambda x: x[1], reverse=True)
    
    return combined_results

def get_document_paragraph_counts():
    """
    Get counts of how many documents contain each paragraph.
    
    Returns:
        dict: Dictionary mapping paragraph_id to document count
    """
    counts = db.session.query(
        document_paragraph.c.paragraph_id,
        func.count(document_paragraph.c.document_id).label('count')
    ).group_by(document_paragraph.c.paragraph_id).all()
    
    return {row[0]: row[1] for row in counts}
