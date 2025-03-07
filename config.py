import os
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-document-analyzer'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'document_analyzer.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    PREVIEW_FOLDER = os.path.join(UPLOAD_FOLDER, 'previews')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_FOLDER, f'app_{datetime.now().strftime("%Y%m%d")}.log')
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}