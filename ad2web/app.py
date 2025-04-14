# -*- coding: utf-8 -*-
# In ad2web/app.py


# --- Standard Imports ---
import os
import signal
import logging
import datetime


# --- Flask and Extensions ---
from flask import Flask, request, render_template, g, redirect, url_for
from flask.cli import with_appcontext
from flask_socketio import SocketIO  # Import SocketIO here
import click  # For CLI commands

# --- AlarmDecoder ---

# --- Application Specific Imports ---
from .config import DefaultConfig
from .extensions import db, mail, login_manager, oid, babel  # Added babel here from configure_extensions
from .utils import INSTANCE_FOLDER_PATH  # Only import needed path from utils here
from .settings.models import Setting
from .setup.constants import SETUP_COMPLETE, SETUP_STAGE_ENDPOINT, SETUP_ENDPOINT_STAGE
from .user.models import User  # Needed for LoginManager user_loader

# --- Blueprints ---
from .blueprints.main import main  # Import main blueprint
from .updater.views import updater
from .user import user
from .settings import settings
from .frontend import frontend
import api, api_settings
from .admin import admin
from .certificate import certificate
from .log import log
from .keypad import keypad
from .notifications import notifications
from .zones import zones
from .setup import setup
from .cameras import cameras
from .decoder import decodersocket, Decoder, create_decoder_socket  # Moved later, needs app context

# --- Imports for initdb Command ---
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

# For import *
__all__ = ['create_app']

