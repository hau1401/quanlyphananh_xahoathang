import os
import io
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from sqlalchemy import text, inspect
from dotenv import load_dotenv
import pandas as pd

# Thư viện Cloudinary
import cloudinary
import cloudinary.uploader

from config import Config
from models import db, Category, Feedback, User, News

# ⚡ Load biến môi trường từ tệp .env
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# 🛠️ Cấu hình Cloudinary từ biến môi trường (.env)
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# 🛠️ Ưu tiên kết nối PostgreSQL trên Render
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# 🔥 CẤU HÌNH TỰ ĐỘNG ĐĂNG XUẤT KHI TẮT TRÌNH DUYỆT
app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

# 🔥 GIỚI HẠN DUNG LƯỢNG FILE TẢI LÊN (75MB Max Request)
app.config['MAX_CONTENT_LENGTH'] = 75 * 1024 * 1024 

db.init_app(app)

# 🔥 TỰ ĐỘNG TẠO BẢNG, VÁ CỘT MỚI & KHỞI TẠO DỮ LIỆU BAN ĐẦU
with app.app_context():
    db.create_all()
    
    inspector = inspect(db.engine)
    if inspector.has_table("feedbacks"):
        existing_columns = [col['name'] for col in inspector.get_columns("feedbacks")]
        
        with db.engine.connect() as conn:
            if "media_files" not in existing_columns:
                conn.execute(text("ALTER TABLE feedbacks ADD COLUMN media_files TEXT;"))
                conn.commit()
            if "latitude" not in existing_columns:
                conn.execute(text("ALTER TABLE feedbacks ADD COLUMN latitude FLOAT;"))
                conn.commit()
            if "longitude" not in existing_columns:
                conn.execute(text("ALTER TABLE feedbacks ADD COLUMN longitude FLOAT;"))
                conn.commit()
            if "response_content" not in existing_columns:
                conn.execute(text("ALTER TABLE feedbacks ADD COLUMN response_content TEXT;"))
                conn.commit()

    # Khởi tạo tài khoản Admin
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            fullname="Quản Trị Viên Xã",
            username="admin",
            password="123456@",
            role="admin"
        )
        db.session.add(admin_user)
    else:
        admin_user.password = "123456@"
        admin_user.role = "admin"
        
    if Category.query.count() == 0:
        default_categories = [
            "Giao thông - Hạ tầng",
            "Môi trường - Rác thải",
            "An ninh - Trật tự",
            "Thủ tục hành chính",
            "Đất đai - Xây dựng",
            "Y tế - Dịch vụ công",
            "Giáo dục - Văn hóa",
            "Lĩnh vực khác"
        ]
        for cat_name in default_categories:
            db.session.add(Category(name=cat_name))

    # Khởi tạo Tin Tức Mẫu nếu chưa có (Dùng ảnh trực tuyến chống mất ảnh khi restart Render)
    if News.query.count() == 0:
        sample_news = [
            News(
                title="Kế hoạch triển khai dịch vụ công trực tuyến năm 2026",
                summary="UBND xã Hòa Thắng thông báo đẩy mạnh tiếp nhận hồ sơ và trả kết quả thủ tục hành chính qua cổng dịch vụ công quốc gia...",
                content="Nhằm nâng cao chất lượng phục vụ người dân và doanh nghiệp, UBND xã Hòa Thắng triển khai tiếp nhận 100% thủ tục hành chính đủ điều kiện lên Dịch vụ công trực tuyến toàn trình.\n\nNgười dân có thể truy cập cổng Dịch vụ công Quốc gia hoặc liên hệ Bộ phận Một cửa xã Hòa Thắng để được bộ phận cán bộ hỗ trợ và hướng dẫn chi tiết.",
                category="Thông báo quan trọng",
                image="https://images.unsplash.com/photo-1450133064473-71024230f91b?auto=format&fit=crop&w=800&q=80",
                is_featured=True
            ),
            News(
                title="Tuyên truyền công tác an toàn giao thông trên địa bàn xã",
                summary="Đoàn thanh niên xã phối hợp với lực lượng công an tổ chức buổi tuyên truyền Luật Giao thông đường bộ...",
                content="Đoàn thanh niên xã phối hợp với lực lượng công an tổ chức buổi tuyên truyền Luật Giao thông đường bộ cho học sinh và bà con nhân dân trên địa bàn.\n\nBuổi tuyên truyền tập trung phổ biến các quy định về việc chấp hành đội mũ bảo hiểm, không sử dụng rượu bia khi tham gia giao thông và chú ý quan sát tại các điểm giao cắt giao thông trọng điểm.",
                category="Hoạt động địa phương",
                image="https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=800&q=80",
                is_featured=False
            )
        ]
        db.session.add_all(sample_news)

    db.session.commit()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'mkv', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==========================================
