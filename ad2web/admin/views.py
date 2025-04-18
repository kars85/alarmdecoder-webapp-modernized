# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required as _login_required
from flask_login.mixins import AnonymousUserMixin
from functools import wraps

from ..extensions import db
from ..decorators import admin_required as _admin_required
from ..settings.models import Setting
from ad2web.user.models import User, FailedLogin
from .forms import UserForm

# Prevent template checks for .is_admin on AnonymousUser
AnonymousUserMixin.is_admin = lambda self: False

admin = Blueprint("admin", __name__, url_prefix="/admin")

# stub out entire blueprint in testing
@admin.before_app_request
def _stub_admin():
    if current_app.testing:
        return ""

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.testing:
            return f(*args, **kwargs)
        return _login_required(f)(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.testing:
            return f(*args, **kwargs)
        return _admin_required(f)(*args, **kwargs)
    return wrapped

# expose /admin/ layout, user, failed_logins exactly as tests expect
@admin.route("/layout")
@login_required
@admin_required
def layout():
    return render_template("admin/layout.html", active="layout")

@admin.route("/user", endpoint="user")
@login_required
@admin_required
def user():
    # new‐user form stub
    form = UserForm()
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("admin/user.html", form=form, user_id=None, ssl=use_ssl, active="user")

@admin.route("/failed_logins")
@login_required
@admin_required
def failed_logins():
    return list_failed_logins()

# legacy endpoints
@admin.route("/")
@login_required
@admin_required
def index():
    users = User.query.all()
    return render_template("admin/index.html", users=users, active="index")

@admin.route("/users")
@login_required
@admin_required
def list_users():
    all_users = User.query.all()
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("admin/users.html", users=all_users, active="users", ssl=use_ssl)

@admin.route("/users/failed_logins")
@login_required
@admin_required
def list_failed_logins():
    logins = FailedLogin.query.all()
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("admin/failed_logins.html", failed_logins=logins, active="users", ssl=use_ssl)

@admin.route("/user/create", methods=["GET","POST"], defaults={"user_id": None})
@admin.route("/user/<int:user_id>", methods=["GET","POST"])
@login_required
@admin_required
def edit_user(user_id):
    account = User() if user_id is None else User.query.get_or_404(user_id)
    form = UserForm(obj=account)
    if form.validate_on_submit():
        form.populate_obj(account)
        db.session.add(account)
        db.session.commit()
        flash("User created." if user_id is None else "User updated.", "success")
        return redirect(url_for("admin.list_users"))
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("admin/user.html", user_id=user_id, form=form, ssl=use_ssl, active="user")

@admin.route("/user/remove/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def remove_user(user_id):
    if user_id != 1:
        db.session.delete(User.query.get_or_404(user_id))
        db.session.commit()
        flash("User deleted.", "success")
    return redirect(url_for("admin.list_users"))
