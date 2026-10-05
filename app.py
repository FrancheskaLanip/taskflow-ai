import os
import csv
from datetime import datetime, timedelta, date
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# -----------------------------------------------------------------------------
# App configuration
# -----------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

# SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///taskflow.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Uploads for profile pictures
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

db = SQLAlchemy(app)

@app.context_processor
def inject_now():
    return {"now": datetime.now}

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    profile_pic = db.Column(db.String(200))  # stores filename in static/uploads/

    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
   
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.Date)                     # store as Date for comparisons
    category = db.Column(db.String(50))               # Work, Personal, School, etc.
    priority = db.Column(db.String(20))               # High, Medium, Low
    recurring = db.Column(db.String(20), default="None")  # None, Daily, Weekly, Monthly
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
   
# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)

def parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def next_recurring_date(current: date, mode: str):
    if not current or not mode or mode == "None":
        return None
    if mode == "Daily":
        return current + timedelta(days=1)
    if mode == "Weekly":
        return current + timedelta(weeks=1)
    if mode == "Monthly": # naive monthly add: +30 days
        return current + timedelta(days=30)
    return None

def flash_due_reminders(user_id: int): # Show in-app reminders for due today and overdue
    today = date.today()
    tasks = Task.query.filter_by(user_id=user_id, completed=False).all()
    due_today = [t for t in tasks if t.deadline == today]
    overdue = [t for t in tasks if t.deadline and t.deadline < today]
    if overdue:
        flash(f"You have {len(overdue)} overdue task(s).", "danger")
    if due_today:
        flash(f"{len(due_today)} task(s) due today.", "warning")
       
@app.context_processor
def inject_user():
    return {"current_user": current_user()}
@app.context_processor
def inject_now():
    return {"now": datetime.now}

