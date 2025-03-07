import docx
import os
import logging
from PIL import Image, ImageDraw, ImageFont
import re

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
        
        # Count the number of pages (approximate since python-docx doesn't provide page count)
        # A rough estimate based on content size
        page_count = max(1, len('\n'.join(full_text)) // 3000)
        
        logger.info(f"Successfully extracted text from DOCX: {file_path}")
        return '\n'.join(full_text), page_count
    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {str(e)}")
        raise

def generate_docx_preview(file_path, preview_dir):
    """Generate a preview image for a DOCX file.
    
    Since we can't easily render a DOCX file directly, we'll create a simple
    preview image showing the document title and basic information.
    
    Args:
        file_path: Path to the DOCX file
        preview_dir: Directory to save preview image
        
    Returns:
        str: Filename of the preview image
    """
    try:
        logger.info(f"Generating preview for DOCX: {file_path}")
        doc = docx.Document(file_path)
        
        # Get the base filename without extension
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create a blank image (letter size 8.5x11 inches at 100 DPI)
        width, height = 850, 1100  # 8.5x11 inches at 100 DPI
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        # Try to get a decent font - fallback to default if necessary
        try:
            # Try to find a system font
            font_large = ImageFont.truetype("Arial", 36)
            font_medium = ImageFont.truetype("Arial", 24)
            font_small = ImageFont.truetype("Arial", 16)
        except IOError:
            # Fallback to default
            font_large = ImageFont.load_default()
            font_medium = font_large
            font_small = font_large
        
        # Draw a border
        draw.rectangle([20, 20, width-20, height-20], outline='black', width=2)
        
        # Draw the top header box
        draw.rectangle([20, 20, width-20, 140], fill='lightblue', outline='black', width=2)
        
        # Draw the document title (use the filename if no title property available)
        title = base_filename
        try:
            # Try to get document title from properties
            core_props = doc.core_properties
            if core_props.title:
                title = core_props.title
        except:
            pass
            
        # Clean up the title
        title = re.sub(r'[_-]', ' ', title)
        
        # Draw the title
        draw.text((width//2, 80), title, fill='black', font=font_large, anchor='mm')
        
        # Draw document information section
        y_pos = 180
        draw.text((40, y_pos), "Document Preview", fill='black', font=font_medium)
        y_pos += 50
        
        # Get some document properties if available
        try:
            # Extract first few paragraphs for preview
            preview_text = []
            for i, para in enumerate(doc.paragraphs):
                if para.text.strip() and i < 10:  # Get first 10 non-empty paragraphs
                    preview_text.append(para.text.strip())
                if len(preview_text) >= 5:  # Stop after 5 paragraphs
                    break
            
            # Draw paragraphs
            for i, text in enumerate(preview_text):
                if len(text) > 80:  # Truncate long paragraphs
                    text = text[:77] + "..."
                
                draw.text((40, y_pos), text, fill='black', font=font_small)
                y_pos += 30
                
                if y_pos > height - 100:  # Stop if we're running out of space
                    break
        except:
            # Draw placeholder text if we couldn't get paragraphs
            draw.text((40, y_pos), "Preview not available - please open the document", fill='black', font=font_small)
        
        # Draw footer
        draw.rectangle([20, height-70, width-20, height-20], fill='lightblue', outline='black', width=2)
        draw.text((width//2, height-45), "Document Analyzer Preview", fill='black', font=font_small, anchor='mm')
        
        # Save the image
        preview_filename = f"{base_filename}_preview.png"
        preview_path = os.path.join(preview_dir, preview_filename)
        image.save(preview_path)
        
        logger.info(f"Preview generated at: {preview_path}")
        return preview_filename
    except Exception as e:
        logger.error(f"Error generating DOCX preview for {file_path}: {str(e)}")
        return None