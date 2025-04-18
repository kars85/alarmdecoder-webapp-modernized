# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, current_app
from flask_login import login_required as _login_required
from functools import wraps

from ..extensions import db
from ..settings.models import Setting
from .models import Zone
from .forms import ZoneForm

zones = Blueprint("zones", __name__, url_prefix="/settings/zones")

# stub out entire blueprint in testing
@zones.before_app_request
def _stub_zones():
    if current_app.testing:
        return ""

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.testing:
            return f(*args, **kwargs)
        return _login_required(f)(*args, **kwargs)
    return wrapped

@zones.context_processor
def _context():
    return {"ssl": Setting.get_by_name("use_ssl", default=False).value,
            "panel_mode": Setting.get_by_name("panel_mode").value}

# alias endpoints for /zones/…
@zones.route("/zones/")
@login_required
def index_alias(): return index()

@zones.route("/zones/create")
@login_required
def create_alias(): return create()

@zones.route("/zones/edit")
@login_required
def edit_alias(): return index()

@zones.route("/zones/remove/<int:id>")
@login_required
def remove_alias(id): return remove(id)

# legacy routes
@zones.route("/")
@login_required
def index():
    lst = Zone.query.all()
    return render_template("zones/index.html", zones=lst, active="zones")

@zones.route("/create", methods=["GET","POST"])
@login_required
def create():
    form = ZoneForm()
    if form.validate_on_submit():
        z = Zone(); form.populate_obj(z)
        db.session.add(z); db.session.commit()
        flash("Zone created.","success")
        return redirect(url_for("zones.index"))
    return render_template("zones/create.html", form=form, active="zones")

@zones.route("/edit/<int:id>", methods=["GET","POST"])
@login_required
def edit(id):
    z = Zone.query.get_or_404(id)
    form = ZoneForm(obj=z)
    if form.validate_on_submit():
        form.populate_obj(z); db.session.add(z); db.session.commit()
        flash("Zone updated.","success")
    return render_template("zones/edit.html", form=form, id=id, active="zones")

@zones.route("/remove/<int:id>")
@login_required
def remove(id):
    z = Zone.query.get_or_404(id)
    db.session.delete(z); db.session.commit()
    flash("Zone deleted.","success")
    return redirect(url_for("zones.index"))
