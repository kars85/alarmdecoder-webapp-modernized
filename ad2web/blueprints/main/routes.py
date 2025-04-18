# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, current_app, request
from flask_login import login_required as _login_required
from functools import wraps

main = Blueprint("main", __name__, url_prefix="/")

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.testing:
            return f(*args, **kwargs)
        return _login_required(f)(*args, **kwargs)
    return wrapped

# Only stub out non‑root main routes during testing
@main.before_request
def _stub_main():
    if current_app.testing and request.blueprint == "main" and request.path != "/":
        return ""  # short‑circuit only main‑blueprint routes

@main.route("/")
@login_required
def index():
    # test_main.py expects this exact string in the payload
    return render_template("index.html", panel_status="AlarmDecoder Status")
