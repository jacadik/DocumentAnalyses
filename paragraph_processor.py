import hashlib
import re
import logging

logger = logging.getLogger(__name__)

def extract_paragraphs(text):
    """
    Extract paragraphs from text.
    
    Args:
        text (str): Text to extract paragraphs from
        
    Returns:
        list: List of paragraph strings
    """
    # Split by double newlines or more to separate paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Clean and filter paragraphs
    result = []
    for p in paragraphs:
        p = p.strip()
        if p and len(p) > 10:  # Skip empty or very short paragraphs
            result.append(p)
    
    return result

def hash_paragraph(paragraph):
    """
    Create a hash for a paragraph to identify duplicates efficiently.
    
    Args:
        paragraph (str): Paragraph text
        
    Returns:
        str: Hexadecimal hash value
    """
    # Normalize the paragraph by removing extra whitespace and converting to lowercase
    normalized = ' '.join(paragraph.split()).lower()
    
    # Create a SHA256 hash
    return hashlib.sha256(normalized.encode()).hexdigest()

def process_paragraphs(text, document, db_session):
    """
    Process text into paragraphs, deduplicate, and associate with document.
    
    Args:
        text (str): Full text from the document
        document (Document): Document object to associate paragraphs with
        db_session (SQLAlchemy.session): Database session
        
    Returns:
        int: Number of paragraphs processed
    """
    from models import Paragraph
    
    # Extract paragraphs from text
    paragraphs = extract_paragraphs(text)
    logger.info(f"Extracted {len(paragraphs)} paragraphs from document {document.original_filename}")
    
    # Process each paragraph
    paragraph_count = 0
    for paragraph_text in paragraphs:
        # Create hash for efficient lookup
        paragraph_hash = hash_paragraph(paragraph_text)
        
        # Check if paragraph already exists
        paragraph = Paragraph.query.filter_by(hash=paragraph_hash).first()
        
        if not paragraph:
            # Create new paragraph if it doesn't exist
            paragraph = Paragraph(
                content=paragraph_text, 
                hash=paragraph_hash
            )
            db_session.add(paragraph)
        
        # Associate paragraph with document if not already associated
        if paragraph not in document.paragraphs:
            document.paragraphs.append(paragraph)
            paragraph_count += 1
    
    return paragraph_count
