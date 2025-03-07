import hashlib
import re
import logging
import unicodedata
import spacy
from spacy.lang.en import English
from difflib import SequenceMatcher

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize spaCy NLP pipeline (done on first use)
nlp = None

def download_spacy_resources():
    """
    Download spaCy resources needed for paragraph processing.
    """
    try:
        # Download spaCy model
        try:
            spacy.load("en_core_web_sm")
            logger.info("spaCy model already downloaded")
        except OSError:
            logger.info("Downloading spaCy model en_core_web_sm")
            spacy.cli.download("en_core_web_sm")
            logger.info("spaCy model downloaded successfully")
    except Exception as e:
        logger.error(f"Error downloading spaCy resources: {str(e)}")
        logger.warning("Paragraph processing may have reduced functionality")

# For backward compatibility with any scripts that might import this
download_nltk_resources = download_spacy_resources

def load_nlp():
    """Load the appropriate spaCy model based on availability."""
    try:
        # Try loading the small English model first
        return spacy.load("en_core_web_sm")
    except OSError:
        # If that fails, download and use the English tokenizer only
        logger.warning("spaCy model not found, using basic English tokenizer")
        try:
            spacy.cli.download("en_core_web_sm")
            return spacy.load("en_core_web_sm")
        except Exception:
            return English()
    except Exception as e:
        # Fallback to the basic English tokenizer
        logger.error(f"Error loading spaCy model: {str(e)}")
        return English()

def preprocess_text(text):
    """Clean and normalize text for processing."""
    if not text:
        return ""
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Replace non-breaking spaces with regular spaces
    text = text.replace('\xa0', ' ')
    
    # Standardize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    return text

def extract_paragraphs(text):
    """
    Extract paragraphs using spaCy's linguistic analysis.
    """
    global nlp
    if nlp is None:
        nlp = load_nlp()
    
    # Preprocess the text
    text = preprocess_text(text)
    
    # First, try splitting by double newlines (standard paragraph markers)
    initial_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    # If this splitting works well, process these paragraphs
    paragraphs = []
    if len(initial_paragraphs) > 1:
        for para in initial_paragraphs:
            if len(para) >= 20:  # Skip very short paragraphs
                paragraphs.append(para)
    
    # If we didn't get good results from simple splitting, use spaCy
    if len(paragraphs) <= 1:
        # Process the document with spaCy
        doc = nlp(text)
        sentences = list(doc.sents)
        
        # Check if text starts with common paragraph starters
        para_starters = [
            r'^Dear\b',
            r'^Thank you\b',
            r'^We are\b',
            r'^Your\b',
            r'^This letter\b',
            r'^Please\b'
        ]
        
        # Group sentences into paragraphs
        current_paragraph = []
        for i, sent in enumerate(sentences):
            sent_text = sent.text.strip()
            
            # Start a new paragraph?
            start_new = False
            if i > 0:  # Not for the first sentence
                for pattern in para_starters:
                    if re.match(pattern, sent_text, re.IGNORECASE):
                        start_new = True
                        break
            
            if start_new and current_paragraph:
                # End current paragraph and start a new one
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = [sent_text]
            else:
                # Continue current paragraph
                current_paragraph.append(sent_text)
        
        # Add the last paragraph if not empty
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
    
    # Filter out very short paragraphs
    paragraphs = [p for p in paragraphs if len(p) >= 20]
    
    logger.info(f"Extracted {len(paragraphs)} paragraphs")
    return paragraphs

def is_container(paragraph, other_paragraphs):
    """
    Check if this paragraph is a container of multiple others.
    Uses SequenceMatcher for accurate substring detection.
    """
    if len(paragraph) < 100:
        return False
    
    # Normalize paragraph
    norm_para = ' '.join(paragraph.lower().split())
    
    # Count contained paragraphs
    contained = 0
    for other in other_paragraphs:
        if other == paragraph or len(other) >= len(paragraph):
            continue
        
        # Normalize other paragraph
        norm_other = ' '.join(other.lower().split())
        
        # Check if other is fully contained in paragraph
        if norm_other in norm_para:
            contained += 1
        else:
            # Check with SequenceMatcher for near-matches
            matcher = SequenceMatcher(None, norm_para, norm_other)
            match = matcher.find_longest_match(0, len(norm_para), 0, len(norm_other))
            if match.size >= len(norm_other) * 0.9:
                contained += 1
    
    # It's a container if it contains multiple other paragraphs
    return contained >= 2

def hash_paragraph(paragraph):
    """Create a hash for a paragraph to identify exact duplicates."""
    # Normalize the paragraph for consistent hashing
    normalized = ' '.join(paragraph.lower().split())
    
    # Create a SHA256 hash
    return hashlib.sha256(normalized.encode()).hexdigest()

def is_structured_content(text):
    """Check if text is a structured element like a bullet list or table."""
    # Bullet list patterns
    bullet_patterns = [
        r'(?:\n\s*[\•\-\*\+◦→⇒]|\n\s*\d+[\.\)])[^\n]+(?:\n\s*[\•\-\*\+◦→⇒]|\n\s*\d+[\.\)])[^\n]+',
        r'(?:\n\s*-\s+[^\n]+){2,}',
        r'(?:\n\s*\*\s+[^\n]+){2,}',
        r'(?:\n\s*\d+\.\s+[^\n]+){2,}'
    ]
    
    # Table patterns
    table_patterns = [
        r'\|\s*\w+.*\|',
        r'\+[-+]+\+',
        r'[^\n]+\t[^\n]+'
    ]
    
    # Check bullet patterns
    for pattern in bullet_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    # Check table patterns
    for pattern in table_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    return False

def process_paragraphs(text, document, db_session):
    """
    Process text into paragraphs and associate with document.
    This function maintains the exact signature expected by app.py.
    """
    from models import Paragraph
    
    # Extract paragraphs using spaCy
    paragraphs = extract_paragraphs(text)
    logger.info(f"Initial extraction: {len(paragraphs)} paragraphs")
    
    # Remove container paragraphs (except structured content)
    filtered_paragraphs = []
    containers_removed = 0
    
    for paragraph in paragraphs:
        # Keep structured content intact
        if is_structured_content(paragraph):
            filtered_paragraphs.append(paragraph)
        # Remove container paragraphs
        elif not is_container(paragraph, paragraphs):
            filtered_paragraphs.append(paragraph)
        else:
            containers_removed += 1
    
    # Safety check - if we removed too many, revert to original
    if containers_removed > 0 and len(filtered_paragraphs) < 2:
        logger.warning("Too many paragraphs removed as containers, using original extraction")
        filtered_paragraphs = paragraphs
    
    logger.info(f"After processing: {len(filtered_paragraphs)} paragraphs ({containers_removed} containers removed)")
    
    # Process each paragraph
    paragraph_count = 0
    exact_match_count = 0
    
    for paragraph_text in filtered_paragraphs:
        # Create hash for efficient lookup
        paragraph_hash = hash_paragraph(paragraph_text)
        
        # Check if paragraph already exists in database
        paragraph = Paragraph.query.filter_by(hash=paragraph_hash).first()
        
        if not paragraph:
            # Create new paragraph
            paragraph = Paragraph(
                content=paragraph_text, 
                hash=paragraph_hash
            )
            db_session.add(paragraph)
        else:
            exact_match_count += 1
        
        # Associate paragraph with document if not already associated
        if paragraph not in document.paragraphs:
            document.paragraphs.append(paragraph)
            paragraph_count += 1
    
    logger.info(f"Document processing complete: {paragraph_count} paragraphs added")
    return paragraph_count
