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
    
    # Remove trailing spaces at end of lines
    text = re.sub(r' +\n', '\n', text)
    
    # Remove excessive newlines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def is_structured_content(text):
    """
    Enhanced detection of structured content like bullet lists, numbered lists, and tables.
    
    Args:
        text (str): The text to check for structured content patterns
        
    Returns:
        bool: True if the text appears to be structured content
    """
    # Empty or very short text can't be structured content
    if not text or len(text) < 30:
        return False
    
    # Count newlines to check for multi-line content
    newline_count = text.count('\n')
    if newline_count <= 1:
        return False
    
    # Bullet list patterns (more comprehensive)
    bullet_patterns = [
        # Common bullet symbols
        r'\n\s*[\•\-\*\+◦→⇒♦■□▪▫●○☐☑☒✓✔✕✖✗✘✓✔✕✖✗✘]\s+\S+',
        # Numbered lists with different formats
        r'\n\s*\d+[\.\)]\s+\S+',
        r'\n\s*[a-zA-Z][\.\)]\s+\S+',
        r'\n\s*[ivxIVX]+[\.\)]\s+\S+',
        # Multi-character bullets like "1." or "a." 
        r'(?:\n\s*(?:\d+|[a-zA-Z])[\.\)]\s+[^\n]+){2,}',
        # Special case for double-indentation in lists
        r'\n\s{2,}[\•\-\*\+]\s+\S+'
    ]
    
    # Table patterns
    table_patterns = [
        # Basic table with columns separated by multiple spaces
        r'(?:\n\S+\s{2,}\S+\s{2,}\S+.*){2,}',
        # Pipe-separated tables
        r'(?:\n\s*\|[^|]*\|[^|]*\|.*){2,}',
        # Tab-separated data
        r'(?:\n\S+\t\S+.*){2,}',
        # Tables with plus and minus border characters
        r'[+\-]{3,}',
        # Table headers with equals signs
        r'[=]{3,}'
    ]
    
    # Headers and section title patterns (should be kept as separate paragraphs)
    header_patterns = [
        r'^\s*[A-Z0-9][\w\s]+:$',
        r'^\s*[IVX]+\.\s+[A-Z]',
        r'^\s*\d+\.\d+\s+[A-Z]'
    ]
    
    # Check for headers and exclude them from structured content
    for pattern in header_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return False
    
    # Check for bullet patterns
    for pattern in bullet_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    # Check for table patterns
    for pattern in table_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    # Check for consistent indentation which often indicates structured content
    lines = text.split('\n')
    indented_lines = [line for line in lines if line.startswith('    ') or line.startswith('\t')]
    if len(indented_lines) >= 2 and len(indented_lines) / len(lines) > 0.5:
        return True
    
    return False

def identify_paragraph_boundaries(text):
    """
    Identify paragraph boundaries using multiple heuristics.
    
    Args:
        text (str): Preprocessed text to split into paragraphs
        
    Returns:
        list: List of paragraph texts
    """
    # First attempt: Split by double newlines (most common paragraph separator)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    # If this works reasonably well, return these paragraphs
    if len(paragraphs) > 1:
        # Post-process to handle some edge cases
        processed_paragraphs = []
        current_paragraph = None
        
        for p in paragraphs:
            # If paragraph is very short and doesn't end with punctuation
            if current_paragraph and len(p) < 100 and not re.search(r'[.!?:;]$', p.strip()):
                # Possible continuation of previous paragraph
                current_paragraph += '\n\n' + p
            else:
                if current_paragraph:
                    processed_paragraphs.append(current_paragraph)
                current_paragraph = p
        
        if current_paragraph:
            processed_paragraphs.append(current_paragraph)
        
        # Check if we have enough paragraphs or need to try another approach
        if len(processed_paragraphs) > 1:
            return processed_paragraphs
    
    # Second attempt: Use more sophisticated boundary detection for difficult cases
    paragraphs = []
    lines = text.split('\n')
    current_paragraph = []
    in_structured_content = False
    
    # Paragraph starter patterns
    para_starters = [
        r'^[A-Z]',  # Starts with capital letter
        r'^Dear\b',
        r'^To Whom\b',
        r'^Thank you\b',
        r'^We are\b',
        r'^Please\b',
        r'^In conclusion\b',
        r'^Furthermore\b',
        r'^However\b',
        r'^Moreover\b',
        r'^In addition\b',
        r'^Subject:',
        r'^RE:',
        r'^From:',
        r'^Date:',
        r'^Sent:',
        r'^To:'
    ]
    
    # Structured content detector patterns
    structured_start_patterns = [
        r'^\s*[\•\-\*\+]\s+',         # Bullet point
        r'^\s*\d+[\.\)]\s+',           # Numbered list
        r'^\s*[a-zA-Z][\.\)]\s+',      # Lettered list
        r'^\s*\|',                     # Table row
        r'^\s*[+\-=]{3,}',             # Table border
        r'^\s*_+$'                     # Underline
    ]
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            # Empty line usually means paragraph break, unless in structured content
            if in_structured_content:
                # Check if this is the end of structured content
                if i+1 < len(lines) and not any(re.match(p, lines[i+1]) for p in structured_start_patterns):
                    in_structured_content = False
                current_paragraph.append('')
            elif current_paragraph:
                # End of paragraph
                paragraphs.append('\n'.join(current_paragraph))
                current_paragraph = []
            continue
        
        # Check if this starts structured content
        if any(re.match(p, line) for p in structured_start_patterns):
            in_structured_content = True
            
        # Check if this is a new paragraph
        is_new_para = False
        if not in_structured_content and current_paragraph:
            # Check if this line starts a new paragraph
            if any(re.match(p, line) for p in para_starters):
                # But don't split if previous line doesn't end with punctuation
                prev_line = current_paragraph[-1].strip()
                if re.search(r'[.!?:;]$', prev_line) or not prev_line:
                    is_new_para = True
        
        if is_new_para:
            paragraphs.append('\n'.join(current_paragraph))
            current_paragraph = [line]
        else:
            current_paragraph.append(line)
    
    # Add the final paragraph
    if current_paragraph:
        paragraphs.append('\n'.join(current_paragraph))
    
    # If we still don't have reasonable paragraphs, fallback to spaCy
    if len(paragraphs) <= 1:
        return extract_paragraphs_with_spacy(text)
    
    return paragraphs

