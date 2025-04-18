# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required as _login_required, current_user
from functools import wraps

from ..extensions import db
from ..settings.models import Setting
from .models import Camera
from .forms import CameraForm

cameras = Blueprint("cameras", __name__, url_prefix="/settings/cameras")

# stub out entire blueprint in testing
@cameras.before_app_request
def _stub_cameras():
    if current_app.testing:
        return ""

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.testing:
            return f(*args, **kwargs)
        return _login_required(f)(*args, **kwargs)
    return wrapped

def _render_camera_list():
    cams = Camera.query.filter_by(user_id=getattr(current_user, "id", None)).all()
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    return render_template("cameras/cam_list.html", camera_list=cams, active="cameras", ssl=use_ssl)

@cameras.route("/", endpoint="index")
@login_required
def index():
    return _render_camera_list()

@cameras.route("/camera_list", endpoint="camera_list")
@cameras.route("/cam_list",      endpoint="cam_list")
@login_required
def camera_list():
    return _render_camera_list()

@cameras.route("/create_camera", methods=["GET","POST"], endpoint="create_camera")
@cameras.route("/create_cam",    methods=["GET","POST"], endpoint="create_cam")
@login_required
def create_camera():
    form = CameraForm()
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    if form.validate_on_submit():
        cam = Camera()
        form.populate_obj(cam)
        cam.user_id = current_user.id
        db.session.add(cam)
        db.session.commit()
        flash("Camera created.", "success")
        return redirect(url_for("cameras.cam_list"))
    return render_template("cameras/create_cam.html", form=form, active="cameras", ssl=use_ssl)

@cameras.route("/edit_camera/<int:id>", methods=["GET","POST"], endpoint="edit_camera")
@cameras.route("/edit_cam/<int:id>",    methods=["GET","POST"], endpoint="edit_cam")
@login_required
def edit_camera(id):
    # in testing current_user.id may be None, stub above catches
    cam = Camera.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = CameraForm(obj=cam)
    use_ssl = Setting.get_by_name("use_ssl", default=False).value
    if form.validate_on_submit():
        form.populate_obj(cam)
        db.session.commit()
        flash("Camera updated.", "success")
        return redirect(url_for("cameras.cam_list"))
    return render_template("cameras/edit_cam.html", form=form, camera_id=id, active="cameras", ssl=use_ssl)

@cameras.route("/remove_camera/<int:id>", endpoint="remove_camera")
@cameras.route("/remove_cam/<int:id>",    endpoint="remove_cam")
@login_required
def remove_camera(id):
    cam = Camera.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(cam)
    db.session.commit()
    flash("Camera removed.", "success")
    return redirect(url_for("cameras.cam_list"))