# -----------------------------------------------------------------------------
# Routes: auth
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("menu"))
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")  
        name = request.form.get("name", "").strip()

        if not email or not password or not name:
            flash("Email, password, and name are required.", "danger")
            return redirect(url_for("signup"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please log in.", "warning")
            return redirect(url_for("login"))

        user = User(email=email, name=name)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        flash("Account created. You are now logged in.", "success")
        return redirect(url_for("menu"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Account not found. Please sign up first.", "warning")
            return redirect(url_for("signup"))
        if not user.check_password(password):
            flash("Incorrect password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash("Logged in successfully.", "success")
        return redirect(url_for("menu"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# Routes: profile (name + profile picture only)
# -----------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        profile_pic_file = request.files.get("profile_pic")

        if name:
            user.name = name

        if profile_pic_file and profile_pic_file.filename and allowed_file(profile_pic_file.filename):
            filename = f"{user.id}_{secure_filename(profile_pic_file.filename)}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            profile_pic_file.save(save_path)
            user.profile_pic = filename

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)
   
@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# -----------------------------------------------------------------------------
# Routes: dashboard
# ----------------------------------------------------------------------------
@app.route("/menu")
def menu():
    user = current_user()
    if not user:
        flash("You must be logged in.", "warning")
        return redirect(url_for("index"))

    flash_due_reminders(user.id)

    tasks = Task.query.filter_by(user_id=user.id).all()
    total = len(tasks) 
    completed = len([t for t in tasks if t.completed])
    pending = total - completed

    today = date.today()
    tomorrow = today + timedelta(days=1)

    due_today = len([t for t in tasks if (t.deadline == today) and not t.completed])
    due_tomorrow = len([t for t in tasks if (t.deadline == tomorrow) and not t.completed])
    overdue = len([t for t in tasks if (t.deadline and t.deadline < today) and not t.completed])

    progress = int((completed / total) * 100) if total > 0 else 0

    return render_template(
        "menu.html",
        user=user,
        stats={
            "total": total,
            "completed": completed,
            "pending": pending,
            "due_today": due_today,
            "due_tomorrow": due_tomorrow,
            "overdue": overdue,
            "progress": progress,
         }
    )

                                    

 # -----------------------------------------------------------------------------
 # # Routes: tasks
 # -----------------------------------------------------------------------------
@app.route("/add", methods=["GET", "POST"])
def add_task():
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        deadline_raw = request.form.get("deadline", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()
        recurring = request.form.get("recurring", "None").strip()

        if not name:
            flash("Task name is required.", "danger")
            return redirect(url_for("add_task"))

        deadline = parse_date(deadline_raw)
        t = Task(
            user_id=user.id,
            name=name,
            deadline=deadline,
            category=category if category else None,
            priority=priority if priority else None,
            recurring=recurring if recurring else "None",
            completed=False,
        )
        db.session.add(t)
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("menu"))

    today = date.today().isoformat()
    return render_template("add_task.html", today=today)

@app.route("/view")
def view_tasks():
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    status = request.args.get("status", "").strip()  # "completed" or "pending"

    tasks = Task.query.filter_by(user_id=user.id).all()

    # Apply filters
    if q:
        tasks = [t for t in tasks if q in t.name.lower()]
    if category:
        tasks = [t for t in tasks if (t.category or "") == category]
    if priority:
        tasks = [t for t in tasks if (t.priority or "") == priority]
    if status:
        tasks = [t for t in tasks if (t.completed and status == "completed") or (not t.completed and status == "pending")]

    # Sort by deadline then created_at
    tasks.sort(key=lambda t: (t.deadline or date(9999, 12, 31), t.created_at))

    return render_template("view_tasks.html", tasks=tasks, filters={"q": q, "category": category, "priority": priority, "status": status})

@app.route("/task/<int:task_id>")
def task_detail(task_id):
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    t = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not t:
        flash("Task not found.", "danger")
        return redirect(url_for("view_tasks"))

    return render_template("task_detail.html", task=t)


@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    t = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not t:
        flash("Task not found.", "danger")
        return redirect(url_for("view_tasks"))

    if request.method == "POST":
        t.name = request.form.get("name", "").strip()
        deadline_raw = request.form.get("deadline", "").strip()
        t.deadline = parse_date(deadline_raw)
        t.category = request.form.get("category", "").strip() or None
        t.priority = request.form.get("priority", "").strip() or None
        t.recurring = request.form.get("recurring", "None").strip()

        db.session.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("task_detail", task_id=t.id))

    return render_template("edit_task.html", task=t)
                                        
                                                                                                                                                                                
@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    t = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not t:
        flash("Task not found.", "danger")
        return redirect(url_for("view_tasks"))

    # If marking completed and recurring, spawn the next occurrence
    if not t.completed and t.recurring and t.recurring != "None":
        next_date = next_recurring_date(t.deadline, t.recurring)
        if next_date:
            new_task = Task(
                user_id=user.id,
                name=t.name,
                deadline=next_date,
                category=t.category,
                priority=t.priority,
                recurring=t.recurring,
                completed=False
            )
            db.session.add(new_task)

    t.completed = not t.completed
    db.session.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("view_tasks"))  

@app.route("/delete", methods=["GET", "POST"])
def delete_task(): 
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        task_id = request.form.get("task_id")
        if not task_id:
            flash("No task selected.", "danger")
            return redirect(url_for("delete_tasks"))
        t = Task.query.filter_by(id=int(task_id), user_id=user.id).first()
        if not t:
            flash("Task not found.", "danger")
            return redirect(url_for("delete_tasks"))
        db.session.delete(t)
        db.session.commit()
        flash("Task deleted.", "info")
        return redirect(url_for("menu"))

    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.deadline.asc()).all()
    return render_template("delete_task.html", tasks=tasks) 

# -----------------------------------------------------------------------------
# # Export CSV
# -----------------------------------------------------------------------------
@app.route("/export")
def export_tasks():
    user = current_user()
    if not user:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    tasks = Task.query.filter_by(user_id=user.id).all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Name", "Deadline", "Category", "Priority", "Recurring", "Completed", "CreatedAt"])
    for t in tasks:
        writer.writerow([
            t.name,
            t.deadline.isoformat() if t.deadline else "",
            t.category or "",
            t.priority or "",
            t.recurring or "None",
            "Yes" if t.completed else "No",
            t.created_at.isoformat()
        ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=tasks.csv"
        output.headers["Content-type"] = "text/csv"
        return output

# -----------------------------------------------------------------------------
 # CLI: init db
# -----------------------------------------------------------------------------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized.")                                                                                                                                           
                                                                                                                                                                   
# -----------------------------------------------------------------------------
# # Run server
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)                                                                                                                                                                           
                                                                                                                                                                             
                                                                                