def extract_paragraphs_with_spacy(text):
    """Use spaCy to extract paragraphs by analyzing sentence boundaries."""
    global nlp
    if nlp is None:
        nlp = load_nlp()
    
    # Process the document with spaCy
    doc = nlp(text)
    sentences = list(doc.sents)
    
    # Group sentences into paragraphs
    paragraphs = []
    current_paragraph = []
    
    para_starters = [
        r'^Dear\b',
        r'^Thank you\b',
        r'^We are\b',
        r'^Your\b',
        r'^This letter\b',
        r'^Please\b',
        r'^In conclusion\b',
        r'^Furthermore\b',
        r'^However\b',
        r'^Moreover\b'
    ]
    
    for i, sent in enumerate(sentences):
        sent_text = sent.text.strip()
        
        # Skip empty sentences
        if not sent_text:
            continue
        
        # Start a new paragraph?
        start_new = False
        if i > 0:  # Not for the first sentence
            # Check if this sentence starts with paragraph starter
            for pattern in para_starters:
                if re.match(pattern, sent_text, re.IGNORECASE):
                    start_new = True
                    break
            
            # Check if previous sentence ends with paragraph-ending punctuation
            if sentences[i-1].text.strip().endswith(('.', '!', '?', ':', ';')):
                # More likely to be a paragraph break
                start_new = True
        
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
    
    return paragraphs

def post_process_paragraphs(paragraphs):
    """
    Post-process extracted paragraphs to fix common issues.
    
    Args:
        paragraphs (list): List of extracted paragraphs
        
    Returns:
        list: List of cleaned paragraphs
    """
    # Filter out very short paragraphs that aren't meaningful
    min_length = 20
    paragraphs = [p for p in paragraphs if len(p) >= min_length]
    
    # Remove duplicate paragraphs
    unique_paragraphs = []
    content_hashes = set()
    
    for para in paragraphs:
        # Normalize paragraph for comparison
        norm_para = ' '.join(para.lower().split())
        para_hash = hashlib.md5(norm_para.encode()).hexdigest()
        
        if para_hash not in content_hashes:
            content_hashes.add(para_hash)
            unique_paragraphs.append(para)
    
    # Ensure structured content is kept intact
    processed_paragraphs = []
    i = 0
    while i < len(unique_paragraphs):
        current = unique_paragraphs[i]
        
        # Check if this is structured content
        if is_structured_content(current):
            processed_paragraphs.append(current)
        # Check if we should merge with next paragraph (continuation)
        elif i+1 < len(unique_paragraphs):
            next_para = unique_paragraphs[i+1]
            
            # Criteria for merger: current doesn't end with punctuation
            # and next doesn't start with capital letter or special markers
            if (not re.search(r'[.!?:;]$', current.strip()) and 
                not re.match(r'^[A-Z]|^Dear\b|^To\b|^From\b', next_para.strip())):
                processed_paragraphs.append(current + '\n\n' + next_para)
                i += 2  # Skip the next paragraph as we've merged it
                continue
            else:
                processed_paragraphs.append(current)
        else:
            processed_paragraphs.append(current)
        
        i += 1
    
    return processed_paragraphs

def extract_paragraphs(text):
    """
    Extract paragraphs using improved detection logic with special handling for structured content.
    
    Args:
        text (str): Text to extract paragraphs from
        
    Returns:
        list: List of extracted paragraphs
    """
    # Preprocess the text
    text = preprocess_text(text)
    
    # Skip processing if text is too short
    if len(text) < 50:
        return [text] if text else []
    
    # Find paragraph boundaries
    paragraphs = identify_paragraph_boundaries(text)
    
    # Post-process to clean up and fix issues
    processed_paragraphs = post_process_paragraphs(paragraphs)
    
    logger.info(f"Extracted {len(processed_paragraphs)} paragraphs")
    return processed_paragraphs

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

def process_paragraphs(text, document, db_session):
    """
    Process text into paragraphs and associate with document.
    This function maintains the exact signature expected by app.py.
    """
    from models import Paragraph
    import sqlite3
    
    # Extract paragraphs
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
    
    for position, paragraph_text in enumerate(filtered_paragraphs):
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
            db_session.flush()  # Ensure paragraph has an ID
        else:
            exact_match_count += 1
        
        # Associate paragraph with document if not already associated
        if paragraph not in document.paragraphs:
            # First add the paragraph to the document (creates the association)
            document.paragraphs.append(paragraph)
            db_session.flush()
            
            try:
                # Get direct database connection to handle position setting
                connection = db_session.connection().connection
                cursor = connection.cursor()
                
                # Update the position using direct SQL
                cursor.execute(
                    "UPDATE document_paragraph SET position = ? WHERE document_id = ? AND paragraph_id = ?",
                    (position, document.id, paragraph.id)
                )
                
                paragraph_count += 1
            except Exception as e:
                logger.error(f"Error setting position: {str(e)}")
                # Continue processing even if position setting fails
                paragraph_count += 1
    
    logger.info(f"Document processing complete: {paragraph_count} paragraphs added")
    return paragraph_count
