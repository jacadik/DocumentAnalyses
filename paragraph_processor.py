import hashlib
import re
import logging
import nltk
# Make sure to install nltk: pip install nltk
from nltk.tokenize import sent_tokenize
from nltk.tokenize.punkt import PunktSentenceTokenizer
from nltk.tokenize.texttiling import TextTilingTokenizer
import string
import unicodedata

# Initialize logger
logger = logging.getLogger(__name__)

# Download NLTK resources (add this to app initialization)
# This should be done once at application startup
def download_nltk_resources():
    """Download required NLTK resources."""
    try:
        resources = ['punkt', 'averaged_perceptron_tagger']
        for resource in resources:
            try:
                nltk.data.find(f'tokenizers/{resource}')
            except LookupError:
                nltk.download(resource)
        logger.info("NLTK resources downloaded successfully")
    except Exception as e:
        logger.error(f"Error downloading NLTK resources: {str(e)}")

def preprocess_text(text):
    """
    Clean and normalize text before paragraph extraction.
    
    Args:
        text (str): Raw text from document
        
    Returns:
        str: Preprocessed text
    """
    if not text:
        return ""
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Replace multiple newlines with double newlines (to preserve paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Fix common OCR errors
    text = text.replace('l-', 'i-')  # Common OCR error
    text = text.replace('|', 'I')    # Pipe often confused with I
    
    return text

def extract_paragraphs(text):
    """
    Extract paragraphs from text using more advanced techniques.
    
    Args:
        text (str): Text to extract paragraphs from
        
    Returns:
        list: List of paragraph strings
    """
    if not text:
        return []
    
    # Preprocess the text
    text = preprocess_text(text)
    
    # First attempt: Split by double newlines (typical paragraph markers)
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Process and clean the paragraphs
    result = []
    for p in paragraphs:
        p = p.strip()
        
        # Skip if the paragraph is too short or just punctuation/numbers
        if not p or len(p) < 20:
            continue
            
        # Skip if paragraph is just a number, page number, or header/footer
        if re.match(r'^[\d\s\-\.]+$', p) or re.match(r'^page\s+\d+$', p, re.IGNORECASE):
            continue
            
        # If paragraph is very long, try to split it into smaller paragraphs using TextTiling
        if len(p) > 1000:
            try:
                # Initialize TextTiling tokenizer
                tt = TextTilingTokenizer()
                # Use TextTiling to find logical paragraph breaks in long text
                subtiles = tt.tokenize(p)
                # Add all subtiles as separate paragraphs
                for tile in subtiles:
                    tile = tile.strip()
                    if tile and len(tile) >= 20:
                        result.append(tile)
            except Exception as e:
                # If TextTiling fails, just add the long paragraph as is
                logger.warning(f"TextTiling failed: {str(e)}, using original long paragraph")
                result.append(p)
        else:
            result.append(p)
    
    # If regular paragraph splitting yields few results, try sentence-based approach
    if len(result) <= 2 and len(text) > 300:
        logger.info("Few paragraphs found, trying sentence-based approach")
        sentences = sent_tokenize(text)
        
        # Group sentences into paragraphs (approx. 3-5 sentences per paragraph)
        current_paragraph = []
        sentence_count = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            current_paragraph.append(sentence)
            sentence_count += 1
            
            # Create a new paragraph after 3-5 sentences
            if sentence_count >= 3 and (sentence_count >= 5 or sentence.endswith('.')):
                result.append(' '.join(current_paragraph))
                current_paragraph = []
                sentence_count = 0
        
        # Add any remaining sentences as a paragraph
        if current_paragraph:
            result.append(' '.join(current_paragraph))
    
    return result

def normalize_paragraph(paragraph):
    """
    Normalize paragraph text for more accurate duplicate detection.
    
    Args:
        paragraph (str): Paragraph text
        
    Returns:
        str: Normalized paragraph text
    """
    if not paragraph:
        return ""
    
    # Convert to lowercase
    text = paragraph.lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Remove specific words that don't contribute to meaning (articles, etc.)
    stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were'}
    words = text.split()
    text = ' '.join(word for word in words if word not in stop_words)
    
    return text

def hash_paragraph(paragraph):
    """
    Create a hash for a paragraph to identify duplicates efficiently.
    
    Args:
        paragraph (str): Paragraph text
        
    Returns:
        str: Hexadecimal hash value
    """
    # Normalize the paragraph for consistent hashing
    normalized = normalize_paragraph(paragraph)
    
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
