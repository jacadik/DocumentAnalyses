import fitz  # PyMuPDF
import os
import logging
import io

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
            - 'file_type': Type of file ('pdf')
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
            'file_type': 'pdf'
        }
        
        doc.close()
        return preview_info
    except Exception as e:
        logger.error(f"Error creating PDF preview info for {file_path}: {str(e)}")
        return None

def generate_page_preview(document, page_number, file_path):
    """Generate a preview image for a specific page of a PDF document in memory.
    
    Args:
        document: Document object
        page_number: Page number to generate (1-based index)
        file_path: Path to the PDF file
        
    Returns:
        tuple: (bytes, str) - Image data as bytes and mimetype
    """
    try:
        # Get preview info
        preview_info = document.get_preview_info()
        if not preview_info:
            logger.error(f"No preview info found for document ID {document.id}")
            return None, None
            
        # Check if page number is valid
        if page_number < 1 or page_number > preview_info.get('document_page_count', 0):
            logger.error(f"Invalid page number {page_number} for document ID {document.id}")
            return None, None
            
        # Open the PDF document
        if not os.path.exists(file_path):
            logger.error(f"Document file not found: {file_path}")
            return None, None
            
        doc = fitz.open(file_path)
        
        # Load the requested page (adjust for 0-based indexing)
        page = doc.load_page(page_number - 1)
        
        # Render page to an image with higher resolution for better quality
        zoom_factor = 2.0  # Adjust as needed for quality vs. file size
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Save the image to a bytes buffer instead of a file
        img_bytes = pix.tobytes("png")
        
        # Create a BytesIO object from the bytes
        buffer = io.BytesIO(img_bytes)
        buffer.seek(0)
        
        logger.info(f"Preview generated in memory for page {page_number} of document ID {document.id}")
        
        doc.close()
        return buffer.getvalue(), "image/png"
    except Exception as e:
        logger.error(f"Error generating page preview: {str(e)}")
        return None, None