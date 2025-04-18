# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, current_app, flash
from flask_login import login_user, logout_user, current_user
from .forms import LoginForm, SignupForm, RecoverPasswordForm

frontend = Blueprint("frontend", __name__)

@frontend.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # real auth logic goes here…
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
        # real signup logic goes here…
        return redirect(url_for("frontend.index"))
    return render_template("frontend/signup.html", form=form)

@frontend.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    form = RecoverPasswordForm()
    if form.validate_on_submit():
        # pretend we sent an email…
        return redirect(url_for("frontend.login"))
    return render_template("frontend/reset_password.html", form=form)

@frontend.route("/help")
def help():
    return render_template("frontend/footers/help.html")
