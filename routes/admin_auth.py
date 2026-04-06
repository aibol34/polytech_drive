from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from extensions import db, login_manager
from models import Admin
from utils.csrf import validate_csrf

bp = Blueprint("admin_auth", __name__, template_folder="../templates")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(Admin, int(user_id))


@bp.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        validate_csrf()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = Admin.query.filter_by(username=username).first()
        if user and user.check_password(password):
            remember = request.form.get("remember") == "1"
            login_user(user, remember=remember)
            next_url = request.args.get("next") or url_for("admin_panel.dashboard")
            return redirect(next_url)
        flash("Неверный логин или пароль.", "error")
    return render_template("admin/login.html")


@bp.route("/admin/logout", methods=["POST"])
def logout():
    validate_csrf()
    logout_user()
    return redirect(url_for("admin_auth.login"))
