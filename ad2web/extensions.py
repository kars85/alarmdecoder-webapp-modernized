# -*- coding: utf-8 -*-

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

from flask_mail import Mail
mail = Mail()

from flask_login import LoginManager
login_manager = LoginManager()

from flask_openid import OpenID
oid = OpenID()

from flask_babelplus import Babel
babel = Babel()
