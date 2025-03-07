import fitz  # PyMuPDF
import os
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file using PyMuPDF."""
    try:
        logger.info(f"Extracting text from PDF: {file_path}")
        doc = fitz.open(file_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        
        page_count = len(doc)
        doc.close()
        logger.info(f"Successfully extracted text from PDF: {file_path}")
        return text, page_count
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        raise

def create_pdf_preview_info(file_path):
    """Create preview information without generating any preview images.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        dict: Dictionary containing preview information:
            - 'base_filename': Base filename for previews (without page number)
            - 'document_page_count': Total number of pages in the document
            - 'preview_format': Format string for previews (e.g., "{base}_page_{page}.png")
    """
    try:
        logger.info(f"Creating preview info for PDF: {file_path}")
        doc = fitz.open(file_path)
        total_doc_pages = len(doc)
        
        # Get the base filename without extension
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create preview info with document metadata
        preview_info = {
            'base_filename': base_filename,
            'document_page_count': total_doc_pages,
            'preview_format': "{base}_page_{page}.png",
            'file_type': 'pdf'
        }
        
        doc.close()
        return preview_info
    except Exception as e:
        logger.error(f"Error creating PDF preview info for {file_path}: {str(e)}")
        return None

def generate_page_preview(document, page_number, preview_dir):
    """Generate a preview image for a specific page of a PDF document.
    
    Args:
        document: Document object
        page_number: Page number to generate (1-based index)
        preview_dir: Directory to save preview image
        
    Returns:
        str: Filename of the generated preview image, or None if failed
    """
    try:
        # Get preview info
        preview_info = document.get_preview_info()
        if not preview_info:
            logger.error(f"No preview info found for document ID {document.id}")
            return None
            
        # Check if page number is valid
        if page_number < 1 or page_number > preview_info.get('document_page_count', 0):
            logger.error(f"Invalid page number {page_number} for document ID {document.id}")
            return None
            
        # Construct the expected preview filename
        preview_filename = preview_info['preview_format'].format(
            base=preview_info['base_filename'],
            page=page_number
        )
        preview_path = os.path.join(preview_dir, preview_filename)
        
        # Check if preview already exists
        if os.path.exists(preview_path):
            logger.info(f"Preview for page {page_number} already exists at: {preview_path}")
            return preview_filename
            
        # Open the PDF document
        file_path = os.path.join(os.path.dirname(preview_dir), document.filename)
        if not os.path.exists(file_path):
            logger.error(f"Document file not found: {file_path}")
            return None
            
        doc = fitz.open(file_path)
        
        # Load the requested page (adjust for 0-based indexing)
        page = doc.load_page(page_number - 1)
        
        # Render page to an image with higher resolution for better quality
        zoom_factor = 2.0  # Adjust as needed for quality vs. file size
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Save the image
        pix.save(preview_path)
        logger.info(f"Preview generated for page {page_number} at: {preview_path}")
        
        doc.close()
        return preview_filename
    except Exception as e:
        logger.error(f"Error generating page preview: {str(e)}")
        return None