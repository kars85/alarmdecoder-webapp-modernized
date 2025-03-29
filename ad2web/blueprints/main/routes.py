from flask import render_template, current_app
from . import main

@main.route('/')
def index():
    return render_template('index.html', panel_status="System OK")
