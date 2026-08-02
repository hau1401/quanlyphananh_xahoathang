import os
import random
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

from config import Config
from models import db, Category, Feedback, User

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
app.secret_key = "ubnd_hoa_thang_secret_key_123"

# 🔥 SỬA LỖI 404: Sử dụng app.root_path để xác định chính xác vị trí thư mục static/uploads
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ==========================================
# DECORATORS BẢO MẬT & PHÂN QUYỀN
# ==========================================

# 1. Kiểm tra đăng nhập bắt buộc
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Vui lòng đăng nhập để sử dụng chức năng này!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# 2. Kiểm tra quyền Admin bắt buộc
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
    return render_template("index.html", categories=categories)


@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    categories = Category.query.all()

    if request.method == "POST":
        filename = ""

        # Xử lý file ảnh được tải lên từ form
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "":
                # Thêm chuỗi thời gian vào tên file để không bị trùng lặp
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)

        fb_item = Feedback(
            feedback_code=generate_feedback_code(),
            fullname=request.form["fullname"],
            phone=request.form["phone"],
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            category_id=request.form["category"],
            title=request.form["title"],
            content=request.form["content"],
            image=filename,  # Lưu tên file thực tế vào CSDL
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

        # Truy vấn tìm tài khoản trong CSDL
        user = User.query.filter_by(username=username).first()

        # 1. Kiểm tra tài khoản có tồn tại hay không
        if not user:
            flash("Tên đăng nhập không tồn tại trong hệ thống!", "danger")
            return redirect(url_for("login"))

        # 2. Kiểm tra mật khẩu
        if user.password != password:
            flash("Mật khẩu không chính xác, vui lòng thử lại!", "danger")
            return redirect(url_for("login"))

        # 3. Đăng nhập thành công -> Lưu dữ liệu vào Session
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

        # Kiểm tra trùng tên đăng nhập trong CSDL
        check_user = User.query.filter_by(username=username).first()

        if check_user:
            flash("Tên đăng nhập này đã tồn tại!", "warning")
            return redirect(url_for("register"))

        # Tạo user mới
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

# Bảng điều khiển Admin
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

    return render_template(
        "admin/dashboard.html",
        total_feedbacks=total_feedbacks,
        pending_count=pending_count,
        processing_count=processing_count,
        completed_count=completed_count,
        total_users=total_users,
        feedbacks=feedbacks,
        categories=categories,
        users=users
    )


# Cập nhật trạng thái phản ánh
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


# Xóa phản ánh rác
@app.route("/admin/feedback/delete/<int:feedback_id>", methods=["POST"])
@admin_required
def delete_feedback(feedback_id):
    fb = db.session.get(Feedback, feedback_id)
    if fb:
        db.session.delete(fb)
        db.session.commit()
        flash("Đã xóa phản ánh thành công!", "success")
    return redirect(url_for("dashboard"))


# Phân quyền người dùng (Chuyển giữa Staff và Admin)
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


# Xóa tài khoản người dùng
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


# Thêm danh mục/lĩnh vực phản ánh mới
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


# Xóa danh mục/lĩnh vực phản ánh
@app.route("/admin/category/delete/<int:cat_id>", methods=["POST"])
@admin_required
def delete_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if cat:
        db.session.delete(cat)
        db.session.commit()
        flash("Đã xóa danh mục thành công!", "success")
    return redirect(url_for("dashboard"))


# ==========================================
# 4. CÁC TRANG TĨNH (GIỚI THIỆU, TIN TỨC, LIÊN HỆ)
# ==========================================

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/news")
def news():
    return render_template("news.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        fullname = request.form.get("fullname")
        flash(f"Cảm ơn {fullname} đã gửi thông tin liên hệ! Chúng tôi sẽ phản hồi sớm nhất.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


# ==========================================
# 5. QUẢN LÝ TÀI KHOẢN CÁ NHÂN & ĐỔI MẬT KHKHẨU
# ==========================================

@app.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    return render_template("profile.html", user=user)


@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    fullname = request.form.get("fullname")
    phone = request.form.get("phone")
    email = request.form.get("email")

    user = db.session.get(User, session["user_id"])
    if user:
        user.fullname = fullname
        if hasattr(user, 'phone'):
            user.phone = phone
        if hasattr(user, 'email'):
            user.email = email

        db.session.commit()

        # Cập nhật lại tên hiển thị trên Navbar
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

    # 1. Kiểm tra mật khẩu cũ trong CSDL
    if not user or user.password != current_password:
        flash("Mật khẩu hiện tại không chính xác!", "danger")
        return redirect(url_for("profile"))

    # 2. Kiểm tra mật khẩu mới và xác nhận mật khẩu
    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận mật khẩu không khớp!", "danger")
        return redirect(url_for("profile"))

    # 3. Cập nhật mật khẩu mới vào CSDL
    user.password = new_password
    db.session.commit()

    flash("Đổi mật khẩu thành công! Vui lòng dùng mật khẩu mới cho lần đăng nhập sau.", "success")
    return redirect(url_for("profile"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")

        # Tìm tài khoản theo username
        user = User.query.filter_by(username=username).first()

        # Kiểm tra sự tồn tại của user và khớp Email
        if not user or (hasattr(user, 'email') and user.email != email):
            flash("Tên đăng nhập hoặc Email không chính xác!", "danger")
            return redirect(url_for("forgot_password"))

        # Xác thực thành công -> Lưu ID vào session tạm thời
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

        # Cập nhật mật khẩu mới vào CSDL
        user = db.session.get(User, reset_user_id)
        if user:
            user.password = new_password
            db.session.commit()

            # Xóa session tạm
            session.pop("reset_user_id", None)

            flash("Đặt lại mật khẩu thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for("login"))

    return render_template("reset_password.html")


if __name__ == "__main__":
    app.run(debug=True)