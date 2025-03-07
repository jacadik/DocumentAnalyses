import docx
import logging

logger = logging.getLogger(__name__)

def extract_text_from_docx(file_path):
    """Extract text from a Word document using python-docx."""
    try:
        logger.info(f"Extracting text from DOCX: {file_path}")
        doc = docx.Document(file_path)
        full_text = []
        
        # Extract text from paragraphs
        for para in doc.paragraphs:
            if para.text.strip():  # Skip empty paragraphs
                full_text.append(para.text)
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():  # Skip empty cells
                        full_text.append(cell.text)
        
        logger.info(f"Successfully extracted text from DOCX: {file_path}")
        return '\n'.join(full_text)
    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {str(e)}")
        raise
