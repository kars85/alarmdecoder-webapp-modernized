# -*- coding: utf-8 -*-

# --- Standard Imports ---
import os
import sys
import signal
import logging
import datetime

# --- Flask and Extensions ---
from flask import Flask, request, render_template, g, redirect, url_for, current_app
from flask.cli import with_appcontext
from flask_socketio import SocketIO
from flask_login import current_user
from logging.handlers import RotatingFileHandler
import click

# --- Application Specific Imports ---
from .config import DefaultConfig, TestConfig
from .extensions import db, mail, login_manager, oid, babel
from .utils import INSTANCE_FOLDER_PATH, user_is_authenticated
from .settings.models import Setting
from .setup.constants import SETUP_COMPLETE, SETUP_STAGE_ENDPOINT, SETUP_ENDPOINT_STAGE
from .user.models import User

# --- Blueprints ---
from .blueprints.main import main
from .updater.views import updater
from ad2web.user.views import user
from ad2web.settings.views import settings
from ad2web.api import api
from ad2web.admin.views import admin
from .certificate import certificate
from .log import log
from .keypad import keypad
from .notifications import notifications
from .zones import zones
from .setup import setup
from .cameras import cameras
from .decoder import decodersocket, Decoder, create_decoder_socket
from ad2web.frontend.views import frontend
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

__all__ = ["create_app"]

DEFAULT_BLUEPRINTS = (
    main,
    admin,
    user,
    settings,
    frontend,
    api,
    certificate,
    log,
    keypad,
    decodersocket,
    notifications,
    zones,
    setup,
    updater,
    cameras,
)


# --- Middleware ---
class ReverseProxied:
    """Middleware to handle reverse proxy headers."""
    def __init__(self, wsgi_app, num_proxies=1):
        self.app = wsgi_app
        self.num_proxies = num_proxies

    def get_remote_addr(self, forwarded_for):
        forwarded_for = [x.strip() for x in forwarded_for if x.strip()]
        if len(forwarded_for) >= self.num_proxies:
            return forwarded_for[-self.num_proxies]
        return None

    def __call__(self, environ, start_response):
        getter = environ.get
        forwarded_proto = getter("HTTP_X_FORWARDED_PROTO", "")
        forwarded_for_str = getter("HTTP_X_FORWARDED_FOR", "")
        forwarded_host = getter("HTTP_X_FORWARDED_HOST", "")
        script_name = getter("HTTP_X_SCRIPT_NAME", "")
        scheme = getter("HTTP_X_SCHEME", "")
        server = getter("HTTP_X_FORWARDED_SERVER", "")

        if scheme:
            environ["wsgi.url_scheme"] = scheme
        elif forwarded_proto:
            environ["wsgi.url_scheme"] = forwarded_proto

        if server:
            environ["HTTP_HOST"] = server
        elif forwarded_host:
            environ["HTTP_HOST"] = forwarded_host

        if forwarded_for_str:
            remote = self.get_remote_addr(forwarded_for_str.split(","))
            if remote:
                environ["REMOTE_ADDR"] = remote

        if script_name:
            orig_sn = environ.get("SCRIPT_NAME", "")
            orig_pi = environ.get("PATH_INFO", "")
            combined = f"{orig_sn.rstrip('/')}/{script_name.lstrip('/')}"
            environ["SCRIPT_NAME"] = combined
            if orig_pi.startswith(script_name):
                new_pi = orig_pi[len(script_name) :]
                environ["PATH_INFO"] = new_pi if new_pi.startswith("/") else f"/{new_pi}"

        return self.app(environ, start_response)


# --- App Factory ---
def create_app(config=None, app_name=None, blueprints=None):
    """Create a Flask app."""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    os.makedirs(INSTANCE_FOLDER_PATH, exist_ok=True)
    flask_app = Flask(
        app_name,
        instance_path=INSTANCE_FOLDER_PATH,
        instance_relative_config=True,
    )

    configure_app(flask_app, config)
    flask_app.wsgi_app = ReverseProxied(
        flask_app.wsgi_app,
        num_proxies=flask_app.config.get("NUM_PROXIES", 1),
    )

    configure_extensions(flask_app)
    configure_blueprints(flask_app, blueprints)
    configure_logging(flask_app)
    configure_template_filters(flask_app)
    configure_template_globals(flask_app)
    configure_hook(flask_app)
    configure_error_handlers(flask_app)
    register_commands(flask_app)

    # Initialize SocketIO and decoder
    socketio = SocketIO(flask_app)
    create_decoder_socket(flask_app)
    decoder = Decoder(flask_app)
    flask_app.decoder = decoder

    return flask_app, socketio


