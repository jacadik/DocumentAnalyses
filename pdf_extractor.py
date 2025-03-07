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

def generate_pdf_preview(file_path, preview_dir, max_pages=5):
    """Generate preview images for multiple pages of a PDF.
    
    Args:
        file_path: Path to the PDF file
        preview_dir: Directory to save preview images
        max_pages: Maximum number of pages to generate previews for
        
    Returns:
        dict: Dictionary containing preview information:
            - 'base_filename': Base filename for previews (without page number)
            - 'total_pages': Total number of pages with previews
            - 'preview_format': Format string for previews (e.g., "{base}_page_{page}.png")
    """
    try:
        logger.info(f"Generating preview for PDF: {file_path}")
        doc = fitz.open(file_path)
        
        # Get the base filename without extension
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create preview info
        preview_info = {
            'base_filename': base_filename,
            'total_pages': min(len(doc), max_pages),
            'preview_format': "{base}_page_{page}.png"
        }
        
        # Generate previews for up to max_pages
        for page_num in range(min(len(doc), max_pages)):
            page = doc.load_page(page_num)
            
            # Render page to an image with higher resolution for better quality
            zoom_factor = 2.0  # Adjust as needed for quality vs. file size
            mat = fitz.Matrix(zoom_factor, zoom_factor)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Create preview filename with page number
            preview_filename = preview_info['preview_format'].format(
                base=base_filename, 
                page=page_num+1
            )
            preview_path = os.path.join(preview_dir, preview_filename)
            
            # Save the image
            pix.save(preview_path)
            logger.info(f"Preview generated for page {page_num+1} at: {preview_path}")
        
        doc.close()
        return preview_info
    except Exception as e:
        logger.error(f"Error generating PDF preview for {file_path}: {str(e)}")
        return None