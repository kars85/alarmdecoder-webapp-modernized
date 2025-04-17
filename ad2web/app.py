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
from .utils import INSTANCE_FOLDER_PATH, user_is_authenticated  # Import user_is_authenticated here
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
        # Ensure forwarded_for is a list of non-empty strings
        forwarded_for = [x.strip() for x in forwarded_for if x.strip()]
        if len(forwarded_for) >= self.num_proxies:
            # Return the IP address based on the number of trusted proxies
            return forwarded_for[-1 * self.num_proxies]
        # Return None or a default if not enough proxies are present
        # Depending on security needs, might want to log this or return None
        return None  # Or potentially environ.get('REMOTE_ADDR') as a fallback

    def __call__(self, environ, start_response):
        getter = environ.get
        forwarded_proto = getter("HTTP_X_FORWARDED_PROTO", "")
        forwarded_for_str = getter("HTTP_X_FORWARDED_FOR", "")
        forwarded_host = getter("HTTP_X_FORWARDED_HOST", "")
        script_name = getter("HTTP_X_SCRIPT_NAME", "")
        scheme = getter("HTTP_X_SCHEME", "")
        server = getter("HTTP_X_FORWARDED_SERVER", "")

        # Handle wsgi.url_scheme
        if scheme:
            environ["wsgi.url_scheme"] = scheme
        elif forwarded_proto:
            environ["wsgi.url_scheme"] = forwarded_proto
        # else: keep the original wsgi.url_scheme

        # Handle HTTP_HOST
        if server:
            environ["HTTP_HOST"] = server
        elif forwarded_host:
            environ["HTTP_HOST"] = forwarded_host
        # else: keep the original HTTP_HOST

        # Handle REMOTE_ADDR
        if forwarded_for_str:
            forwarded_for_list = forwarded_for_str.split(",")
            remote_addr = self.get_remote_addr(forwarded_for_list)
            if remote_addr:
                environ["REMOTE_ADDR"] = remote_addr
            # else: keep the original REMOTE_ADDR

        # Handle SCRIPT_NAME and PATH_INFO
        if script_name:
            original_script_name = environ.get("SCRIPT_NAME", "")
            original_path_info = environ.get("PATH_INFO", "")

            # Combine script names if necessary, ensuring no double slashes
            combined_script_name = f"{original_script_name.rstrip('/')}/{script_name.lstrip('/')}"
            environ["SCRIPT_NAME"] = combined_script_name

            # Adjust PATH_INFO only if it starts with the forwarded script name
            if original_path_info.startswith(script_name):
                # Ensure the remaining path starts with a slash or is empty
                new_path_info = original_path_info[len(script_name) :]
                environ["PATH_INFO"] = (
                    new_path_info if new_path_info.startswith("/") else f"/{new_path_info}"
                )
            # else: keep original PATH_INFO

        return self.app(environ, start_response)


# --- App Factory ---
def create_app(config=None, app_name=None, blueprints=None):
    """Create a Flask app."""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    os.makedirs(INSTANCE_FOLDER_PATH, exist_ok=True)

    flask_app = Flask(app_name, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)

    configure_app(flask_app, config)  # Configure first
    # Apply middleware after initial config but before extensions/blueprints if it affects env vars they might use
    flask_app.wsgi_app = ReverseProxied(
        flask_app.wsgi_app, num_proxies=flask_app.config.get("NUM_PROXIES", 1)
    )

    configure_extensions(flask_app)
    configure_blueprints(flask_app, blueprints)
    configure_logging(flask_app)
    configure_template_filters(flask_app)
    configure_template_globals(flask_app)  # Renamed for clarity
    configure_hook(flask_app)  # Configure hooks after blueprints and extensions
    configure_error_handlers(flask_app)
    register_commands(flask_app)

    # Initialize SocketIO after app configuration
    socketio = SocketIO(flask_app)

    # Initialize app-specific components
    # Important: create_decoder_socket uses app, not socketio directly
    create_decoder_socket(flask_app)  # Pass app, not socketio
    decoder = Decoder(flask_app)
    flask_app.decoder = decoder  # Attach decoder to app instance

    return flask_app, socketio


