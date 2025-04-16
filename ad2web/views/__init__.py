# ad2web/views/__init__.py
from flask import Blueprint
from . import routes  # noqa: F401

frontend = Blueprint('frontend', __name__)
