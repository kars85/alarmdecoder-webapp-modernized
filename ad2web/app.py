# -*- coding: utf-8 -*-

# --- Standard Imports ---
import os
import sys
import signal
import logging
import datetime

# --- Flask and Extensions ---
from flask import Flask, request, render_template, g, redirect, url_for
from flask.cli import with_appcontext
from flask_socketio import SocketIO
from logging.handlers import RotatingFileHandler
import click

# --- Application Specific Imports ---
from .config import DefaultConfig
from .extensions import db, mail, login_manager, oid, babel
from .utils import INSTANCE_FOLDER_PATH
from .settings.models import Setting
from .setup.constants import SETUP_COMPLETE, SETUP_STAGE_ENDPOINT, SETUP_ENDPOINT_STAGE
from .user.models import User

# --- Blueprints ---
from .blueprints.main import main
from .updater.views import updater
from .user import user
from .settings import settings
from .frontend import frontend
from ad2web.api import api, api_settings
from .admin import admin
from .certificate import certificate
from .log import log
from .keypad import keypad
from .notifications import notifications
from .zones import zones
from .setup import setup
from .cameras import cameras
from .decoder import decodersocket, Decoder, create_decoder_socket

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

__all__ = ['create_app']

DEFAULT_BLUEPRINTS = (
    main,
    frontend,
    user,
    settings,
    api,
    api_settings,
    admin,
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

class ReverseProxied:
    """Middleware to handle reverse proxy headers."""
    def __init__(self, wsgi_app, num_proxies=1):
        self.app = wsgi_app
        self.num_proxies = num_proxies

    def get_remote_addr(self, forwarded_for):
        if len(forwarded_for) >= self.num_proxies:
            return forwarded_for[-1 * self.num_proxies]

    def __call__(self, environ, start_response):
        getter = environ.get
        forwarded_proto = getter('HTTP_X_FORWARDED_PROTO', '')
        forwarded_for = getter('HTTP_X_FORWARDED_FOR', '').split(',')
        forwarded_host = getter('HTTP_X_FORWARDED_HOST', '')
        script_name = getter('HTTP_X_SCRIPT_NAME', '')
        scheme = getter('HTTP_X_SCHEME', '')
        server = getter('HTTP_X_FORWARDED_SERVER', '')

        if scheme:
            environ['wsgi.url_scheme'] = scheme
        elif forwarded_proto:
            environ['wsgi.url_scheme'] = forwarded_proto

        if server:
            environ['HTTP_HOST'] = server
        elif forwarded_host:
            environ['HTTP_HOST'] = forwarded_host

        forwarded_for = [x.strip() for x in forwarded_for if x.strip()]
        remote_addr = self.get_remote_addr(forwarded_for)
        if remote_addr:
            environ['REMOTE_ADDR'] = remote_addr

        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        return self.app(environ, start_response)

def create_app(config=None, app_name=None, blueprints=None):
    """Create a Flask app."""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    flask_app = Flask(app_name, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)
    flask_app.wsgi_app = ReverseProxied(flask_app.wsgi_app)

    configure_app(flask_app, config)
    configure_hook(flask_app)
    configure_extensions(flask_app)

    socketio = SocketIO(flask_app)

    configure_blueprints(flask_app, blueprints)
    configure_logging(flask_app)
    configure_template_filters(flask_app)
    configure_error_handlers(flask_app)
    register_commands(flask_app)

    appsocket = create_decoder_socket(flask_app)
    decoder = Decoder(flask_app, appsocket)
    flask_app.decoder = decoder

    return flask_app, socketio

def init_app(flask_app, appsocket):
    """Handles tasks needed when running the app directly."""
    def signal_handler(_signal, _frame):
        print("Stopping services...")
        appsocket.stop()
        if hasattr(flask_app, 'decoder'):
            flask_app.decoder.stop()
        print("Exiting.")
        sys.exit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    with flask_app.app_context():
        try:
            _ = db.session.query(Setting).first()
            if hasattr(flask_app, 'decoder'):
                flask_app.decoder.init()
                flask_app.decoder.start()
            else:
                flask_app.logger.warning("Decoder object not found during init_app.")
        except Exception as err:
            flask_app.logger.error(f"Database connection failed: {err}", exc_info=True)

def configure_app(app, config=None):
    app.config.from_object(DefaultConfig)
    app.config.from_pyfile('config.py', silent=True)
    app.config.from_pyfile('production.cfg', silent=True)

    if config:
        app.config.from_object(config)

    app.config.setdefault('LOG_FOLDER', os.path.join(app.instance_path, 'logs'))
    app.config.setdefault('UPLOAD_FOLDER', os.path.join(app.instance_path, 'uploads'))
    app.config.setdefault('OPENID_FS_STORE_PATH', os.path.join(app.instance_path, 'openid_store'))
    app.config.setdefault('PROJECT_ROOT', os.path.dirname(os.path.dirname(__file__)))

def configure_extensions(app):
    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'frontend.login'
    login_manager.refresh_view = 'frontend.reauth'
    login_manager.login_message_category = 'info'
    if oid:
        oid.init_app(app)
        oid.fs_store_path = app.config.get('OPENID_FS_STORE_PATH')

def configure_blueprints(app, blueprints):
    for blueprint in blueprints:
        app.register_blueprint(blueprint)

def configure_template_filters(app):
    @app.template_filter()
    def format_date(value, format='%Y-%m-%d %H:%M'):
        if isinstance(value, datetime.datetime):
            return value.strftime(format)
        return value

def configure_logging(app):
    if not app.debug and not app.testing:
        log_folder = app.config['LOG_FOLDER']
        os.makedirs(log_folder, exist_ok=True)
        log_path = os.path.join(log_folder, 'ad2web.log')
        handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO if not app.config.get('VERBOSE_LOGGING') else logging.DEBUG)
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG if app.config['DEBUG'] else logging.INFO)
    app.logger.info('AlarmDecoder Webapp starting up...')

