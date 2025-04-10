# -*- coding: utf-8 -*-

import os
import importlib

from flask import Blueprint, render_template, send_from_directory, abort
from flask import current_app as APP
from flask_login import login_required, current_user

from ..utils import user_is_authenticated

user = Blueprint('user', __name__, url_prefix='/user')


# Function to dynamically import User to avoid circular import
def get_user():
    user_module = importlib.import_module('ad2web.user')
    return user_module.User

@user.route('/')
@login_required
def index():
    User = get_user()  # Dynamically import User
    if not user_is_authenticated(current_user):
        abort(403)
    return render_template('user/index.html', user=current_user)


@user.route('/<int:user_id>/profile')
def profile(user_id):
    User = get_user()  # Dynamically import User
    user = User.get_by_id(user_id)
    return render_template('user/profile.html', user=user)


@user.route('/<int:user_id>/avatar/<path:filename>')
@login_required
def avatar(user_id, filename):
    dir_path = os.path.join(APP.config['UPLOAD_FOLDER'], 'user_%s' % user_id)
    return send_from_directory(dir_path, filename, as_attachment=True)

@user.route('/<int:user_id>/history')
@login_required
def history(user_id):
    if user_id is None:
        abort(404)
    if not user_is_authenticated(current_user):
        abort(403)
    if not current_user.is_admin() and current_user.id != user_id:
        abort(403)

    User = get_user()  # Dynamically import User
    user = User.get_by_id(user_id)
    user_history = UserHistory.query.filter_by(user_id=user.id).all()
    return render_template('user/history.html', user=user, user_history=user_history)
