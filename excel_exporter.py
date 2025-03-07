import pandas as pd
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_excel_report(documents, output_dir):
    """Generate an Excel report from extracted document text and paragraphs.
    
    Args:
        documents: List of Document objects
        output_dir: Directory where the Excel file will be saved
        
    Returns:
        str: The filename of the generated Excel report
    """
    try:
        logger.info("Generating Excel report")
        
        # Create summary data for the first sheet
        summary_data = []
        for doc in documents:
            summary_data.append({
                'ID': doc.id,
                'Filename': doc.original_filename,
                'File Type': doc.file_type.upper(),
                'File Size (KB)': round(doc.file_size / 1024, 2),
                'Upload Date': doc.upload_date,
                'Status': doc.status,
                'Text Length (chars)': len(doc.extracted_text) if doc.extracted_text else 0,
                'Paragraph Count': len(doc.paragraphs)
            })
        
        # Create text data for the second sheet
        text_data = []
        for doc in documents:
            text_data.append({
                'ID': doc.id,
                'Filename': doc.original_filename,
                'Extracted Text': doc.extracted_text or "No text extracted"
            })
            
        # Create paragraph data for the third sheet
        paragraph_data = []
        
        # Get all unique paragraphs from all documents
        all_paragraphs = set()
        for doc in documents:
            for para in doc.paragraphs:
                all_paragraphs.add(para)
        
        # For each paragraph, list the documents it appears in
        for para in all_paragraphs:
            # Get a list of document filenames this paragraph appears in
            doc_list = [doc.original_filename for doc in para.documents if doc in documents]
            
            # Truncate paragraph content for Excel if extremely long
            content = para.content
            if len(content) > 32000:  # Excel cell limit
                content = content[:32000] + "... (truncated)"
                
            paragraph_data.append({
                'Paragraph ID': para.id,
                'Content': content,
                'Documents': ', '.join(doc_list),
                'Document Count': len(doc_list)
            })
        
        # Sort paragraphs by document count (most shared first)
        paragraph_data = sorted(paragraph_data, key=lambda x: x['Document Count'], reverse=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f'document_report_{timestamp}.xlsx')
        
        # Create Excel writer with three sheets
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Convert data to DataFrames
            df_summary = pd.DataFrame(summary_data)
            df_text = pd.DataFrame(text_data)
            df_paragraphs = pd.DataFrame(paragraph_data)
            
            # Write to Excel sheets
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            df_text.to_excel(writer, sheet_name='Full Text', index=False)
            df_paragraphs.to_excel(writer, sheet_name='Paragraphs', index=False)
            
            # Auto-adjust column widths for summary sheet
            worksheet = writer.sheets['Summary']
            for i, col in enumerate(df_summary.columns):
                max_width = max(
                    df_summary[col].astype(str).map(len).max(),
                    len(col)
                ) + 2  # Add a little extra space
                # Excel column width is based on character width of the standard font
                worksheet.column_dimensions[chr(65 + i)].width = min(max_width, 50)  # Cap at 50
            
            # Set reasonable width for paragraph content
            if 'Paragraphs' in writer.sheets:
                worksheet = writer.sheets['Paragraphs']
                # Set content column to reasonable width
                content_col = chr(65 + df_paragraphs.columns.get_loc('Content'))
                worksheet.column_dimensions[content_col].width = 80
        
        logger.info(f"Excel report generated successfully: {filename}")
        return os.path.basename(filename)
    except Exception as e:
        logger.error(f"Error generating Excel report: {str(e)}")
        raise
