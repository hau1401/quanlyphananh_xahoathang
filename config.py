import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-123')
    
    # 1. Tự động lấy đường dẫn DATABASE_URL đã cấu hình trên Render
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # 2. Xử lý chuẩn hóa định dạng PostgreSQL cho SQLAlchemy
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False