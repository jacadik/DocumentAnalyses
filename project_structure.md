# Document Analyzer - Enhanced Project Structure

```
document_analyzer/
│
├── app.py                  # Main Flask application with new routes for similarity and tagging
├── config.py               # Configuration settings 
├── models.py               # Database models (with new Tag and DocumentSimilarity models)
├── utils/
│   ├── __init__.py
│   ├── docx_extractor.py       # Word document text extraction
│   ├── pdf_extractor.py        # PDF text extraction with in-memory preview generation
│   ├── excel_exporter.py       # Excel report generation
│   ├── paragraph_processor.py  # Paragraph extraction and processing
│   └── similarity_analyzer.py  # NEW: Document similarity calculation
│
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── main.js
│
├── templates/
│   ├── base.html              # Base template with updated navigation
│   ├── index.html             # Home page
│   ├── upload.html            # Upload form
│   ├── documents.html         # List of documents
│   ├── view.html              # View document details (updated with tagging)
│   ├── paragraphs.html        # View paragraph analysis
│   ├── similarity_map.html    # NEW: Document similarity visualization
│   ├── compare_documents.html # NEW: Compare two documents side by side
│   ├── tags.html              # NEW: Tag management page
│   ├── logs.html              # View application logs
│   └── view_log.html          # View specific log file
│
├── uploads/                   # Folder to store uploaded files
├── logs/                      # Folder for log files
├── instance/                  # Instance-specific data (SQLite database)
└── requirements.txt           # Project dependencies (updated with new requirements)
```

## New Database Tables

```
Table: document_similarity
- id (PK)
- source_id (FK -> document.id)
- target_id (FK -> document.id)
- similarity_score (float)
- created_at (datetime)

Table: tag
- id (PK)
- name (unique string)
- color (string, hex color code)
- description (string)
- created_at (datetime)

Table: document_tag (association table)
- document_id (PK, FK -> document.id)
- tag_id (PK, FK -> tag.id)

Table: paragraph_tag (association table)
- paragraph_id (PK, FK -> paragraph.id)
- tag_id (PK, FK -> tag.id)
```

## New Routes

```
/similarity-map                      # View document similarity visualization
/calculate-similarities              # Calculate and store document similarities
/compare-documents/<doc1>/<doc2>     # Compare two documents side by side
/tags                                # Manage tags
/tags/create                         # Create a new tag
/tags/edit/<id>                      # Edit an existing tag
/tags/delete/<id>                    # Delete a tag
/document/<id>/tag                   # Add/remove tags from a document
/paragraph/<id>/tag                  # Add/remove tags from a paragraph
/api/paragraph/<id>/tags             # API endpoint for paragraph tags
```

## New Dependencies

- scikit-learn (for TF-IDF and similarity calculations)
- d3.js (for visualization, included via CDN)
