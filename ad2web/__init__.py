# ad2web/__init__.py
# Make sure ALL constants used below are imported or defined
# It looks like UPLOAD_FOLDER and OPENID_FS_STORE_PATH might be missing?
# Assuming they are also in utils for this example:
from ad2web.extensions import login_manager  # mail needs to be added here if defined in extensions

# Import the User model
from ad2web.user.models import User  # Adjust path if needed


# --- Fix #1: Add Flask-Login user_loader ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user by ID."""
    try:
        # Ensure user_id is converted to the correct type for querying (usually int)
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        # Handle cases where user_id might not be a valid integer
        # Or if the user does not exist for any reason
        return None


# --- End Fix #1 ---

# --- Fix #4: Prepare for Flask-Mail - Assuming 'mail' is in extensions.py ---
# from ad2web.extensions import mail # Uncomment if mail is defined there

# def create_app(config_object='ad2web.config.DefaultConfig'): # Added default config path
#    # In your create_app function (e.g., ad2web/__init__.py)
#    from ad2web.frontend import frontend as frontend_blueprint # Import the blueprint
#    app.register_blueprint(frontend_blueprint)                # Register it
#    """Application Factory"""
#    app = Flask(__name__, instance_relative_config=True, instance_path=INSTANCE_FOLDER_PATH)

# Load configuration
#    app.config.from_object(config_object) # Load defaults from config.py first
#    app.config.from_pyfile('config.py', silent=True) # Load instance config overrides

# Ensure instance folder exists and other necessary folders
#    try:
#        os.makedirs(app.instance_path, exist_ok=True)
#        make_dir(LOG_FOLDER)
#        # Define UPLOAD_FOLDER and OPENID_FS_STORE_PATH in config or ensure they are correctly imported
# Example assuming they are in config:
#        make_dir(app.config.get('UPLOAD_FOLDER', os.path.join(app.instance_path, 'uploads')))
#        make_dir(app.config.get('OPENID_FS_STORE_PATH', os.path.join(app.instance_path, 'openid_store')))
#    except OSError as e:
#         app.logger.error(f"Error creating instance folders: {e}")


# --- Initialize Extensions ---
#    db.init_app(app)
#    login_manager.init_app(app) # Already done, perfect
#    babel.init_app(app)
# --- Fix #4: Initialize Flask-Mail ---
# mail.init_app(app) # Uncomment and ensure mail is imported if using Flask-Mail

# --- Setup AlarmDecoder Service ---
#    setup_alarmdecoder(app) # Assuming this sets up current_app.decoder needed elsewhere

# --- Register Blueprints ---
# Fix #2: Register ALL necessary blueprints
#    app.register_blueprint(main_blueprint)
# Add other blueprints that contain your routes:
#    from ad2web.frontend import frontend as frontend_blueprint # Example
#    app.register_blueprint(frontend_blueprint)                # Example

#    from ad2web.settings import settings as settings_blueprint # Example
#    app.register_blueprint(settings_blueprint)                 # Example

#    from ad2web.user import user as user_blueprint             # Example
#    app.register_blueprint(user_blueprint)                     # Example

#    from ad2web.admin import admin as admin_blueprint          # Example
#    app.register_blueprint(admin_blueprint)                    # Example

# ... register any other blueprints (certificate, log, api, etc.) ...


# --- Register Error Handlers ---
# Fix #5: Register error handlers
#    register_error_handlers(app)


#    return app


def register_error_handlers(app):
    """Helper function to register error handlers."""
    from flask import render_template

    @app.errorhandler(404)
    def page_not_found(e):
        # Assuming you have this template
        return render_template("errors/page_not_found.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        # Assuming you have this template
        # Log the error e here
        return render_template("errors/server_error.html"), 500

    # Add other handlers (403, etc.) as needed
