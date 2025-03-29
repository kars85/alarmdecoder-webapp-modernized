from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_babelplus import Babel
from ad2web.user.models import User

db = SQLAlchemy()
login_manager = LoginManager()
babel = Babel()

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

