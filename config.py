import os

# Lấy đường dẫn thư mục gốc của dự án
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or "hoathang123"

    # Kiểm tra môi trường: 
    # Nếu chạy trên Render (có biến RENDER) -> Dùng SQLite
    # Nếu chạy dưới máy local -> Dùng MySQL của bạn
    if os.environ.get('RENDER'):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'hoathang_feedback.db')}"
    else:
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:MatKhauMoi123@localhost/hoathang_feedback"

    SQLALCHEMY_TRACK_MODIFICATIONS = False