def configure_hook(app):
    safe_blueprints = {'setup', 'static', None}

    @app.before_request
    def before_request_checks():
        is_secure = request.is_secure or request.headers.get('X-Forwarded-Proto', 'http') == 'https'
        app.config['SESSION_COOKIE_SECURE'] = is_secure
        app.config['REMEMBER_COOKIE_SECURE'] = is_secure

        if request.blueprint not in safe_blueprints:
            try:
                setup_stage = db.session.query(Setting.value).filter_by(name='setup_stage').scalar()
            except Exception:
                setup_stage = None

            if setup_stage is None:
                if request.endpoint not in {'setup.index', 'setup.type'}:
                    return redirect(url_for('setup.index'))
            elif setup_stage != SETUP_COMPLETE:
                required = SETUP_ENDPOINT_STAGE.get(request.endpoint)
                if request.blueprint != 'setup' or (required and required > setup_stage):
                    target = SETUP_STAGE_ENDPOINT.get(setup_stage, 'setup.index')
                    return redirect(url_for(target))

        g.alarmdecoder = getattr(app, 'decoder', None)

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

def configure_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_page(_error):
        return render_template("errors/forbidden_page.html"), 403

    @app.errorhandler(404)
    def page_not_found(_error):
        return render_template("errors/page_not_found.html"), 404

    @app.errorhandler(500)
    def server_error_page(_error):
        app.logger.error(f"Server Error: {_error}", exc_info=True)
        return render_template("errors/server_error.html"), 500

def register_commands(app):
    @app.cli.command('initdb')
    @click.option('--drop', is_flag=True, help='Drop all tables before creating.')
    @with_appcontext
    def initdb_command(drop):
        root = app.config.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(__file__)))
        alembic_ini = os.path.join(root, 'alembic.ini')
        alembic_cfg = AlembicConfig(alembic_ini) if os.path.exists(alembic_ini) else None

        if drop:
            if click.confirm('This operation will drop existing database tables. Do you want to continue?', abort=True):
                click.echo('Dropping database tables...')
                db.drop_all()
                click.echo('Dropped database tables.')

        click.echo('Creating database tables...')
        try:
            db.create_all()
            click.echo('Initialized the database tables.')

            if alembic_cfg:
                click.echo('Stamping Alembic revision to head...')
                alembic_command.stamp(alembic_cfg, "head")
                click.echo('Alembic revision stamped.')

            click.echo('Database initialization complete!')

        except Exception as err:
            db.session.rollback()
            click.echo(f'Database initialization failed: {err}', err=True)
            app.logger.error(f'Database initialization failed: {err}', exc_info=True)

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

if __name__ == '__main__':
    flask_app, socketio = create_app()
    socketio.run(flask_app, host='0.0.0.0', port=5000, debug=flask_app.debug)

