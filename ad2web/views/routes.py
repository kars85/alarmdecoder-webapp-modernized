# ad2web/views/routes.py

from flask import render_template, redirect, url_for, request
from flask_login import login_user, logout_user, current_user

from . import frontend
from .views import LoginForm, SignupForm, RecoverPasswordForm


@frontend.route("/")
def index():
    decoder = current_app.decoder
    panel_status = str(decoder)
    return render_template("index.html", panel_status=panel_status)


@frontend.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # You would put real login logic here
        return redirect(url_for("frontend.index"))
    return render_template("frontend/login.html", form=form)


@frontend.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("frontend.login"))


@frontend.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # You would put real signup logic here
        return redirect(url_for("frontend.index"))
    return render_template("frontend/signup.html", form=form)


@frontend.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    form = RecoverPasswordForm()
    if form.validate_on_submit():
        # Simulate sending email reset
        return redirect(url_for("frontend.login"))
    return render_template("frontend/reset_password.html", form=form)


@frontend.route("/help")
def help():
    return render_template("frontend/footers/help.html")
