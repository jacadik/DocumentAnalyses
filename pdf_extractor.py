import fitz  # PyMuPDF
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
        
        doc.close()
        logger.info(f"Successfully extracted text from PDF: {file_path}")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        raise