# --- Configuration Functions ---
def configure_app(app, config_override=None):
    """Load application configuration."""
    app.config.from_object("ad2web.config.DefaultConfig")  # Base defaults
    app.config.from_pyfile("config.py", silent=True)  # Instance config
    app.config.from_pyfile("production.cfg", silent=True)  # Production overrides

    # Apply testing or explicit overrides
    if config_override:
        if isinstance(config_override, dict):
            app.config.update(config_override)
        else:  # Assume it's a config object/class
            app.config.from_object(config_override)

    # Set derived/default paths
    app.config.setdefault("LOG_FOLDER", os.path.join(app.instance_path, "logs"))
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads"))
    app.config.setdefault("OPENID_FS_STORE_PATH", os.path.join(app.instance_path, "openid_store"))
    app.config.setdefault(
        "PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def configure_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = "frontend.login"  # Endpoint name for the login view
    login_manager.refresh_view = "frontend.reauth"  # Endpoint for reauthentication
    login_manager.login_message_category = "info"  # Flash message category

    # Configure Flask-OpenID if enabled
    if oid:
        oid.init_app(app)
        # Ensure the store path exists
        oid_store_path = app.config.get("OPENID_FS_STORE_PATH")
        if oid_store_path:
            os.makedirs(oid_store_path, exist_ok=True)
            oid.fs_store_path = oid_store_path


def configure_blueprints(app, blueprints):
    """Register blueprints with the Flask app, avoiding duplicates."""
    for blueprint in blueprints:
        if blueprint.name not in app.blueprints:
            app.register_blueprint(blueprint)


def configure_template_filters(app):
    """Register custom Jinja2 template filters."""

    @app.template_filter()
    def format_date(value, format="%Y-%m-%d %H:%M"):
        """Format a datetime object."""
        if isinstance(value, datetime.datetime):
            return value.strftime(format)
        return value


def configure_template_globals(app):
    """Register template globals."""

    @app.context_processor
    def inject_globals():
        """Inject commonly needed variables into template context."""
        # Note: current_user is already available if Flask-Login is configured
        return dict(user_is_authenticated=user_is_authenticated)


def configure_logging(app):
    """Configure application logging."""
    # Basic configuration based on DEBUG setting
    log_level = logging.DEBUG if app.config["DEBUG"] else logging.INFO
    app.logger.setLevel(log_level)

    # Remove default Flask handler if present to avoid duplicate console logs
    # (This might vary depending on Flask version)
    # Example: del app.logger.handlers[:]

    # Console Handler (useful for development and seeing logs immediately)
    # You might want to disable this in production if using file/other handlers
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )
    stream_handler.setFormatter(stream_formatter)
    if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
        app.logger.addHandler(stream_handler)

    # File Handler (only if not in debug/testing)
    if not app.debug and not app.testing:
        log_folder = app.config["LOG_FOLDER"]
        os.makedirs(log_folder, exist_ok=True)
        log_path = os.path.join(log_folder, "ad2web.log")
        file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        file_formatter = logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(
            logging.INFO if not app.config.get("VERBOSE_LOGGING") else logging.DEBUG
        )
        app.logger.addHandler(file_handler)

    app.logger.info("AlarmDecoder Webapp logging configured.")


def configure_hook(app):
    """Register before/after request hooks."""
    # Define blueprints that don't require setup checks
    # safe_blueprints = {'setup', 'static', None} # None is for requests not matching a blueprint

    @app.before_request
    def before_request_checks():
        """Perform checks before handling the request."""
        safe_blueprints = {"setup", "static", None}
        print(f"--- ENTERING before_request_checks. app.testing={app.testing} ---")  # DEBUG
        # --- Common checks ---
        is_secure = request.is_secure or request.headers.get("X-Forwarded-Proto", "http") == "https"
        app.config["SESSION_COOKIE_SECURE"] = is_secure
        app.config["REMEMBER_COOKIE_SECURE"] = is_secure
        g.alarmdecoder = getattr(app, "decoder", None)

        # --- Conditional setup checks (skipped during testing) ---
        if not app.testing:
            if request.blueprint not in safe_blueprints:
                try:
                    # Query database for setup stage
                    setup_stage = (
                        db.session.query(Setting.value).filter_by(name="setup_stage").scalar()
                    )
                except Exception as e:
                    # Log error and assume setup isn't complete if DB fails
                    app.logger.error(
                        f"Error querying setup_stage in before_request: {e}", exc_info=True
                    )
                    setup_stage = None

                if setup_stage is None:
                    # Redirect to setup if not complete and not already in setup
                    if request.endpoint not in {
                        "setup.index",
                        "setup.type",
                    }:  # Allow initial setup pages
                        app.logger.debug(
                            f"Setup not started. Redirecting to setup.index (from {request.endpoint})"
                        )
                        return redirect(url_for("setup.index"))
                elif setup_stage != SETUP_COMPLETE:
                    # Check if current page requires a higher setup stage
                    required_stage = SETUP_ENDPOINT_STAGE.get(request.endpoint)
                    if request.blueprint != "setup" or (
                        required_stage and required_stage > setup_stage
                    ):
                        # Redirect to the correct setup stage page
                        target_endpoint = SETUP_STAGE_ENDPOINT.get(setup_stage, "setup.index")
                        app.logger.debug(
                            f"Setup stage {setup_stage} required, redirecting to {target_endpoint} (from {request.endpoint})"
                        )
                        return redirect(url_for(target_endpoint))

        # No redirect needed, continue request processing
        return None

    @app.after_request
    def apply_security_headers(response):
        """Apply security headers to the response."""
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Add other headers like CSP if needed
        return response


