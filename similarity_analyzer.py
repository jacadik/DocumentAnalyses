import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

def calculate_document_similarities(db, Document, DocumentSimilarity, min_similarity=0.3):
    """
    Calculate similarity between all documents and store in database.
    Only stores relationships with similarity score >= min_similarity.
    
    Args:
        db: SQLAlchemy database instance
        Document: Document model class
        DocumentSimilarity: DocumentSimilarity model class
        min_similarity: Minimum similarity threshold (0.0-1.0)
        
    Returns:
        int: Number of similarity pairs added, or False if not enough documents
    """
    # Get all processed documents
    documents = Document.query.filter_by(status='processed').all()
    if len(documents) < 2:
        logger.info("Not enough documents to calculate similarities (need at least 2)")
        return False
    
    logger.info(f"Calculating similarities for {len(documents)} documents")
    
    # Extract document IDs and text
    doc_ids = [doc.id for doc in documents]
    doc_texts = [doc.extracted_text for doc in documents]
    
    # Calculate TF-IDF vectors
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    try:
        tfidf_matrix = vectorizer.fit_transform(doc_texts)
    except Exception as e:
        logger.error(f"Error calculating TF-IDF matrix: {str(e)}")
        return False
    
    # Calculate cosine similarity between all document pairs
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # Clear existing similarities
    try:
        db.session.execute(db.delete(DocumentSimilarity))
        db.session.commit()
        logger.info("Existing similarity relationships cleared")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing existing similarities: {str(e)}")
        return False
    
    # Store significant similarities
    pairs_added = 0
    try:
        for i in range(len(documents)):
            for j in range(i+1, len(documents)):  # Only upper triangle to avoid duplicates
                similarity = similarity_matrix[i, j]
                
                # Only store if similarity is above threshold
                if similarity >= min_similarity:
                    sim = DocumentSimilarity(
                        source_id=doc_ids[i],
                        target_id=doc_ids[j],
                        similarity_score=float(similarity)
                    )
                    db.session.add(sim)
                    pairs_added += 1
        
        db.session.commit()
        logger.info(f"Added {pairs_added} document similarity relationships")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error storing similarity relationships: {str(e)}")
        return False
    
    return pairs_added

def get_similarity_network_data(Document, DocumentSimilarity):
    """
    Generate network visualization data for documents and their similarities.
    
    Args:
        Document: Document model class
        DocumentSimilarity: DocumentSimilarity model class
        
    Returns:
        dict: Nodes and links data for visualization
    """
    # Get all processed documents
    documents = Document.query.filter_by(status='processed').all()
    
    # Get all document similarity relationships
    similarities = DocumentSimilarity.query.order_by(DocumentSimilarity.similarity_score.desc()).all()
    
    # Format data for visualization
    nodes = []
    for doc in documents:
        nodes.append({
            'id': doc.id,
            'name': doc.original_filename,
            'paragraphs': doc.paragraph_count,
            'file_type': doc.file_type,
            'size': min(20, max(5, doc.paragraph_count / 5))  # Scale node size based on paragraphs
        })
    
    links = []
    for sim in similarities:
        links.append({
            'source': sim.source_id,
            'target': sim.target_id,
            'similarity': sim.similarity_score,
            'value': sim.similarity_score * 5  # Scale link thickness
        })
    
    return {
        'nodes': nodes,
        'links': links
    }