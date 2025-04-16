# -*- coding: utf-8 -*-
"""
ad2web.frontend.views
~~~~~~~~~~~~~~~~~~~~~

Frontend views for login, signup, index, etc.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.fields import EmailField
from wtforms.validators import DataRequired, Length, EqualTo, Email
from ad2web.user.models import User
from ad2web.extensions import db

frontend = Blueprint("frontend", __name__)

# =====================
# ====== FORMS ========
# =====================

class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class SignupForm(FlaskForm):
    name = StringField("Username", validators=[DataRequired(), Length(3, 64)])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(6, 60)])
    password_again = PasswordField("Repeat Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Sign Up")


class ResetPasswordForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Reset Password")


# =====================
# ====== ROUTES =======
# =====================

@frontend.route("/")
def index():
    return render_template("frontend/index.html")

@frontend.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Placeholder logic – replace with actual user lookup
        flash("Logged in successfully.", "success")
        return redirect(url_for("frontend.index"))
    return render_template("frontend/login.html", form=form)


@frontend.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("frontend.index"))


@frontend.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Create and persist a new user
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=form.password.data,
            role="user"
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully.", "success")
        return redirect(url_for("frontend.login"))
    return render_template("frontend/signup.html", form=form)



@frontend.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Placeholder for password reset logic
        flash("Password reset instructions sent.", "info")
        return redirect(url_for("frontend.login"))
    return render_template("frontend/reset_password.html", form=form)


@frontend.route("/help")
def help():
    return render_template("frontend/footers/help.html")

@frontend.route("/license")
def license():
    return render_template("frontend/license.html")

