from flask import render_template, current_app
from . import main
from .views import get_panel_status

@main.route('/')
def index():
    status = get_panel_status(current_app.decoder)
    return render_template('index.html', panel_status=status)
