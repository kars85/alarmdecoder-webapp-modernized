# ad2web/frontend/__init__.py

from flask import Blueprint, render_template

frontend = Blueprint("frontend", __name__, template_folder="templates")


@frontend.route("/")
def index():
    return render_template("index.html")


__all__ = ["frontend"]
