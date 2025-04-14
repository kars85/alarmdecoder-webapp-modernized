# ad2web/views/__init__.py
from flask import Blueprint
from . import routes  # noqa: F401

main = Blueprint('main', __name__)
