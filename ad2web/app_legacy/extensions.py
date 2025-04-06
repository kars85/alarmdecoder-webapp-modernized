from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_babelplus import Babel
#from ad2web.user.models import User

db = SQLAlchemy()
login_manager = LoginManager()
babel = Babel()
# Function to dynamically import User and related constants
def get_user_and_detail():
    user_module = importlib.import_module('ad2web.user')
    return user_module.User, user_module.USER_ROLE, user_module.USER_STATUS, user_module.ADMIN
@login_manager.user_loader
def load_user(user_id):
    # Use the function to get User, UserDetail, USER_ROLE, USER_STATUS, and ADMIN when needed
User, UserDetail, USER_ROLE, USER_STATUS, ADMIN = get_user_and_detail()
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

