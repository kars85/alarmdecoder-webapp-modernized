# ad2web/extensions.py

# --- Existing Imports ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_openid import OpenID
from flask_babel import Babel
# ... any other extension imports ...

# --- Add SocketIO Import ---
from flask_socketio import SocketIO

# --- Existing Instances ---
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
oid = OpenID() # Or None if not used
babel = Babel()
# ... any other extension instances ...

# --- Add SocketIO Instance ---
socketio = SocketIO()