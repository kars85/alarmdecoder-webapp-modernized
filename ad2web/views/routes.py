# ad2web/views/routes.py

from flask import render_template, current_app
from . import main

@main.route('/')
def index():
    decoder = current_app.decoder

    # You could pull status, config, version, etc.
    panel_status = str(decoder)  # customize this based on your decoder API

    return render_template('index.html', panel_status=panel_status)