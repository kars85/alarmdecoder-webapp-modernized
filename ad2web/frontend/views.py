# -*- coding: utf-8 -*-
"""
ad2web.frontend.views
~~~~~~~~~~~~~~~~~~~~~

Frontend views for login, signup, index, etc.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
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
    agree = BooleanField("I agree to the terms", validators=[DataRequired()])
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
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("frontend.index"))
        flash("Invalid email or password.", "danger")

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

    if request.method == "POST":
        if form.validate_on_submit():
            # Check for existing email or username
            existing_user = User.query.filter(
                (User.email == form.email.data) | (User.name == form.name.data)
            ).first()

            if existing_user:
                flash("A user with that email or username already exists.", "danger")
                return redirect(url_for("frontend.signup"))

            # Create new user
            user = User(
                name=form.name.data,
                email=form.email.data,
            )
            role = "user"
            user.password = form.password.data
            db.session.add(user)
            db.session.commit()

            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("frontend.login"))

        # DEBUG: Show form errors during development
        print("Signup form validation errors:", form.errors)

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