def configure_error_handlers(app):
    """Register error handlers."""

    @app.errorhandler(403)
    def forbidden_page(error):
        app.logger.warning(f"Forbidden (403) access attempt: {request.url} - {error}")
        return render_template("errors/forbidden_page.html"), 403

    @app.errorhandler(404)
    def page_not_found(_error):
        app.logger.info(f"Page not found (404): {request.url} - {_error}")
        try:
            # Attempt to render the (now simplified) template
            return render_template("errors/page_not_found.html"), 404
        except Exception as render_err:
            print(f"!!! ERROR rendering 404 template: {render_err}")  # Keep this catch
            app.logger.error(f"Error rendering 404 template for {_error}", exc_info=True)
            return "<h1>Not Found</h1><p>An error occurred rendering the error page.</p>", 404

    @app.errorhandler(500)
    def server_error_page(error):
        app.logger.error(f"Server Error (500): {request.url} - {error}", exc_info=True)
        # Avoid complex rendering in 500 handler if possible
        try:
            return render_template("errors/server_error.html"), 500
        except Exception as render_err:
            print(f"!!! ERROR rendering 500 template: {render_err}")
            app.logger.error(
                f"!!! Additionally failed to render 500 template: {render_err}", exc_info=True
            )
            return (
                "<h1>Server Error</h1><p>An internal server error occurred, and the error page could not be rendered.</p>",
                500,
            )


def register_commands(app):
    """Register custom Flask CLI commands."""

    @app.cli.command("initdb")
    @click.option("--drop", is_flag=True, help="Drop all tables before creating.")
    @with_appcontext
    def initdb_command(drop):
        """Initialize the database."""
        root = app.config.get("PROJECT_ROOT", os.path.dirname(os.path.dirname(__file__)))
        alembic_ini = os.path.join(root, "alembic.ini")
        alembic_cfg = AlembicConfig(alembic_ini) if os.path.exists(alembic_ini) else None

        if drop:
            if click.confirm(
                "This operation will drop existing database tables. Do you want to continue?",
                abort=True,
            ):
                click.echo("Dropping database tables...")
                db.drop_all()
                click.echo("Dropped database tables.")

        click.echo("Creating database tables...")
        try:
            db.create_all()
            click.echo("Initialized the database tables.")

            # Stamp Alembic revision if config exists
            if alembic_cfg:
                click.echo("Stamping Alembic revision to head...")
                alembic_command.stamp(alembic_cfg, "head")
                click.echo("Alembic revision stamped.")

            click.echo("Database initialization complete!")

        except Exception as err:
            db.session.rollback()  # Ensure transaction is rolled back on error
            click.echo(f"Database initialization failed: {err}", err=True)
            app.logger.error(f"Database initialization failed: {err}", exc_info=True)


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None  # Invalid user_id format


# --- Main Execution ---
if __name__ == "__main__":
    # This block runs only when the script is executed directly (e.g., python -m ad2web.app)
    # It's typically used for development server startup.
    flask_app, socketio = create_app()  # Create app using default config
    # Use SocketIO's run method for development server
    socketio.run(
        flask_app,
        host=flask_app.config.get("HOST", "0.0.0.0"),
        port=flask_app.config.get("PORT", 5000),
        debug=flask_app.debug,
        use_reloader=flask_app.debug,  # Use reloader only in debug mode
    )