# DECORATORS BẢO MẬT & PHÂN QUYỀN
# ==========================================

@app.before_request
def make_session_non_permanent():
    session.modified = True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Vui lòng đăng nhập để sử dụng chức năng này!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Vui lòng đăng nhập tài khoản Quản trị!", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Bạn không có quyền truy cập trang Quản trị (Admin)!", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

def generate_feedback_code():
    year = datetime.now().year
    number = random.randint(1000, 9999)
    return f"HT{year}{number}"


# ==========================================
# 1. TRANG CHỦ, GÓP Ý & TRA CỨU
# ==========================================

@app.route("/")
def home():
    categories = Category.query.all()
    total_feedbacks = Feedback.query.count()
    completed_count = Feedback.query.filter_by(status="Đã xử lý").count()
    processing_count = Feedback.query.filter_by(status="Đang xử lý").count()
    recent_feedbacks = Feedback.query.order_by(Feedback.id.desc()).limit(6).all()

    return render_template(
        "index.html", 
        categories=categories,
        total_feedbacks=total_feedbacks,
        completed_count=completed_count,
        processing_count=processing_count,
        recent_feedbacks=recent_feedbacks
    )


@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    categories = Category.query.all()

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()

        if not phone.isdigit() or not (10 <= len(phone) <= 11):
            flash("Số điện thoại không hợp lệ! Vui lòng chỉ nhập từ 10 đến 11 chữ số.", "danger")
            return render_template("feedback.html", categories=categories)

        uploaded_files = request.files.getlist("media_files")
        saved_urls = []

        if len(uploaded_files) > 5:
            flash("Chỉ được gửi tối đa 5 tệp đính kèm!", "danger")
            return render_template("feedback.html", categories=categories)

        for file in uploaded_files:
            if file and file.filename != "":
                if allowed_file(file.filename):
                    try:
                        upload_result = cloudinary.uploader.upload(
                            file,
                            folder="phan_anh_hoa_thang",
                            resource_type="auto"
                        )
                        saved_urls.append(upload_result.get('secure_url'))
                    except Exception as e:
                        flash(f"Lỗi tải file {file.filename} lên Cloudinary: {str(e)}", "danger")
                        return render_template("feedback.html", categories=categories)
                else:
                    flash(f"Tệp '{file.filename}' không đúng định dạng cho phép!", "danger")
                    return render_template("feedback.html", categories=categories)

        media_files_str = ",".join(saved_urls) if saved_urls else None

        lat_val = request.form.get("latitude")
        lng_val = request.form.get("longitude")

        fb_item = Feedback(
            feedback_code=generate_feedback_code(),
            fullname=request.form["fullname"],
            phone=phone,
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            latitude=float(lat_val) if lat_val and lat_val.strip() else None,
            longitude=float(lng_val) if lng_val and lng_val.strip() else None,
            category_id=request.form["category"],
            title=request.form["title"],
            content=request.form["content"],
            media_files=media_files_str,
            status="Đã tiếp nhận"
        )

        db.session.add(fb_item)
        db.session.commit()

        return render_template("success.html", code=fb_item.feedback_code)

    return render_template("feedback.html", categories=categories)


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    fb_item = None
    if request.method == "POST":
        code = request.form.get("code")
        fb_item = Feedback.query.filter_by(feedback_code=code).first()

    return render_template("search.html", feedback=fb_item)