# --- Define Blueprints to Register ---
DEFAULT_BLUEPRINTS = (
    main,          # Add main blueprint
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

# --- Middleware ---
class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    :param app: the WSGI application
    '''
    def __init__(self, app, num_proxies=1):
        self.app = app
        self.num_proxies = num_proxies

    def get_remote_addr(self, forwarded_for):
        """Selects the new remote addr from given list of ips in X-Forwarded-For
        By default it picks the one that the num_proxies proxy server provides.
        """
        if len(forwarded_for) >= self.num_proxies:
            return forwarded_for[-1 * self.num_proxies]

    def __call__(self, environ, start_response):
        # Adapted from werkzeug fixer ProxyFix (consider using werkzeug.middleware.ProxyFix instead)
        getter = environ.get
        forwarded_proto = getter('HTTP_X_FORWARDED_PROTO', '')
        forwarded_for = getter('HTTP_X_FORWARDED_FOR', '').split(',')
        forwarded_host = getter('HTTP_X_FORWARDED_HOST', '')
        script_name = getter('HTTP_X_SCRIPT_NAME', '')
        scheme = getter('HTTP_X_SCHEME', '')
        server = getter('HTTP_X_FORWARDED_SERVER', '')

        # Update scheme
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        elif forwarded_proto:
            environ['wsgi.url_scheme'] = forwarded_proto

        # Update host/server
        if server:
             environ['HTTP_HOST'] = server
        elif forwarded_host:
            environ['HTTP_HOST'] = forwarded_host

        # Update remote address
        forwarded_for = [x for x in [x.strip() for x in forwarded_for] if x]
        remote_addr = self.get_remote_addr(forwarded_for)
        if remote_addr is not None:
            environ['REMOTE_ADDR'] = remote_addr

        # Update script name (path prefix)
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        return self.app(environ, start_response)

# --- Application Factory ---
def create_app(config=None, app_name=None, blueprints=None):
    """Create a Flask app."""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    # Create Flask app instance
    app = Flask(app_name, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)

    # Apply middleware (important: apply before other configs if they depend on fixed environ)
    app.wsgi_app = ReverseProxied(app.wsgi_app)

    # Configure the app from objects/files
    configure_app(app, config)

    # Configure hooks (before/after request)
    configure_hook(app)

    # Configure extensions (db, mail, login, etc.)
    configure_extensions(app)  # Make sure this is called BEFORE blueprints if they use extensions

    # Initialize SocketIO here
    socketio = SocketIO(app)

    # Configure blueprints (register views)
    configure_blueprints(app, blueprints)

    # Configure logging
    configure_logging(app)

    # Configure template filters
    configure_template_filters(app)

    # Configure error handlers
    configure_error_handlers(app)

    # Configure CLI Commands (like initdb)
    register_commands(app)  # Call command registration

    # --- Setup Application Specific Services ---
    # These might need the app context or configured extensions
    appsocket = create_decoder_socket(app)
    decoder = Decoder(app, appsocket)
    app.decoder = decoder  # Attach decoder service to app

    # --- Debug Print ---
    # print(f"\n!!! Factory in ad2web/app.py returning: {(app, appsocket)}\n")

    return app, socketio  # Return tuple for potential use by caller

# --- Initialization for Running Server (Not part of factory) ---
def init_app(app, appsocket):
    """Handles tasks needed when running the app directly (like starting decoder)."""
    def signal_handler(signal, frame):
        print("Stopping services...")
        appsocket.stop()
        if hasattr(app, 'decoder'):
             app.decoder.stop()
        print("Exiting.")
        os._exit(0)  # Force exit if threads don't stop cleanly

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Perform initial checks/starts within app context
    with app.app_context():
        # Make sure the database exists and is connectable
        try:
             # A simple query to check DB connection and table existence
             _ = db.session.query(Setting).first()
             # Start decoder only if DB seems okay
             if hasattr(app, 'decoder'):
                  app.decoder.init()
                  app.decoder.start()
             else:
                  app.logger.warning("Decoder object not found on app during init_app.")

        except Exception as err:  # Correct Python 3 syntax
            app.logger.error(f"Database check/connection failed: {err}. You may need to run 'flask initdb'.", exc_info=True)
            # Decide if you want to exit if DB isn't ready
            # os._exit(1)

# --- Configuration Helpers ---
def configure_app(app, config=None):
    """Load application configuration."""
    app.config.from_object(DefaultConfig)  # Load defaults first
    # Load instance config if it exists (production.cfg is unusual, typically 'config.py')
    app.config.from_pyfile('config.py', silent=True)  # Standard instance config file
    app.config.from_pyfile('production.cfg', silent=True)  # Keep if used

    if config:  # Allow override via passed object (e.g., TestConfig)
        app.config.from_object(config)

    # Ensure essential derived paths are set if not in config files
    app.config.setdefault('LOG_FOLDER', os.path.join(app.instance_path, 'logs'))
    app.config.setdefault('UPLOAD_FOLDER', os.path.join(app.instance_path, 'uploads'))
    app.config.setdefault('OPENID_FS_STORE_PATH', os.path.join(app.instance_path, 'openid_store'))
    app.config.setdefault('PROJECT_ROOT', os.path.dirname(os.path.dirname(__file__)))


def configure_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)  # Initialize Babel
    login_manager.init_app(app)  # Initialize LoginManager

    # Configure Flask-Login settings
    login_manager.login_view = 'frontend.login'  # Where to redirect if login required
    login_manager.refresh_view = 'frontend.reauth'  # Where to redirect for reauthentication
    login_manager.login_message_category = 'info'  # Flash message category

    # Configure Flask-OpenID if used (oid is imported from extensions)
    if oid:
         oid.init_app(app)
         oid.fs_store_path = app.config.get('OPENID_FS_STORE_PATH')


def configure_blueprints(app, blueprints):
    """Register Flask blueprints."""
    for blueprint in blueprints:
        app.register_blueprint(blueprint)


def configure_template_filters(app):
    """Configure Jinja2 template filters."""

    @app.template_filter()
    def format_date(value, format='%Y-%m-%d %H:%M'):  # Default format example
        if isinstance(value, datetime.datetime):
             return value.strftime(format)
        return value  # Return original if not a datetime object


def configure_logging(app):
    """Configure logging."""
    if not app.debug and not app.testing:  # Don't log to file in debug/test by default
         log_folder = app.config['LOG_FOLDER']
         if not os.path.exists(log_folder):
              os.makedirs(log_folder)

         info_log = os.path.join(log_folder, 'ad2web.log')  # Use a more specific name
         file_handler = logging.handlers.RotatingFileHandler(
             info_log, maxBytes=1024 * 1024 * 5, backupCount=5  # 5MB files
         )
         formatter = logging.Formatter(
             '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
         )
         file_handler.setFormatter(formatter)
         file_handler.setLevel(logging.INFO if not app.config.get('VERBOSE_LOGGING') else logging.DEBUG)
         app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.DEBUG if app.config['DEBUG'] else logging.INFO)
    app.logger.info('AlarmDecoder Webapp starting up...')


def configure_hook(app):
    """Register Flask hook functions (before/after request)."""
    safe_blueprints = {'setup', 'static', None}  # Use a set for faster lookups

    @app.before_request
    def before_request_checks():
        is_secure = request.is_secure or request.headers.get('X-Forwarded-Proto', 'http') == 'https'
        app.config['SESSION_COOKIE_SECURE'] = is_secure
        app.config['REMEMBER_COOKIE_SECURE'] = is_secure

        if request.blueprint not in safe_blueprints:
            try:
                 setup_stage = db.session.query(Setting.value).filter_by(name='setup_stage').scalar()
            except Exception:
                 setup_stage = None  # Assume setup not complete if DB error

            if setup_stage is None:
                 if request.endpoint != 'setup.index' and request.endpoint != 'setup.type':
                      return redirect(url_for('setup.index'))
            elif setup_stage != SETUP_COMPLETE:
                 current_stage_required = SETUP_ENDPOINT_STAGE.get(request.endpoint)
                 if request.blueprint != 'setup' or (current_stage_required and current_stage_required > setup_stage):
                      stage_endpoint = SETUP_STAGE_ENDPOINT.get(setup_stage, 'setup.index')
                      return redirect(url_for(stage_endpoint))

        if hasattr(app, 'decoder'):
             g.alarmdecoder = app.decoder
        else:
             g.alarmdecoder = None


    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def configure_error_handlers(app):
    """Register Flask error handlers."""
    @app.errorhandler(403)
    def forbidden_page(error):
        return render_template("errors/forbidden_page.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/page_not_found.html"), 404

    @app.errorhandler(500)
    def server_error_page(error):
        app.logger.error(f"Server Error: {error}", exc_info=True)
        return render_template("errors/server_error.html"), 500


def register_commands(app):
    @app.cli.command('initdb')
    @click.option('--drop', is_flag=True, help='Drop all tables before creating.')
    @with_appcontext
    def initdb_command(drop):
        """Initializes the database and seeds default data."""
        project_root = app.config.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(__file__)))
        alembic_ini_path = os.path.join(project_root, 'alembic.ini')
        if not os.path.exists(alembic_ini_path):
             click.echo(f"Warning: alembic.ini not found at {alembic_ini_path}. Skipping Alembic stamp.", err=True)
             alembic_cfg = None
        else:
             alembic_cfg = AlembicConfig(alembic_ini_path)

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

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user by ID."""
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

# Example: Add to end of ad2web/app.py for simple dev run
if __name__ == '__main__':
    # Important: create_app should now only return app
    app, socketio = create_app()
    # Use socketio.run to start the gevent server
    socketio.run(app, host='0.0.0.0', port=5000, debug=app.debug)
