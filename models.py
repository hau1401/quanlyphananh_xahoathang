from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    feedbacks = db.relationship(
        "Feedback",
        backref="category",
        lazy=True
    )


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    feedback_code = db.Column(db.String(20), unique=True, nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    
    # 📍 Tọa độ bản đồ Google Maps / OpenStreetMap
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # 🎥 🖼️ Lưu danh sách file (ảnh/video) phân cách bằng dấu phẩy
    media_files = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(50), default="Đã tiếp nhận")
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="staff")
    created_at = db.Column(db.DateTime, server_default=db.func.now())