# ==========================================
# 2. XÁC THỰC TÀI KHOẢN (ĐĂNG NHẬP / ĐĂNG KÝ / ĐĂNG XUẤT)
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Tên đăng nhập không tồn tại trong hệ thống!", "danger")
            return redirect(url_for("login"))

        if user.password != password:
            flash("Mật khẩu không chính xác, vui lòng thử lại!", "danger")
            return redirect(url_for("login"))

        session.permanent = False

        session["user_id"] = user.id
        session["username"] = user.username
        session["fullname"] = user.fullname
        session["role"] = user.role

        flash(f"Xin chào {user.fullname}! Đăng nhập thành công.", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        username = request.form["username"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Mật khẩu nhập lại không khớp!", "danger")
            return redirect(url_for("register"))

        check_user = User.query.filter_by(username=username).first()

        if check_user:
            flash("Tên đăng nhập này đã tồn tại!", "warning")
            return redirect(url_for("register"))

        new_user = User(
            fullname=fullname,
            username=username,
            password=password,
            role="staff"
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công.", "info")
    return redirect(url_for("home"))


# ==========================================
# 3. QUẢN TRỊ ADMIN (DASHBOARD & CÁC CHỨC NĂNG)
# ==========================================

@app.route("/dashboard")
@admin_required
def dashboard():
    total_feedbacks = Feedback.query.count()
    pending_count = Feedback.query.filter_by(status="Đã tiếp nhận").count()
    processing_count = Feedback.query.filter_by(status="Đang xử lý").count()
    completed_count = Feedback.query.filter_by(status="Đã xử lý").count()
    total_users = User.query.count()

    feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()
    categories = Category.query.all()
    users = User.query.all()
    news_list = News.query.order_by(News.id.desc()).all()

    return render_template(
        "admin/dashboard.html",
        total_feedbacks=total_feedbacks,
        pending_count=pending_count,
        processing_count=processing_count,
        completed_count=completed_count,
        total_users=total_users,
        feedbacks=feedbacks,
        categories=categories,
        users=users,
        news_list=news_list
    )


@app.route("/export-excel")
@admin_required
def export_excel():
    feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()
    
    data = []
    for fb in feedbacks:
        data.append({
            "Mã PA": fb.feedback_code,
            "Họ và tên": fb.fullname,
            "Số điện thoại": fb.phone,
            "Email": fb.email or "",
            "Địa chỉ": fb.address or "",
            "Lĩnh vực": fb.category.name if fb.category else "Khác",
            "Tiêu đề": fb.title,
            "Nội dung phản ánh": fb.content,
            "Trạng thái": fb.status,
            "Nội dung phản hồi": fb.response_content or "",
            "Ngày gửi": fb.created_at.strftime('%d/%m/%Y %H:%M') if fb.created_at else ""
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Danh_Sach_Phan_Anh')
    
    output.seek(0)
    filename = f"Bao_Cao_Phan_Anh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@app.route("/admin/feedback/update/<int:feedback_id>", methods=["POST"])
@admin_required
def update_feedback_status(feedback_id):
    fb = db.session.get(Feedback, feedback_id)
    if fb:
        fb.status = request.form.get("status")
        if "response_content" in request.form:
            fb.response_content = request.form.get("response_content")
            
        db.session.commit()
        flash(f"Đã cập nhật trạng thái phản ánh #{fb.feedback_code} thành công!", "success")
    else:
        flash("Không tìm thấy phản ánh yêu cầu!", "danger")
        
    return redirect(url_for("dashboard"))


@app.route("/admin/feedback/delete/<int:feedback_id>", methods=["POST"])
@admin_required
def delete_feedback(feedback_id):
    fb = db.session.get(Feedback, feedback_id)
    if fb:
        db.session.delete(fb)
        db.session.commit()
        flash("Đã xóa phản ánh thành công!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/change-role/<int:user_id>", methods=["POST"])
@admin_required
def change_user_role(user_id):
    if user_id == session.get("user_id"):
        flash("Bạn không thể tự hạ quyền Admin của chính mình!", "warning")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if user:
        new_role = request.form.get("role")
        user.role = new_role
        db.session.commit()
        flash(f"Đã phân lại quyền cho tài khoản {user.username} thành '{new_role}'!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("Bạn không thể xóa tài khoản đang đăng nhập!", "warning")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash(f"Đã xóa tài khoản {user.username} thành công!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/category/add", methods=["POST"])
@admin_required
def add_category():
    cat_name = request.form.get("name")
    if cat_name:
        new_cat = Category(name=cat_name)
        db.session.add(new_cat)
        db.session.commit()
        flash(f"Đã thêm lĩnh vực '{cat_name}' thành công!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/category/delete/<int:cat_id>", methods=["POST"])
@admin_required
def delete_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if cat:
        db.session.delete(cat)
        db.session.commit()
        flash("Đã xóa danh mục thành công!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/news/add", methods=["POST"])
@admin_required
def add_news():
    title = request.form.get("title")
    category = request.form.get("category")
    summary = request.form.get("summary")
    content = request.form.get("content")
    is_featured = True if request.form.get("is_featured") == "on" else False

    file = request.files.get("image")
    image_url = None
    if file and file.filename != "" and allowed_file(file.filename):
        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="news_hoa_thang",
                resource_type="auto"
            )
            image_url = upload_result.get('secure_url')
        except Exception as e:
            flash(f"Lỗi tải ảnh tin tức lên Cloudinary: {str(e)}", "danger")

    new_item = News(
        title=title,
        category=category,
        summary=summary,
        content=content,
        image=image_url,
        is_featured=is_featured
    )
    db.session.add(new_item)
    db.session.commit()
    flash("Thêm tin tức / thông báo mới thành công!", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/news/delete/<int:news_id>", methods=["POST"])
@admin_required
def delete_news(news_id):
    news_item = db.session.get(News, news_id)
    if news_item:
        db.session.delete(news_item)
        db.session.commit()
        flash("Đã xóa bài viết tin tức thành công!", "success")
    return redirect(url_for("dashboard"))


# ==========================================
# 4. CÁC TRANG TĨNH & TÀI KHOẢN
# ==========================================

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/news")
def news():
    featured_news = News.query.filter_by(is_featured=True).order_by(News.id.desc()).first()
    if not featured_news:
        featured_news = News.query.order_by(News.id.desc()).first()
        
    if featured_news:
        other_news = News.query.filter(News.id != featured_news.id).order_by(News.id.desc()).all()
    else:
        other_news = []

    return render_template("news.html", featured_news=featured_news, other_news=other_news)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        fullname = request.form.get("fullname")
        flash(f"Cảm ơn {fullname} đã gửi thông tin liên hệ! Chúng tôi sẽ phản hồi sớm nhất.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    return render_template("profile.html", user=user)


@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    fullname = request.form.get("fullname")
    user = db.session.get(User, session["user_id"])
    if user:
        user.fullname = fullname
        db.session.commit()
        session["fullname"] = fullname
        flash("Cập nhật thông tin cá nhân thành công!", "success")

    return redirect(url_for("profile"))


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    user = db.session.get(User, session["user_id"])

    if not user or user.password != current_password:
        flash("Mật khẩu hiện tại không chính xác!", "danger")
        return redirect(url_for("profile"))

    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận mật khẩu không khớp!", "danger")
        return redirect(url_for("profile"))

    user.password = new_password
    db.session.commit()

    flash("Đổi mật khẩu thành công!", "success")
    return redirect(url_for("profile"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Tên đăng nhập không chính xác!", "danger")
            return redirect(url_for("forgot_password"))

        session["reset_user_id"] = user.id
        flash("Xác minh thành công! Vui lòng nhập mật khẩu mới.", "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    reset_user_id = session.get("reset_user_id")
    if not reset_user_id:
        flash("Phiên làm việc không hợp lệ hoặc đã hết hạn!", "warning")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Mật khẩu xác nhận không khớp!", "danger")
            return redirect(url_for("reset_password"))

        user = db.session.get(User, reset_user_id)
        if user:
            user.password = new_password
            db.session.commit()
            session.pop("reset_user_id", None)

            flash("Đặt lại mật khẩu thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route('/api/check-new-feedbacks')
def check_new_feedbacks():
    total = Feedback.query.count()
    return jsonify({'total': total})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)