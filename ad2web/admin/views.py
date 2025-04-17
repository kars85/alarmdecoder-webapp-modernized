# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..decorators import admin_required

from ..user import User, FailedLogin
from .forms import UserForm
from ..settings import Setting


admin = Blueprint("admin", __name__, url_prefix="/admin")


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
    return render_template(
        "admin/failed_logins.html", failed_logins=logins, active="users", ssl=use_ssl
    )


@admin.route("/user/create", methods=["GET", "POST"], defaults={"user_id": None})
@admin.route("/user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    account = User()
    form = UserForm()

    if user_id is not None:
        account = User.query.filter_by(id=user_id).first_or_404()
        form = UserForm(obj=account, next=request.args.get("next"))

    if form.validate_on_submit():
        form.populate_obj(account)
        try:
            db.session.add(account)
            db.session.commit()
        except IntegrityError:
            flash("Duplicate user data, please use unique names and emails for each user.", "error")
            return redirect(url_for("admin.list_users"))

        flash("User created." if user_id is None else "User updated.", "success")
        return redirect(url_for("admin.list_users"))

    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("admin/user.html", user_id=user_id, form=form, ssl=use_ssl)


@admin.route("/user/remove/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def remove(user_id):
    target_user = User.query.filter_by(id=user_id).first_or_404()
    if user_id != 1:
        db.session.delete(target_user)
        db.session.commit()
        flash("User deleted.", "success")
    return redirect(url_for("admin.list_users"))