# --- Configuration Functions ---
def configure_app(app, config_override=None):
    app.config.from_object("ad2web.config.DefaultConfig")
    app.config.from_pyfile("config.py", silent=True)
    app.config.from_pyfile("production.cfg", silent=True)
    if config_override:
        if isinstance(config_override, dict):
            app.config.update(config_override)
        else:
            app.config.from_object(config_override)
    app.config.setdefault("LOG_FOLDER", os.path.join(app.instance_path, "logs"))
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads"))
    app.config.setdefault("OPENID_FS_STORE_PATH", os.path.join(app.instance_path, "openid_store"))
    app.config.setdefault("PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def configure_extensions(app):
    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "frontend.login"
    login_manager.refresh_view = "frontend.reauth"
    login_manager.login_message_category = "info"
    if oid:
        oid.init_app(app)
        store = app.config.get("OPENID_FS_STORE_PATH")
        if store:
            os.makedirs(store, exist_ok=True)
            oid.fs_store_path = store


def configure_blueprints(app, blueprints):
    """
    Register every blueprint twice:
     1) Under its existing blueprint.url_prefix (legacy),
     2) Under a stripped path (alias) when url_prefix starts with '/settings'.
    """
    for bp in blueprints:
        # 1) Legacy registration
        app.register_blueprint(bp)

        # 2) Alias registration: strip '/settings' from the prefix
        if bp.url_prefix and bp.url_prefix.startswith("/settings"):
            alias = bp.url_prefix.replace("/settings", "", 1) or "/"
            # Temporarily allow re-registration by clearing the blueprint cache
            app.blueprints.pop(bp.name, None)
            app.register_blueprint(bp, url_prefix=alias)


def configure_template_filters(app):
    @app.template_filter()
    def format_date(value, format="%Y-%m-%d %H:%M"):
        if isinstance(value, datetime.datetime):
            return value.strftime(format)
        return value


def configure_template_globals(app):
    @app.context_processor
    def inject_globals():
        return dict(user_is_authenticated=user_is_authenticated)


def configure_logging(app):
    level = logging.DEBUG if app.config["DEBUG"] else logging.INFO
    app.logger.setLevel(level)
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
    ch.setFormatter(fmt)
    if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
        app.logger.addHandler(ch)
    # File handler
    if not app.debug and not app.testing:
        lf = app.config["LOG_FOLDER"]
        os.makedirs(lf, exist_ok=True)
        fp = os.path.join(lf, "ad2web.log")
        fh = RotatingFileHandler(fp, maxBytes=5e6, backupCount=5)
        fh.setLevel(logging.INFO if not app.config.get("VERBOSE_LOGGING") else logging.DEBUG)
        fh.setFormatter(fmt)
        app.logger.addHandler(fh)
    app.logger.info("AlarmDecoder Webapp logging configured.")  # :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}


def configure_hook(app):
    @app.before_request
    def before_request_checks():
        safe = {"setup", "static", None}
        g.alarmdecoder = getattr(app, "decoder", None)
        if not app.testing and request.blueprint not in safe:
            try:
                stage = db.session.query(Setting.value).filter_by(name="setup_stage").scalar()
            except Exception as e:
                app.logger.error(f"Error querying setup_stage: {e}", exc_info=True)
                stage = None

            if stage is None and request.endpoint not in {"setup.index","setup.type"}:
                return redirect(url_for("setup.index"))
            if stage not in (None, SETUP_COMPLETE):
                req = SETUP_ENDPOINT_STAGE.get(request.endpoint)
                if request.blueprint != "setup" or (req and req > stage):
                    tgt = SETUP_STAGE_ENDPOINT.get(stage, "setup.index")
                    return redirect(url_for(tgt))
        return None

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def configure_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_page(err):
        return render_template("errors/forbidden_page.html"), 403

    @app.errorhandler(404)
    def page_not_found(err):
        return render_template("errors/page_not_found.html"), 404

    @app.errorhandler(500)
    def server_error(err):
        return render_template("errors/server_error.html"), 500


def register_commands(app):
    @app.cli.command("initdb")
    @click.option("--drop", is_flag=True, help="Drop all tables before creating.")
    @with_appcontext
    def initdb_command(drop):
        root = app.config.get("PROJECT_ROOT", os.path.dirname(os.path.dirname(__file__)))
        alembic_ini = os.path.join(root, "alembic.ini")
        alembic_cfg = AlembicConfig(alembic_ini) if os.path.exists(alembic_ini) else None

        if drop and click.confirm("Drop existing tables?", abort=True):
            db.drop_all()
            click.echo("Dropped database tables.")
        click.echo("Creating database tables...")
        try:
            db.create_all()
            if alembic_cfg:
                alembic_command.stamp(alembic_cfg, "head")
            click.echo("Database initialization complete!")
        except Exception as e:
            db.session.rollback()
            click.echo(f"Init DB failed: {e}", err=True)
            app.logger.error(f"Init DB failed: {e}", exc_info=True)


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# --- Main Execution ---
if __name__ == "__main__":
    flask_app, socketio = create_app()
    socketio.run(
        flask_app,
        host=flask_app.config.get("HOST", "0.0.0.0"),
        port=flask_app.config.get("PORT", 5000),
        debug=flask_app.debug,
        use_reloader=flask_app.debug,
